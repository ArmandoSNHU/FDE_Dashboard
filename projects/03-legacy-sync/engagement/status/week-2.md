# Status: week 2

**To:** Dana Whitfield · **Cc:** Luis Ortega · **Overall: 🟡 amber**, on schedule, scope question decided

## Done

- The sync runs end to end in dry-run mode (`6e4b38f`). On the full sample:
  **479 work orders would load, 18 cancelled ones are skipped, 3 are rejected with reasons, 6 that the API
  missed are recovered from the export, and 20 disagree between the API and the export** (the export wins,
  per ADR-0003).
- A second run over the same data writes nothing, and a failure part way through rolls back the whole run.
- The data-quality report renders for Luis: counts, the 3 rejects with reasons, and every disagreement.

## Change request

- **CR-001: the technician spreadsheet** (`../change-requests/CR-001.md`). Ray's completion sheet is more
  accurate than WOMS for completion times. A half-day spike showed it **can't be joined on the work-order
  number alone (60 of 60 rows ambiguous)**, but it can be joined on number plus site (60 of 60 unique).
  **Decision: defer to phase 2**, with one ask of Northwind (below). Go-live date unchanged.

## Why amber

- The ops platform can store incidents but can't currently *read* them back to the on-call engineer (RAID
  I1). It's a platform-side fix and it's ours; scheduled for week 3. If it slips, go-live slips with it.

## Next week

- Platform read path, end-to-end test through the on-call platform, go-live checklist, handoff.

## Asks

- **Luis:** add a Region column to the technician spreadsheet. It turns phase 2's join from "number + typed
  address" into an exact key.
- **Northwind IT:** schedule a copy of the ops DB on go-live morning (DEP3).
