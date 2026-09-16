# fde-mcp — one MCP server, three real sources, least-privilege by default

Project 1 of the [FDE portfolio](../../README.md). Run commands from this directory.

**Author:** Armando Gomez · **Status:** scaffold (connectors are skeletons; access control, error model, and wiring are implemented and tested)

## The problem

An on-call engineer at a customer site needs three answers fast, and they live in three different places:
*What changed?* (GitHub), *What is deployed where, and what's already been reported?* (a local ops database), and
*Who needs to know right now?* (a Telegram chat). Handing an AI assistant raw credentials to all three is how
a helpful model ends up paging a whole team, or writing to the wrong table, because a prompt was ambiguous.

`fde-mcp` exposes those three sources as [Model Context Protocol](https://modelcontextprotocol.io) tools with:

- **role-scoped tools**: a client only sees and can only call the tools its role grants;
- **per-source isolation**: one source being down, unconfigured, or rate-limited never breaks the others;
- **structured failures**: every error comes back as `{source, kind, retryable, retry_after_s}` so the model can decide whether to retry, explain, or stop;
- **side effects off by default**: Telegram runs in dry-run mode until you explicitly turn it off.

## Why these three sources

| Source | Why it's here | What it exercises |
|---|---|---|
| **GitHub REST API** | The system of record for *change*: PRs and issues. | Remote HTTP auth, rate limits, pagination, 404-means-maybe-forbidden ambiguity. |
| **Local SQLite** | Stands in for the customer's on-prem ops DB: deployments, incidents. | No network auth, file-permission boundary, read vs. write separation, lock contention. |
| **Telegram Bot API** | The notification channel: the one tool with a real-world side effect. | Outbound-only design, dry-run gating, rate limits, never dropping an alert. |

Together they cover read-remote, read/write-local, and write-to-humans: the three shapes of integration an FDE ends up wiring together.

## Tool surface

The registry in `src/fde_mcp/tools/registry.py` is the source of truth. `tests/test_docs_contract.py` fails if this table drifts from it.

| Tool | Scope | Source | Side effect |
|---|---|---|---|
| `server_health` | `health:read` | server | none |
| `github_list_open_prs` | `github:read` | GitHub | none |
| `github_get_issue` | `github:read` | GitHub | none |
| `db_recent_deployments` | `db:read` | SQLite | none |
| `db_log_incident` | `db:write` | SQLite | inserts a row |
| `telegram_send_alert` | `telegram:notify` | Telegram | messages humans |

## Access control

Defined in [`config/policy.toml`](config/policy.toml): **tools require one scope, roles grant scopes, the process runs as one role** (`FDE_MCP_ROLE`).

| Role | `health:read` | `github:read` | `db:read` | `db:write` | `telegram:notify` |
|---|:-:|:-:|:-:|:-:|:-:|
| `viewer` (default) | ✓ | ✓ | ✓ | | |
| `operator` | ✓ | ✓ | ✓ | ✓ | |
| `oncall` | ✓ | ✓ | ✓ | ✓ | ✓ |

Enforcement happens in two places:

1. **At registration.** Tools outside the role's scopes are never registered, so they don't appear in `tools/list` and the model can't pick them.
2. **At call time.** Every handler re-checks its scope before touching a source, as defence in depth.

Deny by default: an unknown role gets zero tools, and a policy that grants an undeclared scope (for example, a typo) fails at startup instead of silently granting nothing.

**Why a role per process?** MCP over stdio is one client per server process, so the natural identity boundary is the
client configuration: register `fde-mcp` twice in your MCP client, once as `viewer` and once as `oncall`. Mapping bearer tokens to roles for a shared HTTP deployment is future work (ADR candidate).

## How auth works, per source

| Source | Credential | Where it lives | Least-privilege setup | What we protect against |
|---|---|---|---|---|
| GitHub | Fine-grained PAT, `Authorization: Bearer` | `GITHUB_TOKEN` | Read-only *Metadata, Contents, Issues, Pull requests* on selected repos only | Token never logged or returned; `server_health` reports presence, not value |
| SQLite | None: filesystem permissions | `FDE_DB_PATH` | Read tools open with `mode=ro`; only `db:write` roles get a read-write connection; no raw SQL tools | Missing file is `not_configured` (never auto-created); all queries parameterised |
| Telegram | Bot token (in URL path) + fixed chat id | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Tool takes no chat-id argument, so the model can't redirect alerts | URLs never logged (token is in the path); `TELEGRAM_DRY_RUN=true` by default |

Credentials are read once from the environment (see [`.env.example`](.env.example)). Nothing is required to *start*: an unconfigured source just reports `not_configured`.

## Failure & degradation

Every tool returns `{"ok": true, "data": ...}` or `{"ok": false, "error": {source, kind, message, retryable, retry_after_s}}`.

| Source | Failure | `kind` | Retryable | Behaviour |
|---|---|---|---|---|
| any | credentials/path missing | `not_configured` | no | Server still starts; other sources unaffected; `server_health` explains what's missing |
| any | scope not granted | `access_denied` | no | Normally unreachable (tool not registered); guard backstop |
| any | unexpected exception | `internal` | no | Detail logged to stderr only; client gets a generic message (exceptions can carry secrets) |
| GitHub | 401 / 403 without rate-limit headers | `auth` | no | Token invalid or lacks repo permission |
| GitHub | 403 with `X-RateLimit-Remaining: 0`, or 429 | `rate_limited` | yes | `retry_after_s` from `Retry-After` / `X-RateLimit-Reset` |
| GitHub | 404 | `not_found` | no | May also mean "private repo this token can't see" |
| GitHub | 5xx, timeout (10 s), connection error | `unavailable` | yes | |
| SQLite | `database is locked` after 2 s busy timeout | `unavailable` | yes | |
| SQLite | corrupt file, schema mismatch, IO error | `unavailable` | no | |
| SQLite | bad severity / limit out of range | `invalid_input` | no | Validated before any query runs |
| Telegram | 401/404 bad token; 400 chat not found | `auth` / `not_configured` | no | |
| Telegram | 429 | `rate_limited` | yes | `retry_after_s` from `parameters.retry_after` |
| Telegram | 5xx, timeout | `unavailable` | yes | **Alert is written to SQLite `alert_outbox`** (if configured) and the result says `delivered: false, queued: true`. Alerts are never silently dropped. |

The mapping for each source is documented at the top of its connector module in `src/fde_mcp/connectors/`.

## Run it

```powershell
uv sync                                   # setup
Copy-Item .env.example .env               # then fill in what you have; everything is optional
uv run pytest -q                          # test
uv run fde-mcp                            # run (stdio MCP server, role from FDE_MCP_ROLE)
```

Register it with any MCP client that speaks stdio. Most use this shape of config:

```json
{
  "mcpServers": {
    "fde-viewer": {
      "command": "uv",
      "args": ["--directory", "/path/to/projects/01-mcp-server", "run", "fde-mcp"],
      "env": { "FDE_MCP_ROLE": "viewer", "GITHUB_TOKEN": "...", "FDE_DB_PATH": "/path/to/data/ops.db" }
    }
  }
}
```

Register it twice with different `FDE_MCP_ROLE` values to give one client read-only access and another the full surface.

## Layout

```
config/policy.toml          roles -> scopes (access control)
db/schema.sql               ops DB schema: deployments, incidents, alert_outbox
src/fde_mcp/
  server.py                 build_server(): policy-filtered registration + guarded() error envelope
  config.py                 Settings.from_env()
  errors.py                 ErrorKind, SourceError: the shared failure vocabulary
  access/policy.py          AccessPolicy: deny-by-default scope checks
  connectors/               one module per source, MCP-agnostic
  tools/registry.py         TOOL_SPECS (surface of record) + thin handlers
tests/                      policy, server wiring, connector contracts, docs contract
docs/adr/                   architecture decision records
docs/postmortems/           incident write-ups
```

## Architecture decisions

Recorded in [`docs/adr/`](docs/adr/). Post-mortems are in [`docs/postmortems/`](docs/postmortems/).

## Limitations (honest list)

- **Connectors are skeletons.** Calls to configured sources currently return `not_implemented`. The contract, failure mapping, and tests around them are in place; the HTTP and SQL bodies are next.
- One role per process. There's no per-request identity yet, so it isn't suitable as a shared multi-tenant HTTP server as-is.
- No retries inside the server: retry decisions are handed to the client via `retryable` / `retry_after_s`. This is deliberate, but it's a trade-off.
- The Telegram → SQLite outbox fallback is designed and documented, but not yet implemented or drained by anything.
- No eval harness yet for "does the model pick the right tool under each role".
