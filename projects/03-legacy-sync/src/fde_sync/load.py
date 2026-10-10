"""Apply a plan to the ops database: the only module in the sync that writes.

All of a run's writes happen in one transaction. If anything fails part way, SQLite rolls
the whole run back, so the on-call view never shows half a sync. Nothing is ever deleted:
a closed or cancelled work order stays an incident, with its status in the summary.

Project 01's incidents table has no status column, which is why the status lives in the
summary text. Adding the column is a change to project 01's contract, and out of scope here.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from fde_sync.model import WorkOrder
from fde_sync.reconcile import Plan
from fde_sync.store import SOURCE

CUSTOMER = "northwind"


@dataclass(frozen=True)
class LoadResult:
    inserted: int
    updated: int


def summary(order: WorkOrder) -> str:
    return f"[{order.trade}][{order.status}] {order.description} ({order.site})"


def apply_plan(conn: sqlite3.Connection, plan: Plan, *, started_at: str, outcome: str) -> LoadResult:
    inserted = updated = 0
    try:
        for decision in plan.decisions:
            order = decision.order
            if decision.action == "new" and order is not None:
                incident_id = conn.execute(
                    "INSERT INTO incidents (customer, summary, severity, created_at) VALUES (?, ?, ?, ?) RETURNING id",
                    (CUSTOMER, summary(order), order.severity, order.opened_at),
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO sync_ledger (source, external_key, incident_id, content_hash, synced_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (SOURCE, order.key, incident_id, order.content_hash(), started_at),
                )
                inserted += 1
            elif decision.action == "changed" and order is not None:
                conn.execute(
                    "UPDATE incidents SET summary = ?, severity = ? WHERE id = ?",
                    (summary(order), order.severity, decision.incident_id),
                )
                conn.execute(
                    "UPDATE sync_ledger SET content_hash = ?, synced_at = ? WHERE source = ? AND external_key = ?",
                    (order.content_hash(), started_at, SOURCE, order.key),
                )
                updated += 1
        counts = {action: plan.count(action) for action in ("new", "changed", "unchanged", "skipped", "rejected", "held")}
        conn.execute(
            "INSERT INTO sync_runs (started_at, mode, outcome, counts_json) VALUES (?, 'apply', ?, ?)",
            (started_at, outcome, json.dumps(counts)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return LoadResult(inserted, updated)
