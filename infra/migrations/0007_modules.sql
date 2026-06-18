-- ATLAS migration 0007: optional activatable modules registry (Decision 3b)
-- ADDITIVE + NON-DESTRUCTIVE — CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE seed,
-- safe to re-apply (the migration runner stamps it once). Mirrors atlas_core.schemas.core.Module.
PRAGMA foreign_keys = ON;

-- A module is an optional capability (e.g. cashflow) that the operator activates
-- from the System page. Off by default so the base install stays lean. `id` is a
-- stable slug (not a uuid) so seeds and code reference it by name.
CREATE TABLE IF NOT EXISTS modules (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'inactive',
    activated_at TEXT
);

-- Seed the cashflow module as available-but-inactive. INSERT OR IGNORE keeps this
-- non-destructive: re-applying never overwrites an operator's activation state.
INSERT OR IGNORE INTO modules(id, name, description, status) VALUES
 ('cashflow',
  'Cashflow',
  'L2 cash-management module — clients, contracts, expenses, invoices, partners, cash-flow, reports.',
  'inactive');
