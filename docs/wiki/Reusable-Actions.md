# Reusable Actions

CI is built from two reusable pieces and one short caller. Each project used to have its own hand-copied job.
Now a project is a 6-line entry in `ci.yml`, and a test fails if a project is missing one.

```
.github/
  actions/setup-uv-project/action.yml   composite action: install uv, sync one project from its lockfile
  workflows/python-project.yml          reusable workflow: one project, Ubuntu + Windows, tests + checks
  workflows/ci.yml                      caller: one job per project, then publish the dashboard
```

```
ci.yml
 ├─ 01 mcp-server ──uses──> python-project.yml ──uses──> setup-uv-project
 │                            ├─ ubuntu-latest:  pytest, demo, smoke_stdio
 │                            └─ windows-latest: pytest, demo, smoke_stdio, demo on cp1252
 ├─ 02 eval-harness ─uses──> python-project.yml ──uses──> setup-uv-project
 │                            ├─ ubuntu-latest:  pytest, fde-evals --check
 │                            └─ windows-latest: pytest, fde-evals --check
 ├─ 03 legacy-sync ──uses──> python-project.yml ──uses──> setup-uv-project
 │                            ├─ ubuntu-latest:  pytest, demo
 │                            └─ windows-latest: pytest, demo, demo on cp1252
 └─ publish dashboard  (needs all three, main only)
      setup-uv-project x3 -> record_run.py -> fde-evals -> build_dashboard_data.py -> deploy to Pages
```

## 1. Composite action: `setup-uv-project`

**Job:** get one project's environment into the exact state the lockfile describes.

| Input | Meaning |
|---|---|
| `working-directory` | project directory holding `pyproject.toml` and `uv.lock` |

What it does, and why:

- **Installs uv with caching keyed on that project's `uv.lock`.** The two projects have different
  dependencies. With one shared key, one project could restore the other's stale cache.
- **Runs `uv sync --frozen`.** If the lockfile is out of date, the step fails instead of re-resolving.
  CI installs exactly what was reviewed, not whatever PyPI happens to serve that day.
- **It's the only place the uv installer version is pinned.** A version bump is a one-line change, and
  `test_the_setup_tool_version_is_pinned_in_exactly_one_place` fails if a workflow starts installing uv
  directly again.

Why a composite action and not a reusable workflow? The deploy job needs the same setup *in the middle of
its own steps* (set up the projects, then record, score, generate and publish). A reusable workflow is a whole
job and can't be dropped in as a step. A composite action can.

## 2. Reusable workflow: `python-project.yml`

**Job:** test one project the same way on both operating systems.

| Input | Required | Meaning |
|---|---|---|
| `project-dir` | yes | e.g. `projects/01-mcp-server` |
| `checks` | no | extra commands after pytest, one per line, and any failing line fails the job |
| `legacy-console-check` | no | command re-run on Windows with `PYTHONIOENCODING=cp1252` |

Design choices worth defending:

- **`shell: bash` on both runners.** With a multi-line `checks` input under pwsh, only the *last* line's
  exit code decides the step, so a broken demo followed by a passing smoke test would go green. bash runs
  with `-e`, so every line counts.
- **Inputs go in through `env`, never interpolated into the script.** `run: ${{ inputs.checks }}` pastes
  text straight into a shell script, which is the textbook GitHub Actions injection shape. Here the inputs
  only come from this repo's own `ci.yml`, but the safe pattern costs nothing, so it's the default.
- **`fail-fast: false`.** If Windows fails, Ubuntu still finishes, so you see whether the problem is the
  platform or the code.
- **The cp1252 step is a first-class input**, not something special-cased for project 01. That console
  problem can hit any project with a script a reviewer runs, so any project can opt in.

## 3. The caller: `ci.yml`

Each project is a short block:

```yaml
  evals:
    name: 02 eval-harness
    uses: ./.github/workflows/python-project.yml
    with:
      project-dir: projects/02-eval-harness
      checks: uv run fde-evals --check
```

`publish dashboard` declares `needs: [mcp-server, evals, legacy-sync]` and runs only on `main`. It sets up all three projects, re-records the sync run,
re-scores the evals so the published numbers come from *this* commit, regenerates `dashboard-data.json`
from a real test run, and deploys to GitHub Pages.

## Adding a project

Project 03 was added exactly this way: one job in `ci.yml`, one name in `deploy.needs`.

1. Create `projects/<NN>-<slug>/` with a `pyproject.toml` and a committed `uv.lock`.
2. Add a 4–6 line job to `ci.yml` that uses `python-project.yml` with its `project-dir`.
3. Add the job name to `deploy.needs`.

Skip step 2 and project 01's suite fails with
`these projects have a pyproject.toml but no CI job: ['projects/04-...']`. Skip step 3 and
`test_publishing_waits_for_every_project` fails. You can't forget either one quietly.

## The contract that holds it together

`projects/01-mcp-server/tests/test_ci_contract.py` reads the workflow files as text (so it needs no YAML
dependency) and pins eight invariants:

| Test | Stops this from happening |
|---|---|
| `test_setup_is_one_composite_action_that_installs_from_the_lockfile` | CI quietly re-resolving dependencies |
| `test_the_reusable_workflow_is_callable_and_runs_on_both_operating_systems` | Windows coverage being dropped |
| `test_the_setup_tool_version_is_pinned_in_exactly_one_place` | Setup logic getting copy-pasted back into workflows |
| `test_every_project_is_tested_by_the_reusable_workflow` | A project shipping without CI |
| `test_the_legacy_console_guard_from_the_postmortem_is_still_wired` | The post-mortem's fix being refactored away |
| `test_the_evals_gate_still_blocks_a_regression` | The 94% / 0-unsafe gate being removed |
| `test_publishing_waits_for_every_project` | The site publishing before a project's tests pass |
| `test_there_are_projects_to_cover` | The coverage check passing because it found nothing to check |

I checked that the contract actually catches problems by breaking `ci.yml` three ways: dropping project
02's job, removing the cp1252 check, and letting deploy skip a project. Each break failed exactly the test
it should, and nothing else. The workflows also pass `actionlint`, which checks each caller's inputs against
the inputs the reusable workflow declares.
