"""Local SQLite ops-database connector.

Auth: there is no network auth — the boundary is the filesystem. FDE_DB_PATH points
at an existing file; OS file permissions decide who can read it. Inside the process
we add two rules:
- read tools open the file with `mode=ro` (URI), so a read path can never write;
- write tools open a separate read-write connection, and only exist for roles with `db:write`.
No tool accepts raw SQL; every query is a fixed, parameterised statement.

Queries run in a worker thread (`asyncio.to_thread`): sqlite3 is blocking, and a slow
disk or a locked file must not stall the server's event loop for every other source.

Schema: db/schema.sql (deployments, incidents, alert_outbox).

Failure mapping:
    path unset / file missing           -> NOT_CONFIGURED (we never auto-create on the read path)
    sqlite3.OperationalError "locked"   -> UNAVAILABLE    (retryable; busy_timeout BUSY_TIMEOUT_MS first)
    sqlite3.OperationalError other      -> UNAVAILABLE    (not retryable: schema mismatch, readonly, IO)
    sqlite3.DatabaseError (corrupt)     -> UNAVAILABLE    (not retryable)
    bad customer / severity / limit     -> INVALID_INPUT  (validated before any query)
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from fde_mcp.connectors.base import Connector, ConnectorStatus
from fde_mcp.errors import ErrorKind, SourceError

BUSY_TIMEOUT_MS = 2000
MAX_LIMIT = 100
SEVERITIES = ("low", "medium", "high", "critical")

T = TypeVar("T")

RECENT_DEPLOYMENTS = """
    SELECT id, customer, service, version, environment, deployed_at
      FROM deployments
     WHERE customer = ?
     ORDER BY deployed_at DESC, id DESC
     LIMIT ?
"""


class SQLiteConnector(Connector):
    name = "sqlite"

    def __init__(self, db_path: Path | None, *, busy_timeout_ms: int = BUSY_TIMEOUT_MS) -> None:
        self._db_path = Path(db_path) if db_path else None
        self._busy_timeout_ms = busy_timeout_ms

    def status(self) -> ConnectorStatus:
        if self._db_path is None:
            return ConnectorStatus(False, "FDE_DB_PATH is not set")
        if not self._db_path.is_file():
            return ConnectorStatus(False, f"database file not found: {self._db_path.name}")
        return ConnectorStatus(True, f"database file present: {self._db_path.name}")

    async def recent_deployments(self, customer: str, limit: int = 20) -> list[dict[str, Any]]:
        """Most recent deployments for one customer, newest first."""
        self._require_configured()
        customer = self._require_text(customer, "customer")
        limit = self._validate_limit(limit)

        def query() -> list[dict[str, Any]]:
            with self._connect(readonly=True) as conn:
                return [dict(row) for row in conn.execute(RECENT_DEPLOYMENTS, (customer, limit))]

        return await self._run(query)

    async def log_incident(self, customer: str, summary: str, severity: str) -> dict[str, Any]:
        """Insert an incident row and return its id + created_at."""
        self._require_configured()
        customer = self._require_text(customer, "customer")
        summary = self._require_text(summary, "summary")
        if severity not in SEVERITIES:
            raise SourceError(
                self.name, ErrorKind.INVALID_INPUT, f"severity must be one of {', '.join(SEVERITIES)}; got {severity!r}"
            )

        def write() -> dict[str, Any]:
            with self._connect(readonly=False) as conn:
                cursor = conn.execute(
                    "INSERT INTO incidents (customer, summary, severity) VALUES (?, ?, ?) RETURNING id, created_at",
                    (customer, summary, severity),
                )
                row = cursor.fetchone()
                conn.commit()
                return {"id": row["id"], "created_at": row["created_at"], "severity": severity}

        return await self._run(write)

    async def enqueue_alert(self, message: str, severity: str, reason: str) -> int:
        """Degradation path for Telegram: persist an undelivered alert to alert_outbox."""
        self._require_configured()
        message = self._require_text(message, "message")

        def write() -> int:
            with self._connect(readonly=False) as conn:
                cursor = conn.execute(
                    "INSERT INTO alert_outbox (message, severity, reason) VALUES (?, ?, ?) RETURNING id",
                    (message, severity, reason),
                )
                row_id = int(cursor.fetchone()["id"])
                conn.commit()
                return row_id

        return await self._run(write)

    # --- plumbing ------------------------------------------------------------

    def _connect(self, *, readonly: bool) -> sqlite3.Connection:
        """Open the database. `readonly` uses SQLite's URI mode=ro, enforced by SQLite itself."""
        assert self._db_path is not None  # guarded by _require_configured
        uri = self._db_path.resolve().as_uri()
        conn = sqlite3.connect(f"{uri}?mode=ro" if readonly else uri, uri=True, timeout=self._busy_timeout_ms / 1000)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
        return conn

    async def _run(self, work: Callable[[], T]) -> T:
        """Run blocking sqlite3 work off the event loop, mapping its errors to SourceError."""
        try:
            return await asyncio.to_thread(work)
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if "locked" in message or "busy" in message:
                raise SourceError(
                    self.name, ErrorKind.UNAVAILABLE, "database is locked by another writer", retryable=True
                ) from exc
            raise SourceError(self.name, ErrorKind.UNAVAILABLE, f"database unusable: {exc}") from exc
        except sqlite3.DatabaseError as exc:
            # Includes DatabaseError("file is not a database") for a corrupt file.
            raise SourceError(self.name, ErrorKind.UNAVAILABLE, f"database error: {exc}") from exc

    def _require_text(self, value: Any, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise SourceError(self.name, ErrorKind.INVALID_INPUT, f"{field} must be a non-empty string")
        return value.strip()

    def _validate_limit(self, limit: Any) -> int:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
            raise SourceError(self.name, ErrorKind.INVALID_INPUT, f"limit must be an integer 1..{MAX_LIMIT}; got {limit!r}")
        return limit
