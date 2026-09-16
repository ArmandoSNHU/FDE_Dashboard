# fde-mcp — one MCP server, three real sources, least-privilege by default

Project 1 of the [FDE portfolio](../../README.md). Run commands from this directory.

**Author:** Armando Gomez · **Status:** working — all three connectors implemented, 170 tests passing, `scripts/demo.py` runs the whole thing with no credentials

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
uv run python scripts/demo.py             # demo: full scenario, no credentials needed
uv run pytest -q                          # test: 170 passed
uv run fde-mcp                            # run (stdio MCP server, role from FDE_MCP_ROLE)
```

`scripts/demo.py` builds a throwaway ops database, starts the real server as `oncall`, and walks one
incident: what shipped → record the incident → alert the chat (dry-run) → ask GitHub with no token,
so you can see a degraded source answer instead of crashing. Copy `.env.example` to `.env` when you
want to point it at real sources; every value is optional.

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
  untrusted.py              third-party text: strip what hides, cap, label provenance
  access/policy.py          AccessPolicy: deny-by-default scope checks
  connectors/               one module per source, MCP-agnostic
  tools/registry.py         TOOL_SPECS (surface of record) + thin handlers
tests/                      policy, server wiring, connector contracts, docs contract
docs/adr/                   architecture decision records
docs/postmortems/           incident write-ups
```

## Architecture decisions

Recorded in [`docs/adr/`](docs/adr/). Post-mortems are in [`docs/postmortems/`](docs/postmortems/).

## Threat model

The interesting threat in an MCP server isn't a hacker at the door — it's that **the server feeds
third-party text into a model that can call tools**. A pull request title is written by a stranger
and lands in the same context window as the instructions the model is following.

| Threat | What we do | Proven by |
|---|---|---|
| **Prompt injection** via PR titles, issue bodies, DB rows | Strip zero-width, bidi-override, ANSI and control characters; cap length; label every such result `provenance: untrusted`; tell the model in the server instructions never to follow tool output | `tests/test_untrusted_content.py`, `tests/test_injection_end_to_end.py` |
| Injection escalating to a **real-world action** | The named tool isn't registered for the role, so there's nothing to call; Telegram is dry-run until a human sets `TELEGRAM_DRY_RUN=false` | `test_obeying_the_injection_is_impossible_for_a_viewer` |
| **Context flooding** (a 400 KB issue body burying the real content) | Per-field caps with a visible truncation marker; blank-line runs collapsed | `test_a_huge_body_cannot_flood_the_context` |
| **Credential exposure** in results, errors or logs | Tokens never interpolated into messages; Telegram's URL (which contains the token) is never logged; unexpected exceptions are replaced with a generic message | token-leak tests in all three connector suites |
| **Credentials committed** to the repo | Every tracked file is scanned for credential shapes; fixtures must carry an obvious fake marker | `tests/test_no_secrets_committed.py` |
| **SQL injection** | No tool accepts SQL; every statement is fixed and parameterised | `test_customer_is_parameterised_not_interpolated` |
| **Data exfiltration** to an attacker's chat | `telegram_send_alert` takes no chat id; the destination comes from the environment | `tests/test_telegram_connector.py` |
| **Over-broad tool access** | Tools require a scope; roles grant scopes; unknown roles get nothing | `tests/test_access_policy.py`, `tests/test_server.py` |
| A **read tool writing** by accident | Read path opens SQLite with `mode=ro`; SQLite itself rejects the write | `test_read_path_opens_the_file_read_only` |

**What we deliberately don't do:** try to detect "an instruction" in third-party text. Phrase-matching for
jailbreaks misses rewordings and mangles legitimate content — a bug report that says "ignore previous
instructions" is a normal bug report. Hostile text stays visible and quoted verbatim, because silently
rewriting it would hide the attack from the human reading the output. The boundary that actually holds is
the one injection can't talk its way through: a capability the process was never started with.

**Known limits:** a model can still be *misled* by hostile text (told a false fact and repeat it). Nothing
here prevents that; it bounds the blast radius to what the role could already do. There is no rate limiting
or audit log of tool calls yet.

## Acceptance criteria

What "done" means for this server, and where each is proven:

| Criterion | Proven by |
|---|---|
| A role can never call a tool outside its scopes, and can't see it either | `tests/test_server.py` (registration + call-time guard), live in `scripts/smoke_stdio.py` |
| No source failure can crash the server or block another source | `tests/test_server.py`, demo step 5 (GitHub unconfigured while SQLite and Telegram work) |
| Every documented failure maps to a stable `kind`, with `retry_after_s` where it exists | `tests/test_github_connector.py`, `test_sqlite_connector.py`, `test_telegram_connector.py` |
| A read tool can never write, even by mistake | `test_read_path_opens_the_file_read_only` (SQLite `mode=ro` rejects the insert) |
| No credential appears in a result, an error, or a log line | token-leak tests in all three connector suites |
| An accepted alert is never silently lost | `tests/test_alert_fallback.py` (transient → outbox; permanent → surfaced) |
| Third-party text can't hide characters, flood the context, or escalate to an action | `tests/test_untrusted_content.py`, `tests/test_injection_end_to_end.py` |
| No credential shape is ever committed | `tests/test_no_secrets_committed.py` (patterns self-tested against realistic values) |
| The server starts with nothing configured | `test_server_starts_and_reports_health_with_nothing_configured` |
| The docs match the code | `tests/test_docs_contract.py` (README tool table vs. registry) |

## Limitations (honest list)

- One role per process. There's no per-request identity yet, so it isn't suitable as a shared multi-tenant HTTP server as-is.
- No retries inside the server: retry decisions are handed to the client via `retryable` / `retry_after_s`. This is deliberate, but it's a trade-off.
- **Nothing drains the outbox yet.** A queued alert is safely stored and visible in `alert_outbox`, but redelivery is manual.
- `github_list_open_prs` returns the first page only (100 PRs). Deeper history is a job for the ops DB, not this tool.
- No eval harness yet for "does the model pick the right tool under each role" — that's portfolio project 02.
- Tested against mocked HTTP. The GitHub and Telegram paths have never run against the live APIs.
