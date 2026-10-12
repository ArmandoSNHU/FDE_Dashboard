"""One sync run, end to end: extract, normalise, reconcile, and (only with apply) load."""

from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fde_sync.extract import fetch_api, read_csv
from fde_sync.legacy import Woms
from fde_sync.load import LoadResult, apply_plan
from fde_sync.normalise import normalise
from fde_sync.reconcile import Plan, reconcile
from fde_sync.store import SyncError, migrate, open_db, read_ledger

Outcome = Literal["ok", "partial", "failed"]


@dataclass
class RunResult:
    started_at: str
    mode: Literal["dry-run", "apply"]
    outcome: Outcome
    plan: Plan | None = None
    load: LoadResult | None = None
    api_complete: bool = True
    api_errors: list[str] = field(default_factory=list)
    error: str = ""


def run_sync(
    woms: Woms,
    db_path: Path,
    *,
    apply: bool,
    export_text: str | None,
    started_at: str | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> RunResult:
    started_at = started_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = RunResult(started_at, "apply" if apply else "dry-run", "failed")

    # The export is the source of truth: without it there is nothing to reconcile against.
    if export_text is None:
        result.error = "nightly export missing: nothing was read or written"
        return result

    api = fetch_api(woms, sleep=sleep)
    result.api_complete, result.api_errors = api.complete, api.errors
    api_orders = [normalise(r, source="api") for r in api.records]
    csv_orders = [normalise(r, source="csv") for r in read_csv(export_text)]

    try:
        with closing(open_db(db_path, readonly=not apply)) as conn:
            result.plan = reconcile(api_orders, csv_orders, read_ledger(conn))
            outcome: Outcome = "ok" if api.complete else "partial"
            if apply:
                migrate(conn)
                result.load = apply_plan(conn, result.plan, started_at=started_at, outcome=outcome)
            result.outcome = outcome
    except SyncError as exc:
        result.error = str(exc)
    return result
