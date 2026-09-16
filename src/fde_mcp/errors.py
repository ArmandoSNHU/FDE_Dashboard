"""Shared error model.

Every connector translates its native failures (HTTP status, sqlite3 exceptions,
network timeouts) into a `SourceError` with one of a small, fixed set of kinds.
The server guard turns that into a structured tool result, so an MCP client always
gets `{"ok": false, "error": {...}}` it can reason about — never a stack trace.

See README "Failure & degradation" for the per-source mapping.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorKind(StrEnum):
    NOT_CONFIGURED = "not_configured"  # credentials / path missing; fix config, don't retry
    AUTH = "auth"  # credentials rejected or insufficient scope
    RATE_LIMITED = "rate_limited"  # upstream throttle; honour retry_after_s
    UNAVAILABLE = "unavailable"  # network down, 5xx, DB locked
    NOT_FOUND = "not_found"
    INVALID_INPUT = "invalid_input"
    ACCESS_DENIED = "access_denied"  # our own policy layer said no
    NOT_IMPLEMENTED = "not_implemented"  # skeleton placeholder
    INTERNAL = "internal"  # unexpected bug; details logged server-side only


class SourceError(Exception):
    """A classified failure from one data source."""

    def __init__(
        self,
        source: str,
        kind: ErrorKind,
        message: str,
        *,
        retryable: bool = False,
        retry_after_s: float | None = None,
    ) -> None:
        super().__init__(f"[{source}:{kind}] {message}")
        self.source = source
        self.kind = kind
        self.message = message
        self.retryable = retryable
        self.retry_after_s = retry_after_s

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "kind": str(self.kind),
            "message": self.message,
            "retryable": self.retryable,
            "retry_after_s": self.retry_after_s,
        }


def error_result(err: SourceError) -> dict[str, Any]:
    return {"ok": False, "error": err.to_dict()}


def ok_result(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}
