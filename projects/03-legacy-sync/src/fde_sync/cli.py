"""fde-sync: load Northwind's work orders into the ops database.

    fde-sync --db data/ops.db                 # dry run: show what would change, write nothing
    fde-sync --db data/ops.db --apply         # write
    fde-sync --db data/ops.db --report r.md   # also save the data-quality report

Exit codes: 0 ok, 3 partial (the API read was incomplete; the export still loaded), 1 failed.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from fde_sync.legacy import build_woms
from fde_sync.report import render_report
from fde_sync.sync import run_sync

DEFAULT_SAMPLE = Path(__file__).resolve().parents[2] / "data" / "nyc311_sample.csv"
EXIT = {"ok": 0, "partial": 3, "failed": 1}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fde-sync", description="Sync Northwind WOMS into the ops DB.")
    parser.add_argument("--db", type=Path, default=os.environ.get("FDE_DB_PATH"), help="ops DB (default: FDE_DB_PATH)")
    parser.add_argument("--apply", action="store_true", help="write changes (default is a dry run)")
    parser.add_argument("--export", type=Path, help="nightly CSV export (default: the mock WOMS export)")
    parser.add_argument("--report", type=Path, help="write the data-quality report to this file")
    args = parser.parse_args(argv)
    if args.db is None:
        parser.error("--db is required when FDE_DB_PATH is not set")

    woms = build_woms(DEFAULT_SAMPLE)
    if args.export is None:
        export_text: str | None = woms.csv_export()
    else:
        export_text = args.export.read_text(encoding="utf-8") if args.export.is_file() else None

    result = run_sync(woms, args.db, apply=args.apply, export_text=export_text)
    report = render_report(result)
    if args.report:
        args.report.write_text(report, encoding="ascii")

    if result.plan is not None:
        counts = ", ".join(f"{a} {result.plan.count(a)}" for a in ("new", "changed", "unchanged", "skipped", "rejected"))
        print(f"{result.mode}: {result.outcome} - {counts}")
    if result.error:
        print(f"error: {result.error}", file=sys.stderr)
    return EXIT[result.outcome]


if __name__ == "__main__":
    raise SystemExit(main())
