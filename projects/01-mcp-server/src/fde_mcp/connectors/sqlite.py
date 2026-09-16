"""Local SQLite ops-database connector.

Auth: there is no network auth — the boundary is the filesystem. FDE_DB_PATH points
at an existing file; OS file permissions decide who can read it. Inside the process
we add two rules:
- read tools open the file with `mode=ro` (URI), so a read path can never write;
- write tools open a separate read-write connection, and only exist for roles with `db:write`.
No tool accepts raw SQL; every query is a fixed, parameterised statement.

Schema: db/schema.sql (deployments, incidents, alert_outbox).

Failure mapping:
    path unset / file missing           -> NOT_CONFIGURED (we never auto-create on the read path)
    sqlite3.OperationalError "locked"   -> UNAVAILABLE    (retryable; busy_timeout BUSY_TIMEOUT_MS first)
    sqlite3.OperationalError other      -> UNAVAILABLE    (not retryable: schema mismatch, readonly, IO)
    sqlite3.DatabaseError (corrupt)     -> UNAVAILABLE    (not retryable)
    bad customer / severity / limit     -> INVALID_INPUT  (validated before any query)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fde_mcp.connectors.base import Connector, ConnectorStatus

BUSY_TIMEOUT_MS = 2000
MAX_LIMIT = 100
SEVERITIES = ("low", "medium", "high", "critical")


class SQLiteConnector(Connector):
    name = "sqlite"

    def __init__(self, db_path: Path | None) -> None:
        self._db_path = Path(db_path) if db_path else None

    def status(self) -> ConnectorStatus:
        if self._db_path is None:
            return ConnectorStatus(False, "FDE_DB_PATH is not set")
        if not self._db_path.is_file():
            return ConnectorStatus(False, f"database file not found: {self._db_path.name}")
        return ConnectorStatus(True, f"database file present: {self._db_path.name}")

    async def recent_deployments(self, customer: str, limit: int = 20) -> list[dict[str, Any]]:
        """Most recent deployments for one customer, newest first."""
        self._require_configured()
        # TODO: validate limit in 1..MAX_LIMIT; read-only connection; parameterised SELECT.
        raise NotImplementedError

    async def log_incident(self, customer: str, summary: str, severity: str) -> dict[str, Any]:
        """Insert an incident row and return its id + created_at."""
        self._require_configured()
        # TODO: validate severity in SEVERITIES; read-write connection; parameterised INSERT.
        raise NotImplementedError

    async def enqueue_alert(self, message: str, severity: str, reason: str) -> int:
        """Degradation path for Telegram: persist an undelivered alert to alert_outbox."""
        self._require_configured()
        # TODO: INSERT into alert_outbox; return row id.
        raise NotImplementedError
