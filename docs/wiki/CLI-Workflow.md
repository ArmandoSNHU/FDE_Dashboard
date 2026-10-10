# CLI Workflow

Everything in this repo is driven from the command line, and every command a reviewer runs locally is the
same command CI runs. That parity is the point: if it passes here, it passes there, and the reverse.

## Prerequisites

- [uv](https://docs.astral.sh/uv/). It installs the right Python and every dependency from the lockfile.
- Nothing else. No credentials, no network calls in tests, no model runtime.

## The loop

```
 clone ──> sync ──> test ──> run the demo ──> score the evals ──> regenerate the dashboard ──> commit
              ^                                                                                  │
              └────────────────────── CI repeats all of it on Ubuntu + Windows ──────────────────┘
```

### 1. Start from the state file

```powershell
Get-Content STATE.md        # the Restart Point lists the exact commands and expected outputs
```

`STATE.md` is the only state file in the repo, and if anything disagrees with it, `STATE.md` wins. Its
**Restart Point** says what to run and what you should see, so whoever picks the work up next (me in a
week, or someone else) checks the repo still reproduces before they change anything.

### 2. Project 01: the MCP server

```powershell
cd projects/01-mcp-server
uv sync                                  # environment from uv.lock
uv run pytest -q                         # 185 passed
uv run python scripts/demo.py            # scripted incident, ends with "Demo complete"
uv run python scripts/smoke_stdio.py     # real server over stdio, one per role: what each can see and call
uv run fde-mcp                           # run the server (stdio), role from FDE_MCP_ROLE
```

### 3. Project 02: the eval harness

```powershell
cd ../02-eval-harness
uv sync
uv run pytest -q                         # 34 passed
uv run fde-evals                         # score both agents, rewrite results/
uv run fde-evals --agent v2              # one agent
uv run fde-evals --check                 # the CI gate: exit 1 under 94% or on any unsafe decision
```

### 4. Project 03: the legacy sync

```powershell
cd ../03-legacy-sync
uv sync
uv run pytest -q                         # 76 passed
uv run python scripts/demo.py            # dry-run -> apply -> re-run (0 writes) -> fde-mcp reads northwind
uv run fde-sync --db path/to/ops.db      # dry run by default: shows what would change, writes nothing
uv run fde-sync --db path/to/ops.db --apply --report report.md
uv run python scripts/record_run.py      # the numbers the dashboard shows, from a real run
```

Exit codes are for a scheduler: `0` ok, `3` partial (the API read was incomplete but the export still
loaded), `1` failed (nothing written).

### 5. Regenerate the dashboard

```powershell
cd ../01-mcp-server
uv run python scripts/build_dashboard_data.py   # writes ../../dashboard-data.json from a real pytest run
```

The generator builds the real server for each role, runs the real error guard for each failure kind,
runs the real sanitiser over a real attack payload, and reads the counts from an actual JUnit report.
I never edit `dashboard-data.json` or a number in `index.html` by hand.

### 6. Update the docs together, then commit

If a status changed, `index.html`, the root `README.md` table and `STATE.md` change in the same commit.
The commit message says what changed, why, and the verification output (`185 passed`, `95.3% / 0 unsafe`).

## Local command ↔ CI step

| Local command | CI job / step | Where it's defined |
|---|---|---|
| `uv sync` (lockfile-exact) | `setup-uv-project` → `uv sync --frozen` | `.github/actions/setup-uv-project/action.yml` |
| `uv run pytest -q` | `Run the test suite`, every project, both OSes | `.github/workflows/python-project.yml` |
| `uv run python scripts/demo.py` | `01 mcp-server` → `checks` | `.github/workflows/ci.yml` |
| `uv run python scripts/smoke_stdio.py` | `01 mcp-server` → `checks` | `.github/workflows/ci.yml` |
| demo on a legacy code page | `Re-run on a legacy code page` (Windows, `PYTHONIOENCODING=cp1252`) | `python-project.yml`, input from `ci.yml` |
| `uv run fde-evals --check` | `02 eval-harness` → `checks` | `.github/workflows/ci.yml` |
| `uv run python scripts/demo.py` (03), also on cp1252 | `03 legacy-sync` → `checks`, `legacy-console-check` | `.github/workflows/ci.yml` |
| `uv run python scripts/record_run.py` (03) | `publish dashboard`, before the data is regenerated | `.github/workflows/ci.yml` |
| `uv run fde-evals` + `build_dashboard_data.py` | `publish dashboard` (main only, after every project passes) | `.github/workflows/ci.yml` |

## Verifying like a reviewer

Passing in my shell isn't enough. A demo once passed every local run and crashed on a stock Windows console
([post-mortem](../../projects/01-mcp-server/docs/postmortems/2026-09-15-demo-crash-on-legacy-console.md)).
Before I promote any status, I verify from a clean clone of the pushed repo:

```powershell
$tmp = Join-Path $env:TEMP "fde-verify"; git clone https://github.com/ArmandoSNHU/FDE_Dashboard $tmp
cd "$tmp/projects/01-mcp-server"; uv sync; uv run pytest -q; uv run python scripts/demo.py
$env:PYTHONIOENCODING = "cp1252"; uv run python scripts/demo.py   # the console I don't control
```

## Approval gates

Some commands have real side effects, so they're never run without the owner's go-ahead:

| Action | Default | Gate |
|---|---|---|
| Telegram send | `TELEGRAM_DRY_RUN=true` | a human sets it to `false` |
| GitHub API with a real token | every HTTP path mocked in tests | owner approval, read-only fine-grained token |
| Scoring a live model (`LocalModelAgent`) | never run, no score published | starting a model runtime needs approval |
| `git push` | stop at the local commit | owner approval |
