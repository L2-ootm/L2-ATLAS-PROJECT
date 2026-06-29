-- Phase 10.7: persist the deterministic, secret-safe policy explanation with
-- each queued approval so every surface renders server authority, not its own
-- policy interpretation.
ALTER TABLE tool_approvals ADD COLUMN policy_receipt TEXT;

