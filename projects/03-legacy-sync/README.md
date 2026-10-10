# fde-sync — a legacy work-order sync, run as a customer engagement

Project 3 of the [FDE portfolio](../../README.md). Run commands from this directory.

**Author:** Armando Gomez · **Status:** working — 76 tests, runnable demo, engagement documents complete

> **Simulated customer, real data.** Northwind Facility Services is fictional. Its work orders are 500 real
> NYC 311 service requests ([source and terms](data/DATA_LICENSE.md)).

## The problem

Northwind's on-call engineers can't see the company's work-order system (WOMS), so at 2am they phone the
dispatch manager to ask what's open. Northwind asked for the tickets to appear in the on-call platform
(project 01). Discovery found the real problem: **nobody trusts ticket status**, because WOMS behaves
differently from its own documentation in five ways:

| # | The API guide says | WOMS actually does | Handled by |
|---|---|---|---|
| Q1 | `wo_id` is unique | IDs restart per region | key on `region:wo_id` |
| Q2 | All timestamps are UTC | The API returns site-local times; only the export is UTC | convert from the region's zone |
| Q3 | Status codes `O`, `A`, `C` | `C` meant *cancelled* before 2024-07-01 and *closed* after; `H` exists | map codes by era; reject unknown codes |
| Q4 | Paging is stable | Records created during a read cause duplicates and get missed | collapse duplicates; recover misses from the export |
| Q5 | — | The API serves stale priorities | the export wins ([ADR-0003](docs/adr/0003-csv-is-source-of-truth.md)); every conflict is reported |

## What it does

```
WOMS (mock, real 311 data)            ops.db (project 01's file)
  paged API, flaky, local times  ─┐     incidents    (project 01 owns)
  nightly CSV export, UTC        ─┼─>   sync_ledger  (ours)        ─> fde-mcp serves it to the on-call engineer
                                  │     sync_runs    (ours)
              extract → normalise → reconcile → load (one transaction)
                                  └─>   data-quality report for the dispatch manager
```

- **Dry run by default.** `--apply` is the only way to write, and a dry run leaves the DB file byte-identical.
- **Reject, don't guess.** An unknown status, priority or date is rejected with a reason in the report.
- **Safe to re-run.** Each record's content hash lives in the ledger, so a second run over the same data
  writes nothing.
- **All or nothing.** A run is one transaction; a failure part way leaves the DB as it was.
- **Additive.** Two new tables in project 01's DB; project 01's tables are never altered.

## Run it

```powershell
uv sync
uv run python scripts/demo.py                    # dry run, apply, re-run, then fde-mcp reads the result
uv run pytest -q                                 # 76 passed
uv run fde-sync --db path/to/ops.db              # dry run: what would change
uv run fde-sync --db path/to/ops.db --apply --report report.md
uv run python scripts/record_run.py              # the numbers the dashboard shows
```

Exit codes: `0` ok, `3` partial (the API read was incomplete; everything still loaded from the export),
`1` failed (nothing written).

## The engagement

The scope, risks, weekly status reports, a change request with its spike, and the go-live and handoff
documents are in [`engagement/`](engagement/). Start with its [README](engagement/README.md).

## Layout

```
data/                      the real 311 sample and its terms
src/fde_sync/legacy/       the mock WOMS: five quirks, one seed
src/fde_sync/              normalise, extract, reconcile, load, report, cli
ops/rollback.sql           the tested rollback
scripts/                   demo, record_run, fetch_sample (network; run once by hand)
docs/                      design, plan, ADR-0003
engagement/                the customer engagement, week by week
```

## Limitations

- **The WOMS system is a mock.** It reproduces behaviour found in discovery; it isn't a real customer system.
- **Status lives in the incident summary.** Project 01's incident table has no status column; adding one is a
  change to project 01's contract, left for phase 2.
- **Records only the API has wait for the next export**, so the on-call view can be up to a day behind.
- **Nothing is ever deleted.** A work order removed from WOMS keeps its last known state as an incident.
- **The CLI reads the mock WOMS by default.** Pointing it at a real system means replacing `fde_sync.legacy`
  with a client for that system, behind the same two calls: `api_page` and `csv_export`.
