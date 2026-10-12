# STATE — FDE Portfolio

Single state file for the whole repo. Project-level detail lives in each project's README and AGENTS.md.

## Restart Point (2026-10-12) — safe point `safe-point-2026-10-12`

**Where things stand, in one breath:** all three projects are built and green, on local `main` and in PR #3
(all six CI checks pass on GitHub). Nothing new is on GitHub's `main` yet, because branch protection still
requires five check names the refactored CI no longer produces. Mando paused the push on 2026-10-12.
Next work, once he says go: publish (below), then score a real local model (decided, below).

**To get back to this exact point:** `git switch main && git reset --hard safe-point-2026-10-12` (only if
`main` was damaged; check `git status` first; a dirty tree is handoff work, never discard it).

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
- **Local `main` is 16 commits ahead of `origin/main`**: the CI refactor, the wiki, all of project 03 and
  STATE updates. Mando's history rewrite already landed on GitHub (`origin/main` = `3d51d12`, no trailers left;
  files identical to the old `974ab0a`), and the 16 commits were rebased onto it.
- **PR #3** (`project-03` → `main`, head = local `main`) is open. All six checks passed on 2026-10-12;
  `publish dashboard` is skipped on PRs by design. It is **blocked** only because `main`'s protection still
  requires `tests (ubuntu-latest)`, `tests (windows-latest)`, `evals (ubuntu-latest)`, `evals (windows-latest)`
  and `dependency-audit`. None of these is produced by any workflow any more (`dependency-audit` never was).
  Protection also requires a PR (0 approvals) and applies to admins, so a direct or forced push is rejected.
- **To publish (Mando runs it; settings changes and merges are blocked for agents):**
  ```powershell
  gh api -X PUT repos/ArmandoSNHU/FDE_Dashboard/branches/main/protection/required_status_checks/contexts -f "contexts[]=01 mcp-server / ubuntu-latest" -f "contexts[]=01 mcp-server / windows-latest" -f "contexts[]=02 eval-harness / ubuntu-latest" -f "contexts[]=02 eval-harness / windows-latest" -f "contexts[]=03 legacy-sync / ubuntu-latest" -f "contexts[]=03 legacy-sync / windows-latest"
  gh pr merge 3 --repo ArmandoSNHU/FDE_Dashboard --merge
  git pull --ff-only
  ```
  `--merge` keeps the 16 commits' hashes, so local `main` fast-forwards. Never `git pull` without
  `--ff-only` against an old history: it would bring the trailer commits back.
- Local branches: `backup-pre-rebase` (local `main` before the rebase onto the rewritten history) and
  `project-03-legacy-sync` (pre-rebase hashes) are stale safety copies; delete them once PR #3 is merged.
  `backup-pre-rewrite` can go too, now that the rewrite is on GitHub.
- Published: GitHub `ArmandoSNHU/FDE_Dashboard` (public), branch `main`. Dashboard:
  https://armandosnhu.github.io/FDE_Dashboard/ — Pages builds from GitHub Actions, not from the branch.
- CI: `ci.yml` calls the reusable `python-project.yml` once per project (Ubuntu + Windows), setup lives in the
  composite action `.github/actions/setup-uv-project`; demo re-run under `PYTHONIOENCODING=cp1252`, evals gated
  at 94% with zero unsafe, then the dashboard data is regenerated and the site published.
  `tests/test_ci_contract.py` pins that shape. Check names are `<NN slug> / <os>`, e.g.
  `01 mcp-server / ubuntu-latest`; renaming a job means updating branch protection too.
