# STATE — FDE Portfolio

Single state file for the whole repo. Project-level detail lives in each project's README and AGENTS.md.

## Restart Point (2026-09-15)

**Verify first**, from `projects/01-mcp-server`:
- `uv sync` then `uv run pytest -q` → expect `160 passed`
- `uv run python scripts/demo.py` → full incident scenario, no credentials, ends with "Demo complete"
- `uv run python scripts/build_dashboard_data.py` → rewrites `dashboard-data.json` at the repo root

**Repo state**
- Layout: `projects/<NN>-<slug>/` per project; `index.html` + `assets/` + `dashboard-data.json` at the root (the dashboard); this file at the root.
- Published: GitHub `ArmandoSNHU/FDE_Dashboard` (public), branch `main`.
- Dashboard: https://armandosnhu.github.io/FDE_Dashboard/ — **Pages now builds from GitHub Actions**, not from the branch. `.github/workflows/ci.yml` runs the suite on Ubuntu + Windows, regenerates the data, then publishes.
- Verified from a clean clone of the public repo: `uv sync`, tests, demo.
- `D:\FDE_Dash\.venv` from the pre-restructure layout is stale and can be deleted (blocked from here by path protection).

**Project 01 — fde-mcp: done**
- Access policy (deny by default, load-time validation), `guarded` error envelope, role-filtered registration, `server_health`.
- **GitHub connector**: full status classification, `retry_after_s` from `Retry-After` / `X-RateLimit-Reset`, slug validation before any request, trimmed responses. Tests via `httpx.MockTransport`.
- **SQLite connector**: `mode=ro` read path, parameterised statements only, locked-DB retryable vs. corrupt not, work in `asyncio.to_thread`.
- **Telegram connector**: dry-run default with no network call; `200 ok:false` treated as undelivered; token never in a result or error.
- **Outbox fallback**: transient Telegram failure → `sqlite.enqueue_alert` → `queued: true`; permanent failures surface; if SQLite is also down the Telegram error wins.
- **Injection defences** (`src/fde_mcp/untrusted.py`): strip zero-width/bidi/ANSI/control characters, cap fields, attach a `provenance` block, and server instructions tell the client never to follow tool output. Hostile text is *not* rewritten — the defence that holds is that the named tool isn't registered for the role.
- **Secret scanning**: every tracked file checked for credential shapes; the patterns are self-tested so the scan can't pass vacuously.
- **Demo**: `scripts/demo.py`, no credentials, one incident end to end.

**Dashboard: generated, not typed**
`scripts/build_dashboard_data.py` writes `dashboard-data.json` by building the real server per role, running
the real guard per failure kind, running the real sanitiser over a real payload, and parsing a pytest report.
The page renders that and adds a role switcher and a failure explorer. It ships a strict CSP
(`default-src 'none'`, no `unsafe-inline`); `tests/test_dashboard_contract.py` fails if an inline style or
script appears, if the data drifts from the registry/policy, or if a referenced asset is missing.

**Bugs found by verification (post-mortem material)**
1. `demo.py` crashed with `UnicodeEncodeError` on a cp1252 console while passing in a UTF-8 shell. Fixed ASCII-only; guarded by `test_scripts_portable.py`; CI now re-runs the demo with `PYTHONIOENCODING=cp1252`.
2. The page's own CSP blocked four inline styles of mine, including one set from JS. Fixed as classes; guarded by `test_dashboard_contract.py`.

**Next, in order**
1. Mando writes `docs/adr/0001-*`. Strongest candidate: role per process vs. per-request identity.
2. Post-mortem — candidate 1 above is the better story (environment assumption, not a typo).
3. Project 02 (evals): tool-selection accuracy per role, 20+ cases including refusal and out-of-scope, committed before/after pass rates.
4. Optional: drain the outbox; run once against the live GitHub API with a read-only token (every HTTP path is mocked so far).

## Session log
- **2026-09-15**: Built project 01 end to end — scaffold, three connectors test-first, outbox fallback, runnable demo. Restructured into `projects/01-mcp-server/`, removed vendor-specific references, deployed to GitHub Pages, verified from a clean clone. Then added prompt-injection defences and secret scanning, rebuilt the dashboard to render generated data with a role switcher and failure explorer under a strict CSP, and added CI that tests on two operating systems before publishing. 27 → 160 tests.
