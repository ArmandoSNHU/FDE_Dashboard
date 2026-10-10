"""Pulling both sources: the API is flaky and pages badly; the CSV is plain."""

from pathlib import Path

from fde_sync.extract import fetch_api, read_csv
from fde_sync.legacy import build_woms

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "nyc311_sample.csv"


class FakeSleep:
    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)


def test_a_clean_read_returns_every_page_and_is_complete():
    woms = build_woms(SAMPLE)
    result = fetch_api(woms, page_size=50, sleep=FakeSleep())
    assert result.complete and result.errors == []
    # Q4: the read sees duplicates and misses the late arrivals; extract reports what it got.
    keys = {f"{r['region']}:{r['wo_id']}" for r in result.records}
    assert len(keys) == 500 - woms.late_arrivals


def test_a_transient_failure_is_retried_with_backoff():
    sleep = FakeSleep()
    result = fetch_api(build_woms(SAMPLE, fail_calls={2, 3}), page_size=50, sleep=sleep)
    assert result.complete
    assert sleep.calls == [0.5, 1.0]
    assert len(result.errors) == 2  # each failure is recorded even when a retry recovers


def test_giving_up_keeps_what_was_fetched_and_says_so():
    sleep = FakeSleep()
    result = fetch_api(build_woms(SAMPLE, fail_calls={2, 3, 4, 5}), page_size=50, max_retries=3, sleep=sleep)
    assert not result.complete
    assert len(result.records) == 50  # the first page made it
    assert sleep.calls == [0.5, 1.0, 2.0]
    assert "gave up" in result.errors[-1]


def test_paging_stops_on_a_short_page():
    woms = build_woms(SAMPLE)
    fetch_api(woms, page_size=200, sleep=FakeSleep())
    assert woms.calls == 3  # 200 + 200 + a short page of the rest


def test_read_csv_returns_rows_and_an_empty_export_is_no_rows():
    woms = build_woms(SAMPLE)
    assert len(read_csv(woms.csv_export())) == 500
    assert read_csv("") == []
    assert read_csv("region,wo_id,opened_at,status,priority,trade,site,description\n") == []
