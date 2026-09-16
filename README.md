# FDE Portfolio — Armando Gomez

Forward Deployed Engineering work in public: integrations that fail safely, evaluations that aren't vibes,
and write-ups that defend the decisions. Each project is self-contained under `projects/`.

**[Dashboard](dashboard/index.html)** — status of every piece, with the verification evidence behind each claim.

| # | Project | What it demonstrates | Status |
|---|---|---|---|
| 01 | [MCP server: GitHub + SQLite + Telegram](projects/01-mcp-server/) | Role-scoped tool access, per-source failure isolation, side effects off by default | **Building** — scaffold done, 27 tests passing, connectors are skeletons |
| 02 | Evaluation framework | 20+ cases over happy path, messy input, out-of-scope and refusal; committed before/after pass rates | Queued |
| 03 | Enterprise integration under real constraints | Undocumented behaviour, inconsistent data, stakeholder impact | Queued |
| 04 | Architecture Decision Record | Rejected options, what the choice cost, what I'd revisit | [Templates ready](projects/01-mcp-server/docs/adr/) |
| 05 | Production post-mortem | Root cause beyond "the code was buggy", and prevention | [Templates ready](projects/01-mcp-server/docs/postmortems/) |

## Layout

```
dashboard/index.html        portfolio dashboard (static, no build step)
projects/01-mcp-server/     project 1: fde-mcp (own README, tests, docs)
STATE.md                    current state and restart point for the whole portfolio
```

## Run project 01

```powershell
cd projects/01-mcp-server
uv sync
uv run pytest -q                       # 27 passed
uv run python scripts/smoke_stdio.py   # live server, per role, no credentials needed
```
