"""Project 03 adds its own tables to project 01's database and touches nothing else."""

import sqlite3

import pytest

from fde_sync.store import SyncError, is_migrated, migrate, open_db, read_ledger


def schema_of(path, tables):
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table'").fetchall()
    return {name: sql for name, sql in rows if name in tables}


def test_migration_adds_our_tables_and_leaves_project_01s_untouched(ops_db):
    owned_by_01 = {"deployments", "incidents", "alert_outbox"}
    before = schema_of(ops_db, owned_by_01)
    with open_db(ops_db, readonly=False) as conn:
        migrate(conn)
        assert is_migrated(conn)
    assert schema_of(ops_db, owned_by_01) == before
    assert set(schema_of(ops_db, {"sync_ledger", "sync_runs"})) == {"sync_ledger", "sync_runs"}


def test_migrating_twice_is_harmless(ops_db):
    with open_db(ops_db, readonly=False) as conn:
        migrate(conn)
        migrate(conn)
        assert read_ledger(conn) == {}


def test_an_unmigrated_db_has_an_empty_ledger(ops_db):
    with open_db(ops_db, readonly=True) as conn:
        assert not is_migrated(conn)
        assert read_ledger(conn) == {}


def test_a_read_only_connection_cannot_write(ops_db):
    with open_db(ops_db, readonly=True) as conn, pytest.raises(sqlite3.OperationalError):
        migrate(conn)


def test_a_missing_db_is_an_error_and_is_not_created(tmp_path):
    missing = tmp_path / "nope.db"
    with pytest.raises(SyncError, match="ops DB not found"):
        open_db(missing, readonly=False)
    assert not missing.exists()
