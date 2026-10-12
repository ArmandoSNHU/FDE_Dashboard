"""The two things a raw record can become: a clean work order, or a documented refusal."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal

Status = Literal["open", "assigned", "on_hold", "closed", "cancelled"]
Severity = Literal["low", "medium", "high", "critical"]
Source = Literal["api", "csv"]


@dataclass(frozen=True)
class WorkOrder:
    key: str  # "<region>:<wo_id>": wo_id alone repeats across regions (Q1)
    opened_at: str  # UTC, "YYYY-MM-DDTHH:MM:SSZ"
    status: Status
    severity: Severity
    trade: str
    site: str
    description: str

    def content_hash(self) -> str:
        """Fingerprint of everything we store, so a re-run can tell 'unchanged' from 'changed'."""
        canonical = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Rejected:
    key: str | None
    source: Source
    reason: str
