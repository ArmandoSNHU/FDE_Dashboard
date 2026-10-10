"""Turn one raw WOMS record into a WorkOrder, or a Rejected with the reason.

The rule for anything we don't understand is to refuse it, with a reason a person can act
on. Loading a guessed value would put a wrong ticket in front of the on-call engineer, and
nobody would know it was a guess.

Each rule below was learned in discovery (engagement/discovery-notes.md), not from the API
guide, which is wrong about IDs and time zones.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fde_sync.model import Rejected, Severity, Source, Status, WorkOrder
from fde_sync.trades import TIMEZONE_BY_REGION

# Q3: Northwind changed its status codes at midnight New York time on 2024-07-01.
CODE_CHANGE_AT = datetime(2024, 7, 1, tzinfo=ZoneInfo("America/New_York"))

STATUS_BEFORE: dict[str, Status] = {"O": "open", "A": "assigned", "H": "on_hold", "D": "closed", "C": "cancelled"}
STATUS_AFTER: dict[str, Status] = {"O": "open", "A": "assigned", "H": "on_hold", "C": "closed", "X": "cancelled"}
SEVERITY: dict[str, Severity] = {"P1": "critical", "P2": "high", "P3": "medium", "P4": "low"}

API_TIME = "%Y-%m-%d %H:%M:%S"  # site-local, no offset (Q2)
CSV_TIME = "%Y-%m-%dT%H:%M:%SZ"  # UTC


def normalise(raw: dict[str, str], *, source: Source) -> WorkOrder | Rejected:
    region = (raw.get("region") or "").strip()
    wo_id = (raw.get("wo_id") or "").strip()
    key = f"{region}:{wo_id}" if region and wo_id else None

    def reject(reason: str) -> Rejected:
        return Rejected(key=key, source=source, reason=reason)

    if region not in TIMEZONE_BY_REGION:
        return reject(f"unknown region {region!r}")
    if not wo_id.isdigit():
        return reject(f"work order id is not a number: {wo_id!r}")

    opened = _opened_utc(raw.get("opened_at") or "", region, source)
    if opened is None:
        return reject(f"unparseable opened_at {raw.get('opened_at')!r}")

    codes = STATUS_BEFORE if opened < CODE_CHANGE_AT else STATUS_AFTER
    code = (raw.get("status") or "").strip()
    if code not in codes:
        return reject(f"unknown status {code!r}")

    severity = SEVERITY.get((raw.get("priority") or "").strip())
    if severity is None:
        return reject(f"unknown priority {raw.get('priority')!r}")

    return WorkOrder(
        key=key,
        opened_at=opened.strftime(CSV_TIME),
        status=codes[code],
        severity=severity,
        trade=_squash(raw.get("trade")),
        site=_squash(raw.get("site")),
        description=_squash(raw.get("description")),
    )


def _opened_utc(value: str, region: str, source: Source) -> datetime | None:
    try:
        if source == "csv":
            return datetime.strptime(value, CSV_TIME).replace(tzinfo=timezone.utc)
        # A local time in a DST gap or overlap still converts: zoneinfo picks fold=0,
        # which is at worst an hour out. Refusing the record would lose a real ticket.
        local = datetime.strptime(value, API_TIME).replace(tzinfo=ZoneInfo(TIMEZONE_BY_REGION[region]))
        return local.astimezone(timezone.utc)
    except ValueError:
        return None


def _squash(value: str | None) -> str:
    """Collapse runs of whitespace. Wording is kept exactly; this is not a sanitiser."""
    return " ".join((value or "").split())
