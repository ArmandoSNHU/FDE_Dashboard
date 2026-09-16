"""Connector contract.

A connector:
- is constructed cheaply and never does I/O in __init__ (a dead source must not block startup);
- reports `status()` without network calls and without exposing secrets;
- raises only `SourceError` from its public async methods (anything else is a bug,
  which the server guard reports as `internal`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from fde_mcp.errors import ErrorKind, SourceError


@dataclass(frozen=True)
class ConnectorStatus:
    configured: bool
    detail: str


class Connector(ABC):
    name: str

    @abstractmethod
    def status(self) -> ConnectorStatus: ...

    def _require_configured(self) -> None:
        status = self.status()
        if not status.configured:
            raise SourceError(self.name, ErrorKind.NOT_CONFIGURED, status.detail)
