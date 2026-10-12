-- Undo fde-sync: remove every incident the sync created, and its ledger.
-- See engagement/rollback.md. Take a copy of the DB file first; this is the only delete in the project.
--
-- Kept on purpose: incidents anyone logged by hand (even for northwind), and sync_runs, the record of
-- what ran and when. After this, the next `fde-sync --apply` loads everything again from scratch.
BEGIN;
DELETE FROM incidents
 WHERE id IN (SELECT incident_id FROM sync_ledger WHERE source = 'woms');
DELETE FROM sync_ledger WHERE source = 'woms';
COMMIT;
