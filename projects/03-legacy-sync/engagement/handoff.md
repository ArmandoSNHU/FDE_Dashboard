# Handoff

What Northwind owns from today, who owns each part, and where to look when something changes.

## Owners

| Area | Owner | Why them |
|---|---|---|
| Running the sync and reading its exit code | Northwind IT | They own the scheduler |
| Reading the data-quality report and fixing rejected records in WOMS | Luis Ortega | The report is written for him |
| **The status-code mapping** (`src/fde_sync/normalise.py`) | **Ray Kowalski** | He found D1 and D2. He'll be first to know when WOMS changes again |
| Access to WOMS and the data path | Priya Natarajan | Read-only, local-only (D7, D8) |

## Where things are

| Need | Look at |
|---|---|
| How to run it, exit codes, health checks | `runbook.md` |
| How to undo it | `rollback.md` |
| Why the export beats the API | `../docs/adr/0003-csv-is-source-of-truth.md` |
| Why each rule in the code exists | `discovery-notes.md`, findings D1–D8 |
| What was promised and how it's proven | `sow.md`, acceptance criteria AC1–AC8 |

## Known limitations at handoff

1. **Status lives in the incident summary**, as `[TRADE][status] ...`, because the platform's incident table has
   no status column (RAID I2).
2. **The technician spreadsheet isn't used yet** (CR-001). It needs a Region column first.
3. **A record that only the API has waits for the next export.** The export is the source of truth, so the
   sync doesn't load from the less reliable source.
4. **Nothing is ever deleted.** If WOMS deletes a work order, its incident stays, showing its last known
   status.

## Phase 2, in order

1. Technician spreadsheet, keyed on `(region, wo_id)` once the column exists.
2. A status column in the platform's incident table.
3. One severity vocabulary across incidents and alerts.
