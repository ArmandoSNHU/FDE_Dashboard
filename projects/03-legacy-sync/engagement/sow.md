# Statement of work: WOMS → ops platform sync

**Customer:** Northwind Facility Services (simulated) · **Sponsor:** Dana Whitfield · **Engineer:** Armando Gomez

## Objective

The on-call engineer can see current, correct work-order status in the ops platform without calling anyone,
and every record that couldn't be read correctly is shown to a person instead of being guessed at. This comes
from the problem restatement in `discovery-notes.md`.

## In scope

1. A one-way sync from WOMS (the API and the nightly export) into the ops platform's incident store.
2. A data-quality report after every run, written for the Dispatch Manager.
3. A dry-run mode, which is the default, so any run can be previewed.
4. Operating documents: runbook, rollback, go-live checklist, handoff.

## Out of scope

- Writing anything back to WOMS (IT Security, D7).
- Deleting incidents. Closed and cancelled work stays visible, with its status.
- Scheduling. The customer runs the command from their own scheduler; the runbook lists the exit codes.
- The technician completion spreadsheet (see CR-001).
- Fixing data inside WOMS. The report lists what needs fixing; Northwind's team fixes it.

## Acceptance criteria

| # | Criterion | How it's proven |
|---|---|---|
| AC1 | Every documented and discovered WOMS behaviour (Q1–Q5) is handled | `tests/test_woms.py` pins each quirk; `tests/test_sync.py::test_the_plan_reflects_every_quirk_in_the_real_sample` |
| AC2 | No record is loaded with a guessed value; every reject has a reason in the report | `tests/test_normalise.py`; `test_the_report_names_every_reject_and_conflict_in_plain_ascii` |
| AC3 | Running twice changes nothing the second time | `test_apply_loads_and_a_second_apply_writes_nothing` |
| AC4 | A dry run writes nothing | `test_a_dry_run_writes_nothing_even_to_an_unmigrated_db` (the file is byte-identical) |
| AC5 | A failed run leaves nothing half-written | `tests/test_load.py::test_a_failure_part_way_through_leaves_the_database_as_it_was` |
| AC6 | The on-call engineer sees Northwind's work orders through the existing platform, scoped by role | `tests/test_end_to_end.py` |
| AC7 | Text from WOMS can't smuggle hidden instructions to the on-call assistant | `test_the_planted_injection_arrives_visible_but_without_its_hidden_characters` |
| AC8 | The whole sync can be removed cleanly | `tests/test_rollback.py`, `rollback.md` |

## Assumptions

See the RAID log, A1–A3. If an assumption turns out to be false, it becomes a change request.

## Change control

Any change to the scope, the date or the acceptance criteria goes through a written change request with an
impact analysis, and the sponsor decides. CR-001 is the first.

## Timeline

Four weeks: discovery and scope (weeks 0–1), build (week 2), go-live and handoff (week 3). See `plan.md`.
