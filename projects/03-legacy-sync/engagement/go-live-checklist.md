# Go-live checklist

Each item names the command or document that proves it. Nothing is ticked on someone's word.

## Before

- [ ] **Tests green:** `uv run pytest -q` in `projects/03-legacy-sync` → `76 passed`
- [ ] **CI green** on Ubuntu and Windows, including the demo on a cp1252 console
- [ ] **Copy of the ops DB taken** (DEP3). The file path is recorded in the go-live log
- [ ] **Dry run against the production DB:** `fde-sync --db <prod ops.db> --report golive-dryrun.md` exits `0`
- [ ] **Ray has reviewed the status mapping** in `src/fde_sync/normalise.py` against the dry-run report
- [ ] **Luis has read the dry-run report**, including the rejected records he'll need to fix in WOMS
- [ ] **Priya has signed off** on read-only access and the local-only data path (D7, D8)

## Go

- [ ] `fde-sync --db <prod ops.db> --apply --report golive.md` exits `0`
- [ ] `fde-sync --db <prod ops.db> --apply` again reports `new 0, changed 0`: the re-run writes nothing
- [ ] An on-call engineer, using the `viewer` role, reads Northwind's work orders through the platform

## After

- [ ] The scheduler entry is in place (runbook, "Scheduling")
- [ ] The first scheduled run's report has been read by Luis
- [ ] Handoff meeting held; `handoff.md` walked through with Luis and Ray

## Abort

If any **Go** step fails: stop, follow `rollback.md`, and keep the report from the failed run.
