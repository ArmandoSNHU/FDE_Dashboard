# Runbook: fde-sync at Northwind

For whoever looks after the sync once the engagement ends. Commands run from `projects/03-legacy-sync`.

## What it does

Every night after the 06:00 UTC export, it reads WOMS (API and export), works out what changed, and writes
new and changed work orders into the ops DB as incidents for `northwind`. It never writes to WOMS and never
deletes anything.

## Running it

```powershell
uv run fde-sync --db D:\ops\ops.db                          # dry run: shows what would change, writes nothing
uv run fde-sync --db D:\ops\ops.db --apply --report run.md  # write, and save the data-quality report
```

`FDE_DB_PATH` can replace `--db`. `--export PATH` points at a specific export file. Without it, the command
reads the mock WOMS in this repo.

## Exit codes

| Code | Meaning | What to do |
|---|---|---|
| `0` | ok | Nothing. Luis reads the report when it suits him |
| `3` | partial: the API read gave up, but everything still loaded from the export | Nothing is lost. If it happens two nights running, ask Northwind IT about API load |
| `1` | failed: nothing was written | Read the error line. Usually the export is missing or the DB path is wrong |

## Scheduling

Run it from Northwind's scheduler at 06:30 UTC, after the export has landed. Alert on exit code `1`, and on
`3` if it repeats.

## Health checks

```sql
-- the last five runs: when, outcome, and what they did
SELECT started_at, outcome, counts_json FROM sync_runs ORDER BY id DESC LIMIT 5;
```

A dry run right after an apply should report `new 0, changed 0`. If it doesn't, something changed WOMS in
between, which is normal during the day.

## Common situations

| Situation | Cause | Fix |
|---|---|---|
| Report lists `unknown status 'Z'` | Someone typed a letter WOMS shouldn't accept | Fix the record in WOMS; the next run picks it up |
| A new status letter appears for every record | WOMS changed its codes again (as on 2024-07-01) | Ray updates the mapping in `normalise.py`; until then those records are rejected, not guessed |
| `ops DB not found` | Wrong path, or the DB moved | Fix the path. The sync never creates a DB |
| `database is locked` | Another writer holds the ops DB | Re-run; the failed run wrote nothing |

## Undoing it

See `rollback.md`.
