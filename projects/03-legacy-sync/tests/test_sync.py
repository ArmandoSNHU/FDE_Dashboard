"""A whole run against the mock WOMS, the way the customer will run it."""

import hashlib

from fde_sync.cli import main
from fde_sync.legacy import build_woms
from fde_sync.report import render_report
from fde_sync.sync import run_sync

from conftest import SAMPLE

NOW = "2024-07-15T06:05:00Z"


def no_sleep(_seconds):
    pass


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync(db, *, apply, fail_calls=None, export="mock"):
    woms = build_woms(SAMPLE, fail_calls=fail_calls)
    text = woms.csv_export() if export == "mock" else export
    return run_sync(woms, db, apply=apply, export_text=text, started_at=NOW, sleep=no_sleep)


def test_a_dry_run_writes_nothing_even_to_an_unmigrated_db(ops_db):
    before = fingerprint(ops_db)
    result = sync(ops_db, apply=False)
    assert result.outcome == "ok" and result.load is None
    assert fingerprint(ops_db) == before


def test_the_plan_reflects_every_quirk_in_the_real_sample(ops_db):
    result = sync(ops_db, apply=False)
    plan = result.plan
    assert plan.count("rejected") == 3  # two unknown statuses, one unparseable date
    assert len(plan.flagged("csv_only")) == build_woms(SAMPLE).late_arrivals  # Q4
    assert len(plan.flagged("conflict:priority")) > 0  # Q5
    assert plan.count("held") == 0
    assert plan.count("new") + plan.count("skipped") + plan.count("rejected") == 500


def test_apply_loads_and_a_second_apply_writes_nothing(ops_db):
    first = sync(ops_db, apply=True)
    assert first.load.inserted == first.plan.count("new") > 400
    second = sync(ops_db, apply=True)
    assert (second.load.inserted, second.load.updated) == (0, 0)
    assert second.plan.count("unchanged") == first.plan.count("new")


def test_a_dry_run_after_an_apply_still_writes_nothing(ops_db):
    sync(ops_db, apply=True)
    before = fingerprint(ops_db)
    assert sync(ops_db, apply=False).plan.count("unchanged") > 400
    assert fingerprint(ops_db) == before


def test_an_api_outage_is_a_partial_run_that_still_loads_everything_from_the_export(ops_db):
    result = sync(ops_db, apply=True, fail_calls=set(range(2, 20)))
    assert result.outcome == "partial" and not result.api_complete
    assert result.load.inserted == sync(ops_db, apply=False).plan.count("unchanged")


def test_a_missing_export_fails_before_any_write(ops_db):
    before = fingerprint(ops_db)
    result = sync(ops_db, apply=True, export=None)
    assert result.outcome == "failed" and "export" in result.error
    assert fingerprint(ops_db) == before


def test_an_empty_export_is_a_valid_run_with_nothing_to_do(ops_db):
    header = "region,wo_id,opened_at,status,priority,trade,site,description\n"
    result = sync(ops_db, apply=True, export=header)
    assert result.outcome == "ok" and result.load.inserted == 0
    assert result.plan.count("held") > 0  # the API still has records; they wait for an export


def test_the_report_names_every_reject_and_conflict_in_plain_ascii(ops_db):
    result = sync(ops_db, apply=False)
    report = render_report(result)
    report.encode("ascii")
    for decision in result.plan.decisions:
        if decision.action == "rejected":
            assert decision.reason in report
    for decision in result.plan.flagged("conflict"):
        assert decision.key in report


def test_cli_defaults_to_dry_run_and_reports_its_mode(ops_db, capsys):
    assert main(["--db", str(ops_db)]) == 0
    out = capsys.readouterr().out
    assert "dry-run" in out
    out.encode("ascii")


def test_cli_apply_and_a_missing_db(ops_db, tmp_path, capsys):
    assert main(["--db", str(ops_db), "--apply"]) == 0
    assert main(["--db", str(tmp_path / "missing.db")]) == 1
    assert "ops DB not found" in capsys.readouterr().err


def test_cli_writes_the_report_where_asked(ops_db, tmp_path):
    target = tmp_path / "report.md"
    main(["--db", str(ops_db), "--report", str(target)])
    assert target.read_text(encoding="ascii").startswith("# Northwind sync report")
