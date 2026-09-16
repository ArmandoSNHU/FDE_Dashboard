# fde-mcp — agent instructions

## Mission
Portfolio project (author: Armando Gomez) demonstrating Forward Deployed Engineer production thinking: a Python MCP
server (official `mcp` SDK 2.x) over GitHub, a local SQLite ops DB, and Telegram, with role-scoped tools and
per-source structured failures. `dashboard/` is the FDE portfolio dashboard that presents this and future projects.

## Read order
1. `STATE.md`: current state and Restart Point. **It wins over anything else.**
2. `README.md`: the public contract (tool table is test-enforced).
3. `config/policy.toml`, `src/fde_mcp/tools/registry.py`, `src/fde_mcp/server.py`.

## Commands
```powershell
uv sync
uv run pytest -q                       # full suite
uv run python scripts/smoke_stdio.py   # live: spawns real server over stdio, per role, no network
uv run fde-mcp                         # run server (stdio)
```

## Architecture
| Module | Role |
|---|---|
| `tools/registry.py` | `TOOL_SPECS`: the surface of record (name, scope, source) and thin handlers |
| `access/policy.py` | Deny-by-default scope checks; `config/policy.toml` maps roles to scopes |
| `server.py` | `build_server` registers only allowed tools; `guarded` re-checks scope and maps errors to the `{ok, error}` envelope |
| `errors.py` | `ErrorKind` + `SourceError`: the only exception connectors may raise |
| `connectors/*.py` | One per source, MCP-agnostic; module docstring = auth + failure mapping |

## Gotchas
- mcp 2.x: `FastMCP` is now `mcp.server.mcpserver.MCPServer`. v1 snippets online won't import.
- `guarded` must set `__signature__` with `return_annotation=dict`. The SDK follows `__wrapped__` to infer output schema, and the handler's return type would reject the envelope.
- stdio transport: stdout is the protocol. Log to stderr only.
- Adding a tool means updating `TOOL_SPECS`, `build_handlers`, the README tool table, and possibly `policy.toml`; `test_docs_contract.py` enforces this.

## Approval gates
- Telegram live sends (`TELEGRAM_DRY_RUN=false`), real GitHub calls with Mando's token, and any push: ask first.
- Dry-run path and mocked-transport tests (`httpx.MockTransport`) must exist before a live send path lands.

## Done means
Tests pass with the count reported, the smoke script output is shown, README/docs match the code, and `STATE.md` has a dated entry.
