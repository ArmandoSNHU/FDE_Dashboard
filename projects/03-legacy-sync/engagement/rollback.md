# Rollback

Two options, in order of preference. Both are rehearsed by tests, not just written down.

## 1. Restore the copy (preferred on go-live day)

The go-live checklist takes a copy of the ops DB before the first apply. Stop the scheduler, put the copy
back, and you're exactly where you started, including anything unrelated to the sync.

## 2. Remove only what the sync wrote

Use this when other things have written to the ops DB since go-live, so restoring the copy would lose them.

```powershell
Copy-Item D:\ops\ops.db D:\ops\ops.before-rollback.db      # always keep a copy first
sqlite3 D:\ops\ops.db ".read ops/rollback.sql"
```

[`ops/rollback.sql`](../ops/rollback.sql) deletes the incidents listed in the sync's ledger, then the ledger
itself, in one transaction. It keeps:

- every incident the sync didn't create, including Northwind incidents someone logged by hand;
- `sync_runs`, the record of what ran and when.

The next `fde-sync --apply` loads everything again from scratch.

**Proven by** `tests/test_rollback.py`: after an apply plus two hand-logged incidents, the rollback leaves
exactly the hand-logged ones, an empty ledger and the run history; and a following run loads the same number
of work orders as the first.
