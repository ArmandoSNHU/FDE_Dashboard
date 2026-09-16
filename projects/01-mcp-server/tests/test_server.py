"""Server wiring: role-filtered tool surface, call-time guard, structured error results."""

import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from fde_mcp.access.policy import AccessPolicy
from fde_mcp.config import DEFAULT_POLICY_PATH, Settings
from fde_mcp.errors import ErrorKind, SourceError
from fde_mcp.server import build_server, guarded
from fde_mcp.tools.registry import TOOL_SPECS, ToolSpec


def unconfigured(role: str) -> Settings:
    """Nothing configured: no tokens, no DB. The server must still start."""
    return Settings(role=role, github_token=None, db_path=None, telegram_bot_token=None, telegram_chat_id=None)


def payload(result) -> dict:
    return json.loads(result.content[0].text)


@pytest.fixture
def policy() -> AccessPolicy:
    return AccessPolicy.from_file(DEFAULT_POLICY_PATH)


async def tool_names(role: str, policy: AccessPolicy) -> set[str]:
    server = build_server(unconfigured(role), policy)
    return {t.name for t in await server.list_tools()}


async def test_viewer_cannot_see_write_or_notify_tools(policy):
    names = await tool_names("viewer", policy)
    assert "github_list_open_prs" in names
    assert "db_log_incident" not in names
    assert "telegram_send_alert" not in names


async def test_oncall_sees_every_tool(policy):
    assert await tool_names("oncall", policy) == {s.name for s in TOOL_SPECS}


async def test_unknown_role_sees_nothing(policy):
    assert await tool_names("intruder", policy) == set()


async def test_hidden_tool_cannot_be_called(policy):
    server = build_server(unconfigured("viewer"), policy)
    with pytest.raises(ToolError, match="Unknown tool"):
        await server.call_tool("telegram_send_alert", {"message": "hi"})


async def test_server_starts_and_reports_health_with_nothing_configured(policy):
    server = build_server(unconfigured("viewer"), policy)
    result = payload(await server.call_tool("server_health", {}))
    assert result["ok"] is True
    health = result["data"]
    assert health["role"] == "viewer"
    assert set(health["sources"]) == {"github", "sqlite", "telegram"}
    assert all(src["configured"] is False for src in health["sources"].values())


async def test_unconfigured_source_returns_structured_error_not_crash(policy):
    server = build_server(unconfigured("viewer"), policy)
    result = payload(await server.call_tool("github_list_open_prs", {"repo": "octo/repo"}))
    assert result["ok"] is False
    assert result["error"]["source"] == "github"
    assert result["error"]["kind"] == ErrorKind.NOT_CONFIGURED


# --- guard unit tests: one handler, every failure path -----------------------

SPEC = ToolSpec(name="t", scope="db:read", source="sqlite", description="d", read_only=True)


async def test_guard_rechecks_scope_at_call_time(policy):
    async def handler() -> dict:
        return {"secret": True}

    result = await guarded(SPEC, handler, role="intruder", policy=policy)()
    assert result["ok"] is False
    assert result["error"]["kind"] == ErrorKind.ACCESS_DENIED


async def test_guard_wraps_success(policy):
    async def handler() -> dict:
        return {"rows": []}

    assert await guarded(SPEC, handler, role="viewer", policy=policy)() == {"ok": True, "data": {"rows": []}}


async def test_guard_maps_source_error(policy):
    async def handler() -> dict:
        raise SourceError("sqlite", ErrorKind.UNAVAILABLE, "database is locked", retryable=True)

    result = await guarded(SPEC, handler, role="viewer", policy=policy)()
    assert result["error"] == {
        "source": "sqlite",
        "kind": "unavailable",
        "message": "database is locked",
        "retryable": True,
        "retry_after_s": None,
    }


async def test_guard_maps_unimplemented_skeleton(policy):
    async def handler() -> dict:
        raise NotImplementedError

    result = await guarded(SPEC, handler, role="viewer", policy=policy)()
    assert result["error"]["kind"] == ErrorKind.NOT_IMPLEMENTED


async def test_guard_hides_unexpected_exception_details(policy):
    async def handler() -> dict:
        raise RuntimeError("token=ghp_supersecret")

    result = await guarded(SPEC, handler, role="viewer", policy=policy)()
    assert result["error"]["kind"] == ErrorKind.INTERNAL
    assert "ghp_supersecret" not in json.dumps(result)
