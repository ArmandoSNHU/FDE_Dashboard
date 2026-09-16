# STATE — FDE Portfolio

Single state file for the whole repo. Project-level detail lives in each project's README/CLAUDE.md.

## Restart Point (2026-09-15)

**Verify first**, from `projects/01-mcp-server`:
- `uv sync` then `uv run pytest -q` → expect `27 passed`
- `uv run python scripts/smoke_stdio.py` → viewer sees 4 tools, oncall sees 6, GitHub call returns `not_configured`

**Repo state**
- Layout: `projects/<NN>-<slug>/` per project, `dashboard/index.html` at root, this file at root.
- Published: GitHub `ArmandoSNHU/FDE_Dashboard` (public), branch `main`. Dashboard artifact: https://claude.ai/artifact/NdqjuqgSzNHbkfbFDyyS7V
- Each project has its own venv; `D:\FDE_Dash\.venv` from the pre-restructure layout is stale and can be deleted.

**Project 01 — fde-mcp: done**
- Implemented + tested: access policy (deny by default, load-time validation), `guarded` error envelope, role-filtered registration, `server_health`, connector `status()`.
- Connector skeletons: GitHub, SQLite, Telegram. Public methods raise `NotImplementedError` after `_require_configured()`; failure mappings documented in module docstrings.
- README: problem, why these sources, auth per source, degradation table, honest limitations. Tool table is test-enforced (`tests/test_docs_contract.py`).

**Project 01 — next, in order**
1. GitHub connector: `_classify_response` TDD with `httpx.MockTransport` (401 / 403-ratelimit / 404 / 422 / 5xx / timeout), then `list_open_pulls`, `get_issue`.
2. SQLite connector: `mode=ro` read path, input validation, locked-DB test, `log_incident`, `enqueue_alert`.
3. Telegram connector: dry-run path first, then live path behind mocks; outbox fallback in the `telegram_send_alert` handler.
4. Mando writes `docs/adr/0001-*` and a post-mortem.

**Portfolio — next**
- Project 02 (evals) and 03 (enterprise integration) not started; candidates noted in the dashboard.
- Optional: enable GitHub Pages (Settings → Pages → branch `main`, folder `/`) so the dashboard is linkable; it is static and needs no build.

## Session log
- **2026-09-15**: Initial scaffold of project 01 (27 tests, stdio smoke verified), built the portfolio dashboard, restructured into `projects/01-mcp-server/`, first commit, pushed to GitHub.
