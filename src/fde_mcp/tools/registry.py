"""The single source of truth for the tool surface.

Each tool declares the scope it needs and the source it touches. The server uses this
to decide what to register for a role; tests use it to keep the README honest.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fde_mcp.connectors import Connector, GitHubConnector, SQLiteConnector, TelegramConnector


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

    async def github_list_open_prs(repo: str) -> list[dict]:
        return await github.list_open_pulls(repo)

    async def github_get_issue(repo: str, number: int) -> dict:
        return await github.get_issue(repo, number)

    async def db_recent_deployments(customer: str, limit: int = 20) -> list[dict]:
        return await sqlite.recent_deployments(customer, limit)

    async def db_log_incident(customer: str, summary: str, severity: str) -> dict:
        return await sqlite.log_incident(customer, summary, severity)

    async def telegram_send_alert(message: str, severity: str = "info") -> dict:
        # TODO: on RATE_LIMITED / UNAVAILABLE from a live send, fall back to
        # sqlite.enqueue_alert(...) and return {"delivered": False, "queued": True}.
        return await telegram.send_alert(message, severity)

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
