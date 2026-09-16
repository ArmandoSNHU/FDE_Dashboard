# FDE Portfolio — Armando Gomez

**[Live dashboard →](https://armandosnhu.github.io/FDE_Dashboard/)**

Forward Deployed Engineering work in public. The theme across these projects is the unglamorous part of
shipping into someone else's environment: what happens when a source is down, who is allowed to call what,
and whether an alert that fails is actually lost. Every status below is backed by a command you can run.

## For a reviewer with five minutes

1. **[The dashboard](https://armandosnhu.github.io/FDE_Dashboard/)** — status of every piece, and the evidence behind each claim.
2. **[Project 01 README](projects/01-mcp-server/)** — the problem, why these three sources, how auth works per source, and the failure/degradation table.
3. **Run the demo** (no credentials, no network): `cd projects/01-mcp-server && uv sync && uv run python scripts/demo.py`
4. **[Acceptance criteria](projects/01-mcp-server/#acceptance-criteria)** — what "done" means, and the test that proves each line.

## Projects

| # | Project | What it demonstrates | Status |
|---|---|---|---|
| 01 | [MCP server: GitHub + SQLite + Telegram](projects/01-mcp-server/) | Role-scoped tool access, per-source failure isolation, side effects off by default, alerts that survive an outage | **Working** — 3 connectors, 107 tests, runnable demo |
| 02 | Evaluation framework | 20+ cases over happy path, messy input, out-of-scope and refusal; committed before/after pass rates | Queued |
| 03 | Enterprise integration under real constraints | Undocumented behaviour, inconsistent data, stakeholder impact | Queued |
| 04 | Architecture Decision Record | Rejected options, what the choice cost, what I'd revisit | [Template ready](projects/01-mcp-server/docs/adr/) |
| 05 | Production post-mortem | Root cause beyond "the code was buggy", and prevention | [Template ready](projects/01-mcp-server/docs/postmortems/) |

## Layout

```
index.html                  portfolio dashboard (static, no build step; served by GitHub Pages)
projects/01-mcp-server/     project 1: fde-mcp (own README, tests, docs)
STATE.md                    current state and restart point for the whole portfolio
```

## Run project 01

```powershell
cd projects/01-mcp-server
uv sync
uv run python scripts/demo.py          # scripted incident against the real server
uv run pytest -q                       # 107 passed
uv run python scripts/smoke_stdio.py   # tool visibility per role
```

---

Armando Gomez · [github.com/ArmandoSNHU](https://github.com/ArmandoSNHU)
