"""SQLite connector: read/write separation, validation, and lock behaviour.

Each test gets its own database file built from db/schema.sql — the real schema,
so a schema change that breaks these queries fails here.
"""

import sqlite3
from pathlib import Path

import pytest

from fde_mcp.connectors.sqlite import SQLiteConnector
from fde_mcp.errors import ErrorKind, SourceError

SCHEMA = Path(__file__).resolve().parents[1] / "db" / "schema.sql"

SEED = """
INSERT INTO deployments (customer, service, version, environment, deployed_at) VALUES
  ('acme',   'api',     '1.4.0', 'prod',    '2026-09-10T09:00:00Z'),
  ('acme',   'api',     '1.4.1', 'prod',    '2026-09-12T14:30:00Z'),
  ('acme',   'worker',  '0.9.2', 'staging', '2026-09-11T08:15:00Z'),
  ('globex', 'api',     '2.0.0', 'prod',    '2026-09-13T10:00:00Z');
"""


@pytest.fixture
def db_path(tmp_path) -> Path:
    path = tmp_path / "ops.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        conn.executescript(SEED)
    return path


@pytest.fixture
def conn(db_path) -> SQLiteConnector:
    return SQLiteConnector(db_path)


# --- reads -------------------------------------------------------------------


async def test_recent_deployments_newest_first_for_that_customer_only(conn):
    rows = await conn.recent_deployments("acme")
    assert [r["version"] for r in rows] == ["1.4.1", "0.9.2", "1.4.0"]
    assert {r["customer"] for r in rows} == {"acme"}
    assert rows[0] == {
        "id": 2,
        "customer": "acme",
        "service": "api",
        "version": "1.4.1",
        "environment": "prod",
        "deployed_at": "2026-09-12T14:30:00Z",
    }


async def test_limit_caps_rows(conn):
    assert len(await conn.recent_deployments("acme", limit=2)) == 2


async def test_unknown_customer_is_empty_not_an_error(conn):
    assert await conn.recent_deployments("nobody") == []


async def test_customer_is_parameterised_not_interpolated(conn):
    # If this were string-formatted SQL, the quote would raise instead of returning [].
    assert await conn.recent_deployments("acme'; DROP TABLE deployments;--") == []
    assert len(await conn.recent_deployments("acme")) == 3


@pytest.mark.parametrize("limit", [0, -1, 101, "ten", None])
async def test_invalid_limit_rejected(conn, limit):
    with pytest.raises(SourceError) as exc:
        await conn.recent_deployments("acme", limit=limit)
    assert exc.value.kind == ErrorKind.INVALID_INPUT


async def test_read_path_opens_the_file_read_only(conn):
    """The read connection must reject writes even if a future query tries one."""
    with conn._connect(readonly=True) as ro:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            ro.execute("INSERT INTO incidents (customer, summary, severity) VALUES ('x', 'y', 'low')")


# --- writes ------------------------------------------------------------------


async def test_log_incident_persists_and_returns_identity(conn, db_path):
    created = await conn.log_incident("acme", "API 500s after 1.4.1", "high")
    assert created["id"] >= 1
    assert created["created_at"]
    with sqlite3.connect(db_path) as raw:
        row = raw.execute("SELECT customer, summary, severity FROM incidents WHERE id = ?", (created["id"],)).fetchone()
    assert row == ("acme", "API 500s after 1.4.1", "high")


@pytest.mark.parametrize("severity", ["", "urgent", "HIGH", None, 3])
async def test_invalid_severity_rejected_before_writing(conn, db_path, severity):
    with pytest.raises(SourceError) as exc:
        await conn.log_incident("acme", "summary", severity)
    assert exc.value.kind == ErrorKind.INVALID_INPUT
    with sqlite3.connect(db_path) as raw:
        assert raw.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 0


@pytest.mark.parametrize(("customer", "summary"), [("", "s"), ("acme", ""), ("acme", "   ")])
async def test_empty_fields_rejected(conn, customer, summary):
    with pytest.raises(SourceError) as exc:
        await conn.log_incident(customer, summary, "low")
    assert exc.value.kind == ErrorKind.INVALID_INPUT


async def test_enqueue_alert_stores_undelivered_alert(conn, db_path):
    row_id = await conn.enqueue_alert("prod api down", "critical", "telegram unavailable")
    with sqlite3.connect(db_path) as raw:
        row = raw.execute("SELECT message, severity, reason, delivered_at FROM alert_outbox WHERE id = ?", (row_id,)).fetchone()
    assert row == ("prod api down", "critical", "telegram unavailable", None)


# --- failure modes -----------------------------------------------------------


async def test_locked_database_is_retryable_unavailable(db_path):
    blocked = SQLiteConnector(db_path, busy_timeout_ms=50)  # keep the test fast
    holder = sqlite3.connect(db_path, isolation_level=None)
    try:
        holder.execute("BEGIN EXCLUSIVE")
        with pytest.raises(SourceError) as exc:
            await blocked.log_incident("acme", "while locked", "low")
        assert exc.value.kind == ErrorKind.UNAVAILABLE
        assert exc.value.retryable is True
    finally:
        holder.close()


async def test_missing_table_is_unavailable_not_retryable(tmp_path):
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()  # a real SQLite file with no schema
    with pytest.raises(SourceError) as exc:
        await SQLiteConnector(empty).recent_deployments("acme")
    assert exc.value.kind == ErrorKind.UNAVAILABLE
    assert exc.value.retryable is False


async def test_corrupt_file_is_reported_not_crashed(tmp_path):
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"this is definitely not a sqlite database" * 10)
    with pytest.raises(SourceError) as exc:
        await SQLiteConnector(corrupt).recent_deployments("acme")
    assert exc.value.kind == ErrorKind.UNAVAILABLE


async def test_reads_do_not_block_the_event_loop(conn):
    """Queries run in a worker thread, so a slow disk can't stall the whole server."""
    import asyncio

    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0)
            ticks += 1

    spinner = asyncio.create_task(ticker())
    await conn.recent_deployments("acme")
    spinner.cancel()
    assert ticks > 0
