"""Deciding, record by record, what a run should do. Nothing is written here."""

import random

from fde_sync.model import Rejected, WorkOrder
from fde_sync.reconcile import reconcile
from fde_sync.store import LedgerRow


def order(key="EAST:1001", status="open", severity="high", description="PLUMBING: LEAK"):
    return WorkOrder(key=key, opened_at="2024-07-03T13:15:00Z", status=status, severity=severity,
                     trade="PLUMBING", site="1 MAIN ST", description=description)


def only(plan):
    assert len(plan.decisions) == 1, plan.decisions
    return plan.decisions[0]


def test_a_record_we_have_never_seen_is_new():
    assert only(reconcile([order()], [order()], {})).action == "new"


def test_a_record_already_loaded_with_the_same_content_is_unchanged():
    ledger = {"EAST:1001": LedgerRow(7, order().content_hash())}
    assert only(reconcile([order()], [order()], ledger)).action == "unchanged"


def test_a_loaded_record_whose_content_moved_is_changed_and_keeps_its_incident():
    ledger = {"EAST:1001": LedgerRow(7, order().content_hash())}
    decision = only(reconcile([], [order(status="closed")], ledger))
    assert (decision.action, decision.incident_id) == ("changed", 7)


def test_the_csv_is_the_source_of_truth_when_the_api_disagrees():
    decision = only(reconcile([order(severity="low", status="assigned")], [order()], {}))
    assert decision.order == order()
    assert set(decision.flags) == {"conflict:priority", "conflict:status"}


def test_a_record_the_api_missed_is_loaded_from_the_csv_and_flagged():
    decision = only(reconcile([], [order()], {}))
    assert (decision.action, decision.flags) == ("new", ("csv_only",))


def test_api_duplicates_collapse_on_the_key():
    assert only(reconcile([order(), order()], [order()], {})).action == "new"


def test_a_record_only_the_api_has_is_held_until_it_is_exported():
    decision = only(reconcile([order()], [], {}))
    assert decision.action == "held" and decision.order is None


def test_a_cancelled_order_is_skipped_unless_we_already_loaded_it():
    assert only(reconcile([], [order(status="cancelled")], {})).action == "skipped"
    ledger = {"EAST:1001": LedgerRow(7, order().content_hash())}
    assert only(reconcile([], [order(status="cancelled")], ledger)).action == "changed"


def test_a_csv_reject_is_reported_with_its_reason():
    bad = Rejected(key="EAST:1001", source="csv", reason="unknown status 'Z'")
    decision = only(reconcile([order()], [bad], {}))
    assert (decision.action, decision.reason) == ("rejected", "unknown status 'Z'")


def test_a_key_repeated_in_the_export_is_rejected_not_overwritten():
    decisions = reconcile([], [order(), order(description="OTHER")], {}).decisions
    assert [d.action for d in decisions] == ["new", "rejected"]
    assert decisions[1].reason == "duplicate key in export"


def test_input_order_does_not_change_the_plan():
    api = [order(f"EAST:{i}") for i in range(30)] + [order("METRO:5", severity="low")]
    csv = [order(f"EAST:{i}") for i in range(2, 32)] + [order("METRO:5")]
    expected = reconcile(api, csv, {})
    rng = random.Random(3)
    for _ in range(5):
        rng.shuffle(api)
        rng.shuffle(csv)
        assert reconcile(api, csv, {}) == expected
