-- 0015_agent_contract_snapshots.sql — immutable run contract snapshots.

CREATE TABLE IF NOT EXISTS agent_contract_snapshots (
    id                TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL UNIQUE,
    contract_sha256   TEXT NOT NULL UNIQUE,
    snapshot_json     TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TRIGGER IF NOT EXISTS agent_contract_snapshots_no_update
BEFORE UPDATE ON agent_contract_snapshots
BEGIN
    SELECT RAISE(ABORT, 'agent contract snapshots are immutable');
END;

CREATE TRIGGER IF NOT EXISTS agent_contract_snapshots_no_delete
BEFORE DELETE ON agent_contract_snapshots
BEGIN
    SELECT RAISE(ABORT, 'agent contract snapshots are immutable');
END;
