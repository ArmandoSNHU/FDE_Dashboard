# Review

Two reviews in one page. The first covers the change that factored CI into reusable pieces, written the
way I'd want a PR reviewed. The second steps back to the pipeline and the portfolio as a whole. Both list
what's weak, not just what works.

**Date:** 2026-10-10 · **Reviewer:** Armando Gomez

---

## Part 1: the reusable-CI change

### What changed

| File | Change |
|---|---|
| `.github/actions/setup-uv-project/action.yml` | **new.** Composite action: uv install (cache keyed per lockfile) + `uv sync --frozen` |
| `.github/workflows/python-project.yml` | **new.** Reusable workflow: one project × {Ubuntu, Windows}, pytest, `checks`, optional cp1252 re-run |
| `.github/workflows/ci.yml` | 3 hand-written jobs → 2 calls to the reusable workflow + the deploy job (‑73 / +29 lines) |
| `projects/01-mcp-server/tests/test_ci_contract.py` | **new.** 8 tests pinning the CI shape |
| `scripts/build_dashboard_data.py` | labels the new suite on the dashboard |

### Behaviour preserved

Every command the old pipeline ran still runs, on the same operating systems:

| Old step | New home | Same OS coverage |
|---|---|---|
| pytest (01) | reusable → `Run the test suite` | ✓ both |
| demo.py (01) | `ci.yml` → `checks` | ✓ both |
| demo.py on cp1252 (01) | `ci.yml` → `legacy-console-check` | ✓ Windows only, as before |
| smoke_stdio.py (01) | `ci.yml` → `checks` | ✓ both |
| pytest (02) | reusable → `Run the test suite` | ✓ both |
| `fde-evals --check` (02) | `ci.yml` → `checks` | ✓ both |
| deploy: rescore, generate, publish | unchanged apart from setup | ✓ |

### Verification

| Check | Result |
|---|---|
| `uv run pytest -q` (01) | `181 passed` (173 before + 8 new) |
| `uv run pytest -q` (02) | `34 passed` |
| `uv run fde-evals --check` | `OK: v2 at 94.6% with 0 unsafe decisions` |
| demo and smoke_stdio | `Demo complete`; viewer can't see `telegram_send_alert`, oncall sees all 6 tools |
| `actionlint` over `.github/` | no findings |
| Mutation check on the contract | 3 deliberate breaks in `ci.yml`, each caught by exactly the intended test |

**Not yet verified: a real run on GitHub.** actionlint and the contract test check the structure, but the
first push is the real test. That push is approval-gated, so this stays at a local commit until it's approved.

### Risks and how they're handled

1. **CI check names changed.** `tests (ubuntu-latest)` is now `01 mcp-server / ubuntu-latest`. If a branch
   protection rule requires the old names, PRs will wait forever on a check that never reports. *Action:*
   update the required checks after the first green run. (No such rule exists on this repo today.)
2. **The Windows test step now runs under bash instead of pwsh.** That was needed so a failure on any line
   of a multi-line `checks` input fails the job. The cp1252 re-run still sets the encoding through the
   environment, which works the same in either shell.
3. **`eval` of a workflow input.** The workflow executes its `checks` input by design, so the input is
   trusted code. Here the only caller is this repo's `ci.yml`. Another repo could call this public workflow
   by its full path, but it would run in *that* repo's context, with that repo's token and permissions, so
   it gains nothing here. Inputs pass through `env` rather than being interpolated into the script, so
   values with quotes or `$(...)` can't break out of the step.
4. **The contract test reads YAML as text.** It's simple and has no dependencies, but a legal YAML
   restyling (flow-style `needs`, reordered keys) could break the test without breaking CI. That fails
   loudly rather than silently, which is the right direction. If it gets annoying, switch to a real parser.

---

## Part 2: the pipeline and portfolio as a whole

### What holds up

- **The numbers can't drift from the code.** The dashboard is generated from a real run in the same
  pipeline that publishes it, behind gates for both tests and evals.
- **Safety is measured separately from accuracy.** The eval harness reports *unsafe* decisions next to the
  pass rate, and CI fails on even one.
- **Verification happens outside my environment.** Clean clone, two operating systems, a hostile console
  encoding. Each of those caught a real bug ([post-mortem](../../projects/01-mcp-server/docs/postmortems/2026-09-15-demo-crash-on-legacy-console.md)).
- **Decisions record their cost.** Both ADRs list the rejected options and what the chosen option gives up.

### Findings

| # | Severity | Finding | Recommendation |
|---|---|---|---|
| 1 | medium | **Prose test counts had drifted.** Project 01's README said 170 while STATE said 173. Generated numbers are guarded; numbers typed into prose aren't. Fixed to 181 in this change. | Add a test asserting every `NNN passed` in the READMEs and `STATE.md` matches the generated `dashboard-data.json` |
| 2 | medium | **Third-party actions are pinned by major tag** (`@v4`), not commit SHA. A retagged or compromised action would run with `pages: write`. | Pin to SHAs and let Dependabot propose bumps; essential before any customer deployment |
| 3 | medium | **Live integrations are untested.** Every GitHub and Telegram path runs against a mocked transport. | One read-only run against the real GitHub API with a fine-grained token, recorded as evidence (approval-gated) |
| 4 | medium | **Nothing drains the alert outbox.** A failed alert is stored safely but never redelivered. | Retry worker with backoff and an attempts column; the outbox table already exists |
| 5 | low | **No audit log of tool calls.** Both ADRs name it as the next thing to build. | Append-only log of role, tool, args hash, result kind |
| 6 | low | **The eval gate leaves little headroom** (94% vs 95.3% after the northwind cases). One new honest case could fail CI. | Intentional ratchet. When adding cases, update the threshold and the README in the same commit |
| 7 | low | **The deploy job runs the suite a third time** (via the generator). | Accept it: the published numbers have to come from the commit being published. Revisit if CI time matters |
| 8 | info | **No score from a real model.** `LocalModelAgent` is unit-tested but has never been run live. | Run a local ~7B model once and publish it with the model, quantisation and temperature |

### What I'd do next, in order

1. Push and confirm the new pipeline is green on GitHub, then update any required-check names.
2. Finding 1: the prose-count guard. It's cheap and closes the exact gap that let 170 vs 173 slip through.
3. Finding 2: SHA-pin the actions.
4. ~~Project 03~~ Done: [`projects/03-legacy-sync`](../../projects/03-legacy-sync/). Its phase 2 list is in its [handoff](../../projects/03-legacy-sync/engagement/handoff.md).
