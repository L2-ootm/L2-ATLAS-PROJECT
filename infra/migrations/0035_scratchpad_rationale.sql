-- 0035: the self-extension decision becomes a recorded artifact.
--
-- WP-A of the self-extension roadmap was shipped as doctrine only: the four
-- questions ("is it actually missing / will it be needed again / is it bounded
-- / what is the cheapest unblock") lived in a skill file and a tool
-- description, and nothing verified that a run had answered them before
-- minting a disposable. A per-run cap was the only mechanical bound on the
-- landfill failure mode.
--
-- `rationale` makes the decision a required, durable, operator-visible field on
-- every materialized tool. It does not make the judgment good — nothing can —
-- but it makes the judgment *stated*, which is what a later run needs when it
-- finds the same disposable being rebuilt for the third time, and what the
-- promotion pipeline (WP-C) reads as its evidence.
--
-- Existing rows keep '': tools minted before this migration were created under
-- the old contract and must not be retroactively claimed to have a rationale.

ALTER TABLE scratchpad_entries ADD COLUMN rationale TEXT NOT NULL DEFAULT '';
