# STATE — FDE Portfolio

Single state file for the whole repo. Project-level detail lives in each project's README and AGENTS.md.

## Restart Point (2026-09-17)

**Verify first:**
- `projects/01-mcp-server`: `uv sync` then `uv run pytest -q` → expect `173 passed`
- `projects/01-mcp-server`: `uv run python scripts/demo.py` → ends with "Demo complete"
- `projects/02-eval-harness`: `uv sync` then `uv run pytest -q` → expect `34 passed`
- `projects/02-eval-harness`: `uv run fde-evals --check` → v2 at 94.6%, 0 unsafe
- `projects/01-mcp-server`: `uv run python scripts/build_dashboard_data.py` → rewrites `dashboard-data.json`

**Repo state**
- Published: GitHub `ArmandoSNHU/FDE_Dashboard` (public), branch `main`. Dashboard:
  https://armandosnhu.github.io/FDE_Dashboard/ — Pages builds from GitHub Actions, not from the branch.
- CI (`.github/workflows/ci.yml`): both projects tested on Ubuntu + Windows, demo re-run under
  `PYTHONIOENCODING=cp1252`, evals gated at 94% with zero unsafe, then the dashboard data is regenerated and
  the site published.
- Verified from a clean clone of the public repo.
- `D:\FDE_Dash\.venv` from the pre-restructure layout is stale and can be deleted (path protection blocks it
  from this session).

**Project 01 — fde-mcp: complete for its scope**
Three connectors (GitHub, SQLite, Telegram), role-scoped registration with a call-time guard, one error
envelope for every failure, an outbox so a failed alert is never dropped, injection defences in
`untrusted.py`, secret scanning, a credential-free demo, ADRs 0001 and 0002, and a post-mortem.

**Project 02 — fde-evals: complete for its scope**
37 cases across happy path, write, notify, out-of-scope, ambiguous, injection, error handling and two
deliberate known gaps. Two rule-based agents scored: v1 45.9% with 8 unsafe, v2 94.6% with 0 unsafe.
Results committed as JSON and Markdown in `results/`. `LocalModelAgent` can score a real model over an
OpenAI-compatible endpoint; its parsing is unit-tested but **it has never been run against a live model**,
and no score for it is published.

**Bugs found by verification, all now guarded**
1. `demo.py` crashed with `UnicodeEncodeError` on a cp1252 console (post-mortem written).
2. The dashboard's own CSP blocked four inline styles, one of them set from JS.
3. Six light-theme text colours failed WCAG AA; writing the guard found a seventh in dark.
4. The test total moved with repo size (211 in CI vs 198 locally) because a scan was parametrised per file.
5. The eval harness caught its own matcher bugs: `pr` matching inside `prod`, then plurals matching nothing.

**Next, whoever picks this up**
1. Project 03 (enterprise integration) is the only unstarted piece. System not chosen.
2. An audit log of tool calls — named in both ADRs as the first thing to build next.
3. Drain the outbox: queued alerts are stored but never redelivered.
4. Run project 01 once against the live GitHub API with a read-only token; every HTTP path is mocked so far.
   Needs Mando's approval (real credentials).
5. Score a real local model with `LocalModelAgent` — needs a model runtime started, which is approval-gated.

## Session log
- **2026-09-15**: Built project 01 end to end — scaffold, three connectors test-first, outbox fallback, demo.
  Restructured into `projects/`, published to GitHub Pages, verified from a clean clone. Added
  prompt-injection defences and secret scanning; rebuilt the dashboard to render generated data with a role
  switcher and failure explorer under a strict CSP; added CI across two operating systems.
- **2026-09-17**: Wrote ADR-0001, ADR-0002 and the post-mortem. Built project 02 (eval harness) and wired its
  results into the dashboard and CI. Removed the co-authorship trailers from the two commits that carried
  them. Reviewer checklist now 6/6.
