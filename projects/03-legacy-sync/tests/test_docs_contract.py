"""Docs-as-contract: the engagement documents may only cite tests and numbers that exist."""

import json
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
DOCS = sorted([*(PROJECT / "engagement").rglob("*.md"), PROJECT / "README.md"])


def test_every_test_a_document_cites_exists():
    defined = set()
    for path in (PROJECT / "tests").glob("test_*.py"):
        defined |= set(re.findall(r"^(?:async )?def (test_\w+)", path.read_text(encoding="utf-8"), flags=re.M))
    for doc in DOCS:
        cited = set(re.findall(r"\b(test_\w+)\b", doc.read_text(encoding="utf-8"))) - {"test_"}
        cited = {name for name in cited if not (PROJECT / "tests" / f"{name}.py").exists()}  # module names are fine
        missing = cited - defined
        assert not missing, f"{doc.relative_to(PROJECT)} cites tests that don't exist: {sorted(missing)}"


def test_the_engagement_outcome_table_matches_the_recorded_run():
    run = json.loads((PROJECT / "results" / "sync-run.json").read_text(encoding="utf-8"))
    table = (PROJECT / "engagement" / "README.md").read_text(encoding="utf-8")
    expected = {
        "Work orders in the export": run["source_records"],
        "Loaded into the on-call platform": run["loaded"],
        "Skipped (cancelled before ever being loaded)": run["skipped_cancelled"],
        "Rejected, with a reason, for Northwind to fix": run["rejected"],
        "Missed by the API, recovered from the export": run["missed_by_api"],
        "API and export disagreed (export used, each listed)": run["conflicts"],
        "Rows written by a second run": run["rerun_writes"],
    }
    for label, value in expected.items():
        assert f"| {label} | {value} |" in table, f"engagement/README.md: '{label}' should be {value}"
