# STATE — FDE Portfolio

Single state file for the whole repo. Project-level detail lives in each project's README and AGENTS.md.

## Restart Point (2026-10-10)

**Verify first:**
- `projects/01-mcp-server`: `uv sync` then `uv run pytest -q` → expect `185 passed`
- `projects/01-mcp-server`: `uv run python scripts/demo.py` → ends with "Demo complete"
- `projects/02-eval-harness`: `uv sync` then `uv run pytest -q` → expect `34 passed`
- `projects/02-eval-harness`: `uv run fde-evals --check` → v2 at 95.3%, 0 unsafe
- `projects/03-legacy-sync`: `uv sync` then `uv run pytest -q` → expect `76 passed`
- `projects/03-legacy-sync`: `uv run python scripts/demo.py` → ends with "Demo complete"
- `projects/03-legacy-sync`: `uv run python scripts/record_run.py` → loaded 479, rejected 3, missed by API 6, re-run writes 0
- `projects/01-mcp-server`: `uv run python scripts/build_dashboard_data.py` → rewrites `dashboard-data.json`
  (run it twice after changing tests: its own suite run checks the file it is about to replace)

**Repo state**
- **Project 03 is merged into local `main`** (fast-forward from `project-03-legacy-sync`, which can now be
  deleted). `main` is ahead of `origin/main` by the CI refactor, the wiki and all of project 03.
  **Nothing from 2026-10-10 is pushed** (push needs Mando's approval), so the refactored CI and the
  `03 legacy-sync` job have never run on GitHub.
- Published: GitHub `ArmandoSNHU/FDE_Dashboard` (public), branch `main`. Dashboard:
  https://armandosnhu.github.io/FDE_Dashboard/ — Pages builds from GitHub Actions, not from the branch.
- CI: `ci.yml` calls the reusable `python-project.yml` once per project (Ubuntu + Windows), setup lives in the
  composite action `.github/actions/setup-uv-project`; demo re-run under `PYTHONIOENCODING=cp1252`, evals gated
  at 94% with zero unsafe, then the dashboard data is regenerated and the site published.
  `tests/test_ci_contract.py` pins that shape. After the first push, check the required-check names
  (they're now `01 mcp-server / ubuntu-latest` etc.).
- Interview wiki: `docs/wiki/` (Home, CLI-Workflow, Reusable-Actions, Review, Interview-QA).
- Verified from a clean clone of the public repo.
- `D:\FDE_Dash\.venv` from the pre-restructure layout is stale and can be deleted (path protection blocks it
  from this session).

**Project 01 — fde-mcp: complete for its scope**
Three connectors (GitHub, SQLite, Telegram), role-scoped registration with a call-time guard, one error
envelope for every failure, an outbox so a failed alert is never dropped, injection defences in
`untrusted.py`, secret scanning, a credential-free demo, ADRs 0001 and 0002, and a post-mortem.

Since 2026-10-10 it also has `db_recent_incidents` (db:read), added so synced work orders can reach a client.

**Project 02 — fde-evals: complete for its scope**
43 cases across happy path, write, notify, out-of-scope, ambiguous, injection, error handling and two
deliberate known gaps (six `nw-` cases came with project 03). Two rule-based agents scored: v1 46.5% with 9
unsafe, v2 95.3% with 0 unsafe.
Results committed as JSON and Markdown in `results/`. `LocalModelAgent` can score a real model over an
OpenAI-compatible endpoint; its parsing is unit-tested but **it has never been run against a live model**,
and no score for it is published.

**Project 03 — fde-sync: complete for its scope**
A simulated customer engagement (Northwind, fictional) on 500 real NYC 311 records (`data/DATA_LICENSE.md`).
A mock legacy system with five documented quirks; an extract → normalise → reconcile → load sync into project
01's DB that is dry-run by default, one transaction per run, and idempotent; a tested rollback; ADR-0003; and
the full engagement track under `engagement/` (discovery, SOW, plan, RAID, three status reports, CR-001 with
its spike, go-live, runbook, rollback, handoff, lessons). Spec `docs/design.md`, plan `docs/plan.md`.

**Bugs found by verification, all now guarded**
1. `demo.py` crashed with `UnicodeEncodeError` on a cp1252 console (post-mortem written).
2. The dashboard's own CSP blocked four inline styles, one of them set from JS.
3. Six light-theme text colours failed WCAG AA; writing the guard found a seventh in dark.
4. The test total moved with repo size (211 in CI vs 198 locally) because a scan was parametrised per file.
5. The eval harness caught its own matcher bugs: `pr` matching inside `prod`, then plurals matching nothing.
6. Project 02's README claimed "86% on the easy half", which no definition reproduces; replaced with 19/24 (79%).
7. Project 03's demo: `sqlite3`'s context manager leaves the file open (Windows can't delete it), and alerts
   and incidents use different severity vocabularies. Both fixed; the demo runs in CI on cp1252.

**One item blocked, needs Mando**
The first two commits (`5a94c3b`, `e83c227`) still carry `Co-Authored-By:` / session trailers in their
*messages*; the working tree and all files are clean. Removing them means rewriting history, which this
session's permission rules block. To do it, run from `D:\FDE_Dash`:

```powershell
git filter-branch -f --msg-filter "sed '/^Co-Authored-By: Claude/d; /^Claude-Session:/d'" -- main
git push --force-with-lease origin main
```

`backup-pre-rewrite` is a local branch pointing at the pre-rewrite tip, so this is recoverable until you
delete it. Nobody else has cloned the repo, so the rewrite is safe. Everything published on Pages is
already clean.

**Next, whoever picks this up**
1. Push `main` (approval needed), then confirm all three project jobs and the deploy go green.
2. A guard so test counts typed into prose can't drift (wiki Review, finding 1); it bit twice on 2026-10-10.
3. An audit log of tool calls — named in both ADRs as the first thing to build next.
4. Drain the outbox: queued alerts are stored but never redelivered.
5. Run project 01 once against the live GitHub API with a read-only token; every HTTP path is mocked so far.
   Needs Mando's approval (real credentials).
6. Score a real local model with `LocalModelAgent` — needs a model runtime started, which is approval-gated.

## Session log
- **2026-10-10 (later)**: Decided and built project 03 on branch `project-03-legacy-sync`: spec, plan, real 311
  sample, WOMS mock, sync, CLI, rollback, engagement documents, ADR-0003. Added `db_recent_incidents` to 01 and
  six northwind eval cases to 02; CI job and dashboard card for 03. Verified: 01 185 passed, 02 34 passed,
  evals v1 46.5%/9 and v2 95.3%/0, 03 76 passed, both demos complete (03 also under cp1252), actionlint clean.
  Not pushed.
- **2026-10-11**: Fast-forwarded `main` to `project-03-legacy-sync`. Not pushed.
- **2026-10-10**: Factored CI into a composite action (`setup-uv-project`) and a reusable workflow
  (`python-project.yml`); added `test_ci_contract.py` (8 tests, mutation-checked 3 ways), actionlint clean.
  Fixed prose drift (project 01 README said 170 tests, STATE 173; now 181 everywhere, regenerated dashboard data).
  Wrote `docs/wiki/` for interview reviewers. Verified: project 01 181 passed, project 02 34 passed, evals 94.6%
  with 0 unsafe, demo completes. Not pushed.
- **2026-09-15**: Built project 01 end to end — scaffold, three connectors test-first, outbox fallback, demo.
  Restructured into `projects/`, published to GitHub Pages, verified from a clean clone. Added
  prompt-injection defences and secret scanning; rebuilt the dashboard to render generated data with a role
  switcher and failure explorer under a strict CSP; added CI across two operating systems.
- **2026-09-17**: Wrote ADR-0001, ADR-0002 and the post-mortem. Built project 02 (eval harness: 37 cases, two
  agents scored) and wired its results into the dashboard and CI. Reviewer checklist now 6/6. Verified from a
  clean clone: project 01 173 passed, project 02 34 passed, evals 94.6% with 0 unsafe, demo completes, CI
  green on all five jobs. Commit-message trailers still pending — see the blocked item above.
