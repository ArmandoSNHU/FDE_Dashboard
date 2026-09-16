# STATE — FDE Portfolio

Single state file for the whole repo. Project-level detail lives in each project's README and AGENTS.md.

## Restart Point (2026-09-15)

**Verify first**, from `projects/01-mcp-server`:
- `uv sync` then `uv run pytest -q` → expect `75 passed`
- `uv run python scripts/smoke_stdio.py` → viewer sees 4 tools, oncall sees 6, GitHub call returns `not_configured`

**Repo state**
- Layout: `projects/<NN>-<slug>/` per project, `index.html` (dashboard) at the root, this file at the root.
- Published: GitHub `ArmandoSNHU/FDE_Dashboard` (public), branch `main`.
- Dashboard is served by GitHub Pages from `main` at the repo root: https://armandosnhu.github.io/FDE_Dashboard/
- Each project has its own venv; `D:\FDE_Dash\.venv` from the pre-restructure layout is stale and can be deleted.

**Project 01 — fde-mcp: done**
- Access policy (deny by default, load-time validation), `guarded` error envelope, role-filtered registration, `server_health`, connector `status()`.
- **GitHub connector implemented**: status classification (401/403/403-ratelimit/404/422/5xx/timeout/connect-error), `retry_after_s` from `Retry-After` or `X-RateLimit-Reset`, repo-slug validation before any request, trimmed response shapes. 24 tests, all against `httpx.MockTransport` — no network, no token.
- **SQLite connector implemented**: read path opens `mode=ro` (SQLite itself rejects writes), parameterised queries only, input validation, locked-DB → retryable `unavailable`, corrupt/missing-table → non-retryable, queries run via `asyncio.to_thread` so a slow disk can't stall the event loop. 24 tests against a real DB built from `db/schema.sql`.
- README: problem, why these sources, auth per source, degradation table, honest limitations. Tool table is test-enforced (`tests/test_docs_contract.py`).

**Project 01 — next, in order**
1. Telegram connector: dry-run path first (no network), then the live path behind mocks.
2. Outbox fallback in the `telegram_send_alert` handler: on rate-limited/unavailable, call `sqlite.enqueue_alert` and return `delivered: false, queued: true`.
3. Mando writes `docs/adr/0001-*` and a post-mortem.

**Portfolio — next**
- Project 02 (evals) and 03 (enterprise integration) not started; candidates noted on the dashboard.

## Session log
- **2026-09-15**: Scaffolded project 01 and built the portfolio dashboard; restructured into `projects/01-mcp-server/`; implemented the GitHub and SQLite connectors test-first (27 → 75 tests); removed vendor-specific references; deployed the dashboard to GitHub Pages.
