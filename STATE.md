# STATE — FDE Portfolio

Single state file for the whole repo. Project-level detail lives in each project's README and AGENTS.md.

## Restart Point (2026-09-15)

**Verify first**, from `projects/01-mcp-server`:
- `uv sync` then `uv run pytest -q` → expect `110 passed`
- `uv run python scripts/demo.py` → full incident scenario, no credentials, ends with "Demo complete"
- `uv run python scripts/smoke_stdio.py` → viewer sees 4 tools, oncall sees 6

**Repo state**
- Layout: `projects/<NN>-<slug>/` per project, `index.html` (dashboard) at the root, this file at the root.
- Published: GitHub `ArmandoSNHU/FDE_Dashboard` (public), branch `main`.
- Dashboard live via GitHub Pages from `main` at the repo root: https://armandosnhu.github.io/FDE_Dashboard/
- Verified from a clean clone of the public repo (temp dir): `uv sync`, 110 passed, demo runs.
- Each project has its own venv; `D:\FDE_Dash\.venv` from the pre-restructure layout is stale and can be deleted.

**Project 01 — fde-mcp: done**
- Access policy (deny by default, load-time validation), `guarded` error envelope, role-filtered registration, `server_health`.
- **GitHub connector**: 401/403/403-ratelimit/429/404/422/5xx/timeout/connect-error classification, `retry_after_s` from `Retry-After` or `X-RateLimit-Reset`, slug validation before any request, trimmed responses. 24 tests via `httpx.MockTransport`.
- **SQLite connector**: `mode=ro` read path (SQLite itself rejects writes), parameterised queries only, locked-DB → retryable, corrupt/missing-table → not retryable, work runs in `asyncio.to_thread`. 24 tests against a real DB from `db/schema.sql`.
- **Telegram connector**: dry-run default with no network call, live path classifies 401/404/400-chat-not-found/400-other/429 (`parameters.retry_after`)/5xx/transport, and treats `200 ok:false` as undelivered. Token never appears in a result or error. 24 tests.
- **Outbox fallback** (`tools/registry.py`): transient Telegram failure → `sqlite.enqueue_alert` → `delivered:false, queued:true`; permanent failures surface instead; if SQLite is also down the original Telegram error wins. 8 tests.
- **Demo**: `scripts/demo.py` — throwaway DB, real server as `oncall`, one incident end to end including a degraded GitHub call.
- Docs: acceptance-criteria table (promise → the test proving it), honest limitations, reviewer path in the root README.

**Known bug found and fixed (candidate post-mortem material)**
Clean-clone verification caught `demo.py` crashing with `UnicodeEncodeError` on a Windows console using cp1252, because it printed box-drawing characters. It passed locally in a UTF-8 shell. Fixed by going ASCII-only, guarded by `tests/test_scripts_portable.py`. The lesson — "verified on my machine" isn't verified — is exactly what the post-mortem template asks for.

**Project 01 — next, in order**
1. Mando writes `docs/adr/0001-*`. Strongest candidate: role per process vs. per-request identity (options, cost, what would reopen it).
2. Post-mortem from the cp1252 bug above, or a real incident.
3. Optional: drain the outbox (queued alerts are stored but never redelivered).
4. Optional: run once against the live GitHub API with a read-only token — every HTTP path so far is mocked.

**Portfolio — next**
- Project 02 (evals): candidate is tool-selection accuracy per role against this server — 20+ cases including refusal and out-of-scope, with committed before/after pass rates.
- Project 03 (enterprise integration): system not chosen yet.

## Session log
- **2026-09-15**: Built project 01 end to end — scaffold, then GitHub, SQLite and Telegram connectors test-first, outbox fallback, runnable demo (27 → 110 tests). Restructured into `projects/01-mcp-server/`, removed vendor-specific references, deployed the dashboard to GitHub Pages, and verified the whole thing from a clean clone (which found the cp1252 bug).