- Interview wiki: `docs/wiki/` (Home, CLI-Workflow, Reusable-Actions, Review, Interview-QA) is the source.
  The GitHub wiki (https://github.com/ArmandoSNHU/FDE_Dashboard/wiki) is enabled but **empty**: GitHub only
  creates its git repo after a first page is saved in the browser. To publish a copy, rewrite links
  (`Page.md` → `Page`; `../../path` → `https://github.com/ArmandoSNHU/FDE_Dashboard/blob/main/path`, `tree/`
  for directories), add a `_Sidebar.md` listing the five pages, then clone `FDE_Dashboard.wiki.git`, copy,
  commit, push. Do it after PR #3 merges, or the project 03 links 404.
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

**Resolved: commit-message trailers.** Mando rewrote history on GitHub; `origin/main` has no trailers
(checked 2026-10-12), and none of the 16 new commits carries any.

**Decided 2026-10-12 — why the next work is what it is**
The FDE role breaks into AI engineering, AI system design and customer craft; plus integrating, deploying
and explaining to executives. Mapped against the portfolio: customer craft, integration and system design are
covered (project 03 engagement, three ADRs). The visible gap is **no real model has ever run in the
pipeline** (both scored agents are rule-based). Second gap: nothing written for an executive audience.

**Next, in order (each needs Mando's go-ahead to start)**
1. **Publish:** the three commands under "Repo state", then confirm `publish dashboard` runs green on `main`
   and the dashboard shows project 03. Then the GitHub wiki copy (see "Interview wiki").
2. **Score a real local model.** Decided model: **Gemma 4 E4B, QAT Q4_0 GGUF**, via Ollama:
   `hf.co/google/gemma-4-E4B-it-qat-q4_0-gguf:latest` (5.15 GB, fits the RTX 2070's 8 GB; Apache 2.0).
   Already pulled, and Ollama serves it at `http://localhost:11434`. A one-case smoke test returned correct
   JSON (`{"action": "call", "tool": "db_recent_incidents"}`) in 28 s, so 43 cases take ~20 min.
   Rejected: the 27B 2-bit model (doesn't fit in VRAM; 2-bit hurts tool choice) and the `-unquantized` repo
   (~16 GB safetensors, not an Ollama format). A cloud model is an option later; it needs approval per run.
   **Fix the harness first (TDD):** `LocalModelAgent.decide` turns "model unreachable" and "named a tool it
   wasn't offered" into `refuse`, and refusals score as passes on out-of-scope cases, so a dead model would
   look safe. Make both count as failures (tool-hallucination should count as unsafe), then add a
   `--local-model NAME [--base-url URL]` option to `fde-evals` writing `results/v3-local-model.*`.
   Keep it **out of the CI gate** (no GPU in CI); record the run as a committed result, like
   `record_run.py` does. Update the `LocalModelAgent` docstring, README, wiki and dashboard together.
   Open question for Mando: results must name the model tested; we read the no-vendor rule as being about
   *attribution*, not naming a model under evaluation. Confirm before publishing.
3. **Executive brief for project 03:** one page (or five slides): problem, what discovery found, outcome in
   numbers from `results/sync-run.json`, risk retired, phase 2. Audience: Dana (VP Operations).
4. Optional, "deploying it" made literal: a Windows Task Scheduler registration script for the sync, plus the
   runbook update.

**Backlog**
- A guard so test counts typed into prose can't drift (wiki Review, finding 1); it bit twice on 2026-10-10.
- An audit log of tool calls — named in both ADRs as the first thing to build next.
- Drain the outbox: queued alerts are stored but never redelivered.
- Run project 01 once against the live GitHub API with a read-only token; every HTTP path is mocked so far.
  Needs Mando's approval (real credentials).
- Project 03's deferred minors: the CLI default sample path only works from an editable install; a partial API
  outage is reported as "missed by the API"; a hand-deleted incident makes the next update write 0 rows
  silently; reject reasons echo the raw status value.

## Session log
- **2026-10-10 (later)**: Decided and built project 03 on branch `project-03-legacy-sync`: spec, plan, real 311
  sample, WOMS mock, sync, CLI, rollback, engagement documents, ADR-0003. Added `db_recent_incidents` to 01 and
  six northwind eval cases to 02; CI job and dashboard card for 03. Verified: 01 185 passed, 02 34 passed,
  evals v1 46.5%/9 and v2 95.3%/0, 03 76 passed, both demos complete (03 also under cp1252), actionlint clean.
  Not pushed.
- **2026-10-11**: Fast-forwarded `main` to `project-03-legacy-sync`. Not pushed.
- **2026-10-12**: Push rejected twice: first by the rewritten history (rebased the 16 commits onto it), then by
  branch protection. Opened PR #3; its CI is the first run of the reworked workflows, and all six checks
  passed. Publishing paused by Mando; the commands are recorded above. Decided the next work (real local model,
  executive brief) and pulled the Gemma model; verified it with one request. Safe point tagged
  `safe-point-2026-10-12` (local tag). Verified on `main`: 01 185 passed, 03 76 passed.
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
  green on all five jobs. Commit-message trailers were pending then (since resolved).
