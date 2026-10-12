"""Writing a plan: one transaction, nothing deleted, and a second run has nothing to do."""

import sqlite3

import pytest

from fde_sync.load import apply_plan, summary
from fde_sync.model import WorkOrder
from fde_sync.reconcile import reconcile
from fde_sync.store import migrate, open_db, read_ledger


def order(key="EAST:1001", status="open", severity="high"):
    return WorkOrder(key=key, opened_at="2024-07-03T13:15:00Z", status=status, severity=severity,
                     trade="PLUMBING", site="1 MAIN ST", description="PLUMBING: LEAK")


def run(db, orders):
    with open_db(db, readonly=False) as conn:
        migrate(conn)
        plan = reconcile(orders, orders, read_ledger(conn))
        return apply_plan(conn, plan, started_at="2024-07-15T06:05:00Z", outcome="ok")


def incidents(db):
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT id, customer, summary, severity, created_at FROM incidents ORDER BY id").fetchall()


def test_summary_carries_trade_status_description_and_site():
    assert summary(order()) == "[PLUMBING][open] PLUMBING: LEAK (1 MAIN ST)"


def test_new_orders_become_northwind_incidents_with_their_real_open_time(ops_db):
    result = run(ops_db, [order(), order("METRO:1001", severity="critical")])
    assert (result.inserted, result.updated) == (2, 0)
    rows = incidents(ops_db)
    assert [r[1] for r in rows] == ["northwind", "northwind"]
    assert rows[0][4] == "2024-07-03T13:15:00Z"


def test_a_second_run_over_the_same_data_writes_nothing(ops_db):
    run(ops_db, [order(), order("METRO:1001")])
    again = run(ops_db, [order(), order("METRO:1001")])
    assert (again.inserted, again.updated) == (0, 0)
    assert len(incidents(ops_db)) == 2


def test_a_changed_order_updates_the_same_incident(ops_db):
    run(ops_db, [order()])
    result = run(ops_db, [order(status="closed", severity="low")])
    assert (result.inserted, result.updated) == (0, 1)
    [(incident_id, _, text, severity, _)] = incidents(ops_db)
    assert text.startswith("[PLUMBING][closed]") and severity == "low"


def test_every_applied_run_is_recorded(ops_db):
    run(ops_db, [order()])
    run(ops_db, [order()])
    with sqlite3.connect(ops_db) as conn:
        runs = conn.execute("SELECT mode, outcome, counts_json FROM sync_runs").fetchall()
    assert [r[:2] for r in runs] == [("apply", "ok"), ("apply", "ok")]
    assert '"new": 1' in runs[0][2] and '"unchanged": 1' in runs[1][2]


def test_a_failure_part_way_through_leaves_the_database_as_it_was(ops_db):
    # The second order breaks project 01's CHECK on severity after the first has been inserted.
    with pytest.raises(sqlite3.IntegrityError):
        run(ops_db, [order(), order("METRO:1001", severity="urgent")])
    assert incidents(ops_db) == []
    with open_db(ops_db, readonly=True) as conn:
        assert read_ledger(conn) == {}
