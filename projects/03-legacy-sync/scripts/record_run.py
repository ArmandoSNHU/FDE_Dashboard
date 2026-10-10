"""Record a real sync run's numbers for the dashboard. Writes results/sync-run.json.

    uv run python scripts/record_run.py

Runs the sync three times against a fresh ops DB built from project 01's schema: a dry run,
an apply, and a second apply that should write nothing. The dashboard shows these numbers
and nothing else, so the page can't claim more than this script produced.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from fde_sync.legacy import build_woms
from fde_sync.sync import run_sync

PROJECT = Path(__file__).resolve().parents[1]
SAMPLE = PROJECT / "data" / "nyc311_sample.csv"
OPS_SCHEMA = PROJECT.parent / "01-mcp-server" / "db" / "schema.sql"
OUT = PROJECT / "results" / "sync-run.json"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fde-sync-record-") as tmp:
        db = Path(tmp) / "ops.db"
        with closing(sqlite3.connect(db)) as conn:
            conn.executescript(OPS_SCHEMA.read_text(encoding="utf-8"))

        def run(apply: bool):
            woms = build_woms(SAMPLE)
            return woms, run_sync(woms, db, apply=apply, export_text=woms.csv_export(), sleep=lambda _s: None)

        woms, dry = run(False)
        _, first = run(True)
        _, second = run(True)

    plan = first.plan
    record = {
        "source_records": len(woms.csv_records),
        "loaded": first.load.inserted,
        "skipped_cancelled": plan.count("skipped"),
        "rejected": plan.count("rejected"),
        "rejected_reasons": sorted(d.reason for d in plan.decisions if d.action == "rejected"),
        "missed_by_api": len(plan.flagged("csv_only")),
        "conflicts": len(plan.flagged("conflict")),
        "dry_run_writes": 0 if dry.load is None else dry.load.inserted + dry.load.updated,
        "rerun_writes": second.load.inserted + second.load.updated,
        "outcome": first.outcome,
    }
    OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(PROJECT)}: loaded {record['loaded']}, rejected {record['rejected']}, "
          f"missed by API {record['missed_by_api']}, re-run writes {record['rerun_writes']}")


if __name__ == "__main__":
    main()
