-- 0037: a team member's message carries what was known about it.
--
-- A team run is a chain of agents reading each other's output. Each member
-- received the previous member's `result_preview` as bare text under its role
-- label, so "I migrated the schema and the tests pass" arrived at the next
-- member indistinguishable from an established fact. Nothing in the record
-- said whether that actor had succeeded, failed, or been cancelled, and
-- nothing said whether any check had run against what it claimed. The next
-- member built on it either way. This is the dominant failure mode of
-- delegated work: not a bad result, an unexamined one.
--
-- Both columns are written at append time by the worker, which is the only
-- place that holds the actor row and the child run id together. Deriving them
-- later at render time would re-read state that has since moved on — the
-- verdict a reader needs is the one that was true when the message was sent.
--
-- Existing rows keep '': messages appended before this migration were written
-- under the old contract, and an empty string renders as no claim about
-- provenance rather than as a passing one (see team_run_service.render_inbox).

ALTER TABLE team_chat_messages ADD COLUMN sender_status TEXT NOT NULL DEFAULT '';
ALTER TABLE team_chat_messages ADD COLUMN verification TEXT NOT NULL DEFAULT '';
