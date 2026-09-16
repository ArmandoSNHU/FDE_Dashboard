"""The single source of truth for the tool surface.

Each tool declares the scope it needs and the source it touches. The server uses this
to decide what to register for a role; tests use it to keep the README honest.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fde_mcp.connectors import Connector, GitHubConnector, SQLiteConnector, TelegramConnector
from fde_mcp.errors import ErrorKind, SourceError
from fde_mcp.untrusted import PROVENANCE_NOTE

# Telegram failures worth parking in the outbox: the message may still be deliverable later.
QUEUEABLE = frozenset({ErrorKind.RATE_LIMITED, ErrorKind.UNAVAILABLE})


@dataclass(frozen=True)
class ToolSpec:
    name: str
    scope: str
    source: str  # "github" | "sqlite" | "telegram" | "server"
    description: str
    read_only: bool


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec("server_health", "health:read", "server", "Per-source configuration status and the active role.", True),
    ToolSpec("github_list_open_prs", "github:read", "github", "List open pull requests for an owner/name repo.", True),
    ToolSpec("github_get_issue", "github:read", "github", "Fetch one GitHub issue by number.", True),
    ToolSpec("db_recent_deployments", "db:read", "sqlite", "Recent deployments for a customer from the ops DB.", True),
    ToolSpec("db_log_incident", "db:write", "sqlite", "Record an incident for a customer in the ops DB.", False),
    ToolSpec("telegram_send_alert", "telegram:notify", "telegram", "Send an alert to the on-call Telegram chat.", False),
)

Handler = Callable[..., Awaitable[Any]]


def build_handlers(
    role: str,
    github: GitHubConnector,
    sqlite: SQLiteConnector,
    telegram: TelegramConnector,
) -> dict[str, Handler]:
    """Thin adapters from MCP arguments to connector calls. No policy or error logic here."""
    connectors: dict[str, Connector] = {c.name: c for c in (github, sqlite, telegram)}

    async def server_health() -> dict:
        return {
            "role": role,
            "sources": {name: {"configured": s.configured, "detail": s.detail} for name, c in connectors.items() for s in [c.status()]},
        }

    async def github_list_open_prs(repo: str) -> dict:
        return {"repo": repo, "pulls": await github.list_open_pulls(repo), "provenance": PROVENANCE_NOTE}

    async def github_get_issue(repo: str, number: int) -> dict:
        return {"issue": await github.get_issue(repo, number), "provenance": PROVENANCE_NOTE}

    async def db_recent_deployments(customer: str, limit: int = 20) -> dict:
        rows = await sqlite.recent_deployments(customer, limit)
        return {"customer": customer, "deployments": rows, "provenance": PROVENANCE_NOTE}

    async def db_log_incident(customer: str, summary: str, severity: str) -> dict:
        return await sqlite.log_incident(customer, summary, severity)

    async def telegram_send_alert(message: str, severity: str = "info") -> dict:
        """Send an alert; if Telegram is temporarily down, park it in the SQLite outbox.

        Only transient failures queue. An auth or validation failure is surfaced, because
        hiding a misconfiguration behind a success-shaped result is how alerting rots.
        """
        try:
            return await telegram.send_alert(message, severity)
        except SourceError as exc:
            if exc.kind not in QUEUEABLE or not sqlite.status().configured:
                raise
            reason = f"{exc.kind}: {exc.message}"
            try:
                outbox_id = await sqlite.enqueue_alert(message, severity, reason)
            except SourceError:
                raise exc from None  # both sources down: report the one the caller asked about
            return {
                "delivered": False,
                "queued": True,
                "outbox_id": outbox_id,
                "reason": reason,
                "retry_after_s": exc.retry_after_s,
            }

    handlers = {
        "server_health": server_health,
        "github_list_open_prs": github_list_open_prs,
        "github_get_issue": github_get_issue,
        "db_recent_deployments": db_recent_deployments,
        "db_log_incident": db_log_incident,
        "telegram_send_alert": telegram_send_alert,
    }
    assert handlers.keys() == {s.name for s in TOOL_SPECS}, "registry and handlers out of sync"
    return handlers
