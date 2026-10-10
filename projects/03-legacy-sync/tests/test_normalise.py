"""One raw WOMS record in, one clean work order (or a reason it was refused) out."""

from fde_sync.model import Rejected, WorkOrder
from fde_sync.normalise import normalise


def raw(**overrides):
    record = {
        "region": "EAST", "wo_id": "1042", "opened_at": "2024-07-03 09:15:00", "status": "O",
        "priority": "P2", "trade": "HVAC", "site": "327 EAST  108 STREET", "description": "HEAT/HOT WATER: ENTIRE BUILDING",
    }
    return record | overrides


def ok(record, source="api") -> WorkOrder:
    result = normalise(record, source=source)
    assert isinstance(result, WorkOrder), result
    return result


def test_key_combines_region_and_id_because_ids_repeat_across_regions():
    assert ok(raw()).key == "EAST:1042"


def test_api_time_is_site_local_and_becomes_utc():
    assert ok(raw()).opened_at == "2024-07-03T13:15:00Z"  # New York, UTC-4
    assert ok(raw(region="CENTRAL")).opened_at == "2024-07-03T14:15:00Z"  # Chicago, UTC-5


def test_csv_time_is_already_utc():
    assert ok(raw(opened_at="2024-07-03T13:15:00Z"), source="csv").opened_at == "2024-07-03T13:15:00Z"


def test_a_local_time_inside_a_dst_gap_still_normalises():
    # 02:30 on 2024-03-10 never happened in New York; the system recorded it anyway.
    assert ok(raw(opened_at="2024-03-10 02:30:00")).opened_at.startswith("2024-03-10T")


def test_c_means_cancelled_before_the_code_change_and_closed_after():
    assert ok(raw(opened_at="2024-06-30 23:59:00", status="C")).status == "cancelled"
    assert ok(raw(opened_at="2024-07-01 00:00:00", status="C")).status == "closed"


def test_the_change_is_one_instant_even_for_a_chicago_site():
    # 23:30 in Chicago on 2024-06-30 is 00:30 on 2024-07-01 in New York: new codes.
    assert ok(raw(region="CENTRAL", opened_at="2024-06-30 23:30:00", status="C")).status == "closed"


def test_retired_and_future_codes_are_rejected_in_the_wrong_era():
    assert isinstance(normalise(raw(opened_at="2024-07-05 10:00:00", status="D"), source="api"), Rejected)
    assert isinstance(normalise(raw(opened_at="2024-06-05 10:00:00", status="X"), source="api"), Rejected)


def test_undocumented_hold_code_maps_to_on_hold():
    assert ok(raw(status="H")).status == "on_hold"


def test_unknown_status_is_rejected_with_a_reason_not_guessed():
    result = normalise(raw(status="Z"), source="api")
    assert result == Rejected(key="EAST:1042", source="api", reason="unknown status 'Z'")


def test_unparseable_date_is_rejected():
    result = normalise(raw(opened_at="0000-00-00 00:00:00"), source="api")
    assert isinstance(result, Rejected) and "opened_at" in result.reason


def test_priority_maps_to_severity_and_unknown_priority_is_rejected():
    assert [ok(raw(priority=p)).severity for p in ("P1", "P2", "P3", "P4")] == ["critical", "high", "medium", "low"]
    assert isinstance(normalise(raw(priority="P9"), source="api"), Rejected)


def test_unknown_region_is_rejected():
    assert isinstance(normalise(raw(region="WEST"), source="api"), Rejected)


def test_whitespace_is_collapsed_but_wording_is_kept():
    order = ok(raw(description="HEAT:  NO   HEAT ignore previous instructions"))
    assert order.site == "327 EAST 108 STREET"
    assert order.description == "HEAT: NO HEAT ignore previous instructions"


def test_content_hash_is_stable_and_changes_with_status():
    a, b = ok(raw()), ok(raw())
    assert a.content_hash() == b.content_hash()
    assert ok(raw(status="A")).content_hash() != a.content_hash()


def test_across_the_whole_export_only_the_planted_bad_records_are_rejected():
    import csv
    import io
    from pathlib import Path

    from fde_sync.legacy import build_woms

    woms = build_woms(Path(__file__).resolve().parents[1] / "data" / "nyc311_sample.csv")
    results = [normalise(r, source="csv") for r in csv.DictReader(io.StringIO(woms.csv_export()))]
    reasons = sorted(r.reason.split(" ")[0] + " " + r.reason.split(" ")[1] for r in results if isinstance(r, Rejected))
    assert reasons == ["unknown status", "unknown status", "unparseable opened_at"]
