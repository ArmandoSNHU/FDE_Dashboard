# STATE

## Restart Point (2026-09-15)

**Verify first:** `uv run pytest -q` → expect `27 passed`; `uv run python scripts/smoke_stdio.py` → viewer sees 4 tools, oncall sees 6.

**Done**
- Scaffold: package layout, `config/policy.toml`, `db/schema.sql`, `.env.example`, docs templates.
- Implemented + tested: access policy (deny by default, load-time validation), `guarded` error envelope, role-filtered registration, `server_health`, connector `status()`.
- Connector skeletons: GitHub, SQLite, Telegram. Public methods raise `NotImplementedError` after `_require_configured()`; failure mappings documented in module docstrings.
- README: problem, why these sources, auth per source, degradation table, limitations.

**Next (in order)**
1. GitHub connector: `_classify_response` TDD with `httpx.MockTransport` (401/403-ratelimit/404/422/5xx/timeout), then `list_open_pulls`, `get_issue`.
2. SQLite connector: `mode=ro` read path, validation, locked-DB test, `log_incident`, `enqueue_alert`.
3. Telegram connector: dry-run path first, then live path behind mocks; outbox fallback in `telegram_send_alert` handler.
4. Mando writes `docs/adr/0001-*` and a post-mortem.

**Open questions**
- Should the repo become a multi-project portfolio (`projects/01-mcp-server/…`), or stay single-project with the dashboard linking out?

## Session log
- **2026-09-15**: Initial scaffold + FDE portfolio dashboard. 27 tests passing; stdio smoke verified.
