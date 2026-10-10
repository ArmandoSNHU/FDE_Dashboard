"""The rollback in engagement/rollback.md must do exactly what it says, so it is tested, not just written."""

import sqlite3
from contextlib import closing
from pathlib import Path

from fde_sync.legacy import build_woms
from fde_sync.sync import run_sync

from conftest import SAMPLE

ROLLBACK = Path(__file__).resolve().parents[1] / "ops" / "rollback.sql"


def apply(db):
    woms = build_woms(SAMPLE)
    return run_sync(woms, db, apply=True, export_text=woms.csv_export(), started_at="2024-07-15T06:05:00Z")


def count(db, sql):
    with closing(sqlite3.connect(db)) as conn:
        return conn.execute(sql).fetchone()[0]


def test_rollback_removes_only_what_the_sync_wrote_and_keeps_the_audit_trail(ops_db):
    apply(ops_db)
    with closing(sqlite3.connect(ops_db)) as conn:
        conn.execute("INSERT INTO incidents (customer, summary, severity) VALUES ('acme', 'manual entry', 'low')")
        conn.execute("INSERT INTO incidents (customer, summary, severity) VALUES ('northwind', 'logged by hand', 'low')")
        conn.commit()
        conn.executescript(ROLLBACK.read_text(encoding="utf-8"))

    assert count(ops_db, "SELECT COUNT(*) FROM incidents WHERE customer = 'acme'") == 1
    # A northwind incident someone logged by hand is not the sync's to remove.
    assert count(ops_db, "SELECT COUNT(*) FROM incidents WHERE customer = 'northwind'") == 1
    assert count(ops_db, "SELECT COUNT(*) FROM sync_ledger") == 0
    assert count(ops_db, "SELECT COUNT(*) FROM sync_runs") == 1


def test_after_a_rollback_the_next_run_loads_everything_again(ops_db):
    first = apply(ops_db)
    with closing(sqlite3.connect(ops_db)) as conn:
        conn.executescript(ROLLBACK.read_text(encoding="utf-8"))
    assert apply(ops_db).load.inserted == first.load.inserted
