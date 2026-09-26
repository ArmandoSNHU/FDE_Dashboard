# SQLite connection lifecycle contribution
Author: Armando Gomez
Date: 2026-09-26

## Defect and operational impact
The connector used `with sqlite3.connect(...)` as if it also closed the connection. That context manages transactions; it does not close the connection. Reads, incident writes and queued-alert writes could retain handles until garbage collection. Setup failure during PRAGMA also left the newly opened handle without explicit cleanup. This matters in long-running integrations where resource use and file release should be predictable.

## Reproduction and fix
Seven tests retain instrumented real SQLite connections so garbage collection cannot hide the behavior. Before the fix, all seven failed because `close()` had not run. The fix nests the existing transaction context inside `contextlib.closing`, preserving commit/rollback while guaranteeing closure in the same worker thread. The setup path closes on exception before propagating the existing error mapping.

The tests exercise three successful operations, three query failures, and one setup failure. Existing persistence, read-only enforcement, lock handling and role tests remain in the suite. No new tool, permission or network action is introduced.

## Verify from the repository root
```powershell
cd projects/01-mcp-server
uv sync --frozen
uv run pytest -q
uv run python scripts/demo.py
uv run python scripts/smoke_stdio.py
cd ../02-eval-harness
uv sync --frozen
uv run pytest -q
uv run fde-evals --check
cd ../01-mcp-server
uv run python scripts/build_dashboard_data.py
```

Observed baseline: server `173 passed in 7.65s`; evaluation harness `34 passed in 5.35s`. New lifecycle tests against old code: `7 failed in 0.47s`. After the fix: server `180 passed in 3.35s`. The credential-free demo ended `Demo complete`; stdio smoke verified viewer hides telegram_send_alert while oncall exposes six tools. Evaluation scores remain 94.6% and zero unsafe decisions for the scope-aware rule agent, not a live model.

## TechOps value and experience
This demonstrates reproducing a reliability defect, testing resource lifetime independently from garbage collection, preserving transaction safety, reading failure paths, and verifying a multi-component integration. TechOpsagent can use the same evidence-first workflow for a future repository troubleshooting workspace; it does not yet automate these repository audits.

Only temporary synthetic databases, mocked transports and dry-run alerts were used. No production database or live message was involved. The change does not provide outbox redelivery or continuous resource monitoring. The generated dashboard must be refreshed after tests; its screenshot is a local branch preview, not proof the PR has merged.
