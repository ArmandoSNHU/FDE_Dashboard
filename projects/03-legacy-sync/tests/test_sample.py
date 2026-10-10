"""The committed sample is real 311 data; these checks keep it fit for the quirks built on it."""

import csv
from pathlib import Path

from fde_sync.trades import REGION_BY_BOROUGH, TRADE_BY_COMPLAINT

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "nyc311_sample.csv"
COLUMNS = [
    "unique_key", "created_date", "closed_date", "complaint_type",
    "descriptor", "status", "incident_address", "borough",
]


def rows() -> list[dict[str, str]]:
    with SAMPLE.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == COLUMNS
        return list(reader)


def test_sample_is_large_enough_to_be_interesting():
    assert len(rows()) >= 400


def test_every_borough_appears_so_every_region_and_time_zone_is_exercised():
    assert {r["borough"] for r in rows()} == set(REGION_BY_BOROUGH)


def test_dates_span_the_status_code_change_on_2024_07_01():
    dates = {r["created_date"][:10] for r in rows()}
    assert min(dates) < "2024-07-01" <= max(dates)


def test_every_complaint_type_maps_to_a_trade():
    assert {r["complaint_type"] for r in rows()} <= set(TRADE_BY_COMPLAINT)


def test_unique_keys_are_unique():
    keys = [r["unique_key"] for r in rows()]
    assert len(keys) == len(set(keys))
