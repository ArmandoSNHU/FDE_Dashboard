# fde-sync — agent instructions

## Mission
Project 3 of the FDE portfolio: a sync from a legacy work-order system (a mock built on real NYC 311 data)
into project 01's ops DB, presented as a simulated customer engagement. Run every command from this directory.

## Read order
1. `../../STATE.md`: repo-wide state and Restart Point. **It wins over anything else.**
2. `README.md`, then `docs/design.md` (the spec) and `engagement/README.md`.

## Commands
```powershell
uv sync
uv run pytest -q                       # full suite
uv run python scripts/demo.py          # end to end, including fde-mcp over stdio
uv run python scripts/record_run.py    # rewrites results/sync-run.json (the dashboard reads it)
```

## Architecture
| Module | Role |
|---|---|
| `legacy/woms.py` | The mock customer system: quirks Q1–Q5, one seed |
| `normalise.py` | Raw record -> `WorkOrder` or `Rejected`; never guesses |
| `extract.py` | Bounded retries on the API; reads the export |
| `reconcile.py` | Pure decisions; the export is the source of truth (ADR-0003) |
| `load.py` | The only writer; one transaction per run |
| `store.py`, `schema.sql` | Additive tables in project 01's DB |
| `sync.py`, `cli.py`, `report.py` | Orchestration, CLI, the ASCII report |

## Gotchas
- `sqlite3`'s context manager commits but does not close; use `contextlib.closing` where a file must be released (Windows).
- The Q3 code change is one instant (midnight New York), shared by the mock and `normalise.py`.
- Engagement docs are checked by `tests/test_docs_contract.py`: cited tests must exist, and the outcome table must match `results/sync-run.json`.
- Scripts must stay cp1252-printable (`tests/test_scripts_portable.py`).

## Done means
Suite passes with the count reported, the demo ends with "Demo complete", `results/sync-run.json` is fresh,
and the root README, `STATE.md` and the dashboard agree.
