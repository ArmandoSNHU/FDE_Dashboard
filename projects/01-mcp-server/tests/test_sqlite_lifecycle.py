"""Connections must close deterministically, not when garbage collection runs."""
import sqlite3
from pathlib import Path

import pytest

from fde_mcp.connectors.sqlite import SQLiteConnector
from fde_mcp.errors import SourceError


@pytest.fixture
def tracked(tmp_path, monkeypatch):
    path = tmp_path / 'synthetic.db'
    raw = sqlite3.connect(path)
    raw.executescript((Path(__file__).resolve().parents[1] / 'db/schema.sql').read_text(encoding='utf-8'))
    raw.close()
    opened = []
    behavior = {'fail': None}
    connect = sqlite3.connect

    class TrackedConnection(sqlite3.Connection):
        was_closed = False

        def close(self):
            self.was_closed = True
            super().close()

        def execute(self, statement, *args, **kwargs):
            if behavior['fail'] and statement.lstrip().startswith(behavior['fail']):
                raise sqlite3.OperationalError('synthetic failure')
            return super().execute(statement, *args, **kwargs)

    def open_tracked(*args, **kwargs):
        connection = connect(*args, **kwargs, factory=TrackedConnection)
        opened.append(connection)  # Retain it so a GC side effect cannot hide a leak.
        return connection

    monkeypatch.setattr(sqlite3, 'connect', open_tracked)
    return SQLiteConnector(path), opened, behavior


async def invoke(conn, action):
    if action == 'read':
        return await conn.recent_deployments('synthetic-customer')
    if action == 'incident':
        return await conn.log_incident('synthetic-customer', 'Synthetic incident', 'low')
    return await conn.enqueue_alert('Synthetic alert', 'low', 'Synthetic outage')


@pytest.mark.parametrize('action', ['read', 'incident', 'outbox'])
async def test_closes_connection_after_success(tracked, action):
    conn, opened, _ = tracked
    await invoke(conn, action)
    assert len(opened) == 1
    assert opened[0].was_closed


@pytest.mark.parametrize('action', ['read', 'incident', 'outbox'])
async def test_closes_connection_after_query_failure(tracked, action):
    conn, opened, behavior = tracked
    behavior['fail'] = 'SELECT' if action == 'read' else 'INSERT'
    with pytest.raises(SourceError):
        await invoke(conn, action)
    assert opened[0].was_closed


async def test_closes_connection_when_configuration_fails(tracked):
    conn, opened, behavior = tracked
    behavior['fail'] = 'PRAGMA'
    with pytest.raises(SourceError):
        await conn.recent_deployments('synthetic-customer')
    assert opened[0].was_closed
