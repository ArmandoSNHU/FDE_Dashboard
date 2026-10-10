"""Decide what a run should do with each record. Pure: reads its inputs, writes nothing.

The CSV export is the source of truth (ADR-0003). The API is used to *check* it: a record
the API missed is still loaded (flagged csv_only), a field the two disagree on is flagged
as a conflict for a person to look at, and a record only the API has waits for the next
export rather than being loaded from the less reliable source.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fde_sync.model import Rejected, WorkOrder
from fde_sync.store import LedgerRow

Action = Literal["new", "changed", "unchanged", "skipped", "rejected", "held"]


@dataclass(frozen=True)
class Decision:
    key: str
    action: Action
    order: WorkOrder | None = None
    flags: tuple[str, ...] = ()
    reason: str = ""
    incident_id: int | None = None


@dataclass(frozen=True)
class Plan:
    decisions: tuple[Decision, ...]

    def count(self, action: Action) -> int:
        return sum(d.action == action for d in self.decisions)

    def flagged(self, prefix: str) -> list[Decision]:
        return [d for d in self.decisions if any(f.startswith(prefix) for f in d.flags)]


def reconcile(
    api: list[WorkOrder | Rejected],
    csv: list[WorkOrder | Rejected],
    ledger: dict[str, LedgerRow],
) -> Plan:
    api_orders = {o.key: o for o in api if isinstance(o, WorkOrder)}  # Q4 duplicates collapse here
    api_keys = {o.key for o in api if o.key}
    decisions: list[Decision] = []
    seen: set[str] = set()

    for i, record in enumerate(_stable(csv)):
        if isinstance(record, Rejected):
            decisions.append(Decision(record.key or f"csv-row-{i}", "rejected", reason=record.reason))
            continue
        if record.key in seen:
            decisions.append(Decision(record.key, "rejected", reason="duplicate key in export"))
            continue
        seen.add(record.key)
        decisions.append(_decide(record, api_orders.get(record.key), ledger.get(record.key)))

    for key in sorted(api_keys - seen - {d.key for d in decisions}):
        decisions.append(Decision(key, "held", reason="in the API but not yet in an export"))

    return Plan(tuple(decisions))


def _decide(order: WorkOrder, api_order: WorkOrder | None, loaded: LedgerRow | None) -> Decision:
    flags: list[str] = []
    if api_order is None:
        flags.append("csv_only")
    else:
        if api_order.severity != order.severity:
            flags.append("conflict:priority")
        if api_order.status != order.status:
            flags.append("conflict:status")
    flags_t = tuple(flags)

    if loaded is None:
        if order.status == "cancelled":
            return Decision(order.key, "skipped", order, flags_t, reason="cancelled before it was ever loaded")
        return Decision(order.key, "new", order, flags_t)
    if loaded.content_hash == order.content_hash():
        return Decision(order.key, "unchanged", order, flags_t, incident_id=loaded.incident_id)
    return Decision(order.key, "changed", order, flags_t, incident_id=loaded.incident_id)


def _stable(records: list[WorkOrder | Rejected]) -> list[WorkOrder | Rejected]:
    """Order records so the plan doesn't depend on the order the source happened to send them in."""
    return sorted(records, key=lambda r: (r.key or "", isinstance(r, Rejected), repr(r)))
