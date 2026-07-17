-- 0020_retention_safe_contract_deletion.sql
--
-- Contract snapshots remain immutable while retained (the UPDATE trigger from
-- 0015 stays in force), but an authorized retention transaction must be able
-- to delete the snapshot with its parent run. The original DELETE trigger also
-- blocked SQLite's ON DELETE CASCADE and made archived-mission purge fail after
-- a native run had persisted its contract.

DROP TRIGGER IF EXISTS agent_contract_snapshots_no_delete;
