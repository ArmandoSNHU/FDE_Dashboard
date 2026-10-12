# Status: week 3, go-live

**To:** Dana Whitfield · **Cc:** Luis Ortega, Ray Kowalski, Priya Natarajan · **Overall: 🟢 green**

## Done

- **The on-call engineer can see Northwind's work orders** through the ops platform, scoped by role
  (`1646038`). The platform gained a read path for incidents (`3dc25fb`), which resolves last week's amber.
- Go-live run, recorded in `../../results/sync-run.json`: **479 loaded, 18 skipped as cancelled, 3 rejected,
  6 recovered from the export; the re-run wrote 0 rows.**
- Hostile text planted in a work-order description reaches the on-call assistant visibly, but without its
  hidden characters (AC7).
- The rollback is tested: it removes everything the sync wrote and nothing else (`../rollback.md`, AC8).
- All eight acceptance criteria are met, each by a named test. 76 tests pass in the sync project.

## Handoff

- Runbook, rollback and handoff documents delivered. Ray is the named owner of the status-code mapping.

## Open items for phase 2

1. Technician spreadsheet ingestion (CR-001), once the Region column exists.
2. A status column in the platform's incident table (RAID I2), to replace status-in-summary.
3. One severity vocabulary across incidents and alerts (RAID I3).

## Asks

- **Luis:** the 3 rejected records are listed in the first report; they need fixing in WOMS.
