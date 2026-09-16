"""MCP server entrypoint: wires settings -> connectors -> policy-filtered tools."""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from fde_mcp.access.policy import AccessDenied, AccessPolicy
from fde_mcp.config import Settings
from fde_mcp.connectors import GitHubConnector, SQLiteConnector, TelegramConnector
from fde_mcp.errors import ErrorKind, SourceError, error_result, ok_result
from fde_mcp.tools.registry import TOOL_SPECS, Handler, ToolSpec, build_handlers

log = logging.getLogger("fde_mcp")

INSTRUCTIONS = (
    "Tools return {ok, data} or {ok: false, error: {source, kind, message, retryable, retry_after_s}}. "
    "A failure in one source does not affect the others. Honour retry_after_s on rate_limited; "
    "do not retry not_configured, auth, access_denied or invalid_input."
)


def guarded(spec: ToolSpec, handler: Handler, *, role: str, policy: AccessPolicy) -> Handler:
    """Wrap a handler with the call-time scope check and error-to-result mapping."""

    @functools.wraps(handler)  # keeps the signature, so MCP still derives the input schema
    async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            policy.require(role, spec.scope, tool=spec.name)
            return ok_result(await handler(*args, **kwargs))
        except AccessDenied as exc:
            return error_result(SourceError(spec.source, ErrorKind.ACCESS_DENIED, str(exc)))
        except SourceError as exc:
            log.warning("tool=%s source=%s kind=%s", spec.name, exc.source, exc.kind)
            return error_result(exc)
        except NotImplementedError:
            return error_result(SourceError(spec.source, ErrorKind.NOT_IMPLEMENTED, f"{spec.name} is a skeleton"))
        except Exception:
            # Full detail goes to server logs (stderr), never to the client: exceptions can carry secrets.
            log.exception("unexpected failure in tool=%s", spec.name)
            return error_result(SourceError(spec.source, ErrorKind.INTERNAL, "unexpected server error; see server logs"))

    # Schema introspection follows __wrapped__ to the handler's signature. Keep its parameters
    # (the input schema) but declare the envelope as the return type (the output schema).
    wrapper.__signature__ = inspect.signature(handler, eval_str=True).replace(return_annotation=dict)
    return wrapper


def build_server(settings: Settings, policy: AccessPolicy) -> MCPServer:
    github = GitHubConnector(settings.github_token)
    sqlite = SQLiteConnector(settings.db_path)
    telegram = TelegramConnector(settings.telegram_bot_token, settings.telegram_chat_id, dry_run=settings.telegram_dry_run)
    handlers = build_handlers(settings.role, github, sqlite, telegram)

    server = MCPServer("fde-mcp", instructions=INSTRUCTIONS)
    for spec in TOOL_SPECS:
        if not policy.allows(settings.role, spec.scope):
            continue  # not registered -> not listed -> not callable
        server.add_tool(
            guarded(spec, handlers[spec.name], role=settings.role, policy=policy),
            name=spec.name,
            description=spec.description,
            annotations=ToolAnnotations(readOnlyHint=spec.read_only, openWorldHint=spec.source in {"github", "telegram"}),
        )
    return server


def main() -> None:
    # stdio transport: stdout is the protocol channel, so logs must go to stderr.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings.from_env()
    policy = AccessPolicy.from_file(settings.policy_path)
    log.info("starting fde-mcp role=%s scopes=%s", settings.role, sorted(policy.scopes_for(settings.role)))
    build_server(settings, policy).run("stdio")


if __name__ == "__main__":
    main()
