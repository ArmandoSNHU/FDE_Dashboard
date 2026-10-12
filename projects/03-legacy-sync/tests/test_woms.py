"""The mock WOMS must reproduce every documented quirk, deterministically.

If the mock stops misbehaving, the sync's tests stop proving anything, so each quirk
is pinned here before the sync is built against it.
"""

import csv
import io
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fde_sync.legacy import WomsUnavailable, build_woms

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "nyc311_sample.csv"


@pytest.fixture
def woms():
    return build_woms(SAMPLE)


def read_all_pages(woms, page_size=50):
    pages, offset = [], 0
    while True:
        page = woms.api_page(offset, page_size)
        pages.extend(page)
        if len(page) < page_size:
            return pages
        offset += page_size


def csv_rows(woms):
    return list(csv.DictReader(io.StringIO(woms.csv_export())))


def key(record):
    return f"{record['region']}:{record['wo_id']}"


def test_q1_wo_id_is_not_unique_across_regions(woms):
    by_id = Counter(r["wo_id"] for r in csv_rows(woms))
    assert any(count > 1 for count in by_id.values())
    assert len({key(r) for r in csv_rows(woms)}) == len(csv_rows(woms))


def test_q2_api_times_are_site_local_and_csv_times_are_utc(woms):
    csv_by_key = {key(r): r for r in csv_rows(woms)}
    offsets = set()
    for record in read_all_pages(woms):
        exported = csv_by_key.get(key(record))
        if exported is None or record["opened_at"].startswith("0000") or exported["opened_at"].startswith("0000"):
            continue
        local = datetime.strptime(record["opened_at"], "%Y-%m-%d %H:%M:%S")
        utc = datetime.strptime(exported["opened_at"], "%Y-%m-%dT%H:%M:%SZ")
        offsets.add((record["region"], utc - local))
    assert ("EAST", timedelta(hours=4)) in offsets  # New York in July: UTC-4
    assert ("CENTRAL", timedelta(hours=5)) in offsets  # Chicago in July: UTC-5
    assert all(r["opened_at"].endswith("Z") for r in csv_rows(woms) if not r["opened_at"].startswith("0000"))


def test_q3_status_codes_change_meaning_on_2024_07_01(woms):
    rows = csv_rows(woms)
    change = "2024-07-01T04:00:00Z"  # midnight in New York, where Northwind changed the codes
    before = {r["status"] for r in rows if r["opened_at"] < change}
    after = {r["status"] for r in rows if r["opened_at"] >= change}
    assert "D" in before and "X" not in before  # old codes: D done, C cancelled
    assert "X" in after and "D" not in after  # new codes: C closed, X cancelled
    assert "C" in before and "C" in after
    assert "H" in {r["status"] for r in rows}  # on hold: real, undocumented


def test_q4_records_created_during_a_read_cause_duplicates_and_misses(woms):
    pages = read_all_pages(woms)
    seen = Counter(key(r) for r in pages)
    exported = {key(r) for r in csv_rows(woms)}
    assert woms.late_arrivals > 0
    assert any(count > 1 for count in seen.values()), "expected duplicates at page boundaries"
    assert len(exported - set(seen)) == woms.late_arrivals


def test_q5_some_api_priorities_disagree_with_the_csv(woms):
    csv_by_key = {key(r): r for r in csv_rows(woms)}
    disagreements = [r for r in read_all_pages(woms) if csv_by_key[key(r)]["priority"] != r["priority"]]
    assert 0 < len(disagreements) < 50


def test_bad_records_are_present_for_the_sync_to_reject(woms):
    rows = csv_rows(woms)
    assert sum(r["status"] == "Z" for r in rows) == 2
    assert sum(r["opened_at"].startswith("0000") for r in rows) == 1


def test_an_injection_payload_sits_in_one_description(woms):
    assert sum("ignore previous instructions" in r["description"] for r in csv_rows(woms)) == 1


def test_the_same_seed_gives_identical_output():
    assert build_woms(SAMPLE).csv_export() == build_woms(SAMPLE).csv_export()
    assert build_woms(SAMPLE, seed=1).csv_export() != build_woms(SAMPLE).csv_export()


def test_listed_calls_fail_as_unavailable():
    woms = build_woms(SAMPLE, fail_calls={1})
    with pytest.raises(WomsUnavailable):
        woms.api_page(0, 50)
    assert len(woms.api_page(0, 50)) == 50  # the next call succeeds


def test_export_time_is_after_every_open_time(woms):
    export = datetime(2024, 7, 15, 6, 0, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert all(r["opened_at"] < export for r in csv_rows(woms))
