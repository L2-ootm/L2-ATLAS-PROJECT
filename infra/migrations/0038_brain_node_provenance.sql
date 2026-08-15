-- 0038: a Brain node records where it came from, and a losing claim is kept.
--
-- `brain_nodes.confidence` was written by the agent that created the node,
-- defaulting to 0.8 (graph_bridge add_node). A writer that grades its own
-- homework grades generously, and nothing else in the row could contradict it:
-- `source_id` is `run:<id>`, which records who said a thing and never what
-- backed it. So the graph could not distinguish a checked fact from a guess,
-- and neither could anything reading it.
--
-- `grade` replaces that judgement with a fact about origin, assigned by the
-- code that knows the origin (see atlas_core.schemas.provenance). The agent
-- cannot set it. `confidence` is left in place: it is still a legitimate
-- ranking signal within a grade, and dropping a column would break readers
-- for no gain.
--
-- Existing rows are backfilled by the same rule the retriever has been
-- inferring at read time, so the stored answer matches what runs already saw:
-- `run` and `mission` nodes are ATLAS's own projections of rows it holds, and
-- are therefore observed; everything else was authored by an agent through
-- atlas_graph with no evidence requirement, and `derived` is the honest
-- ceiling for that.
--
-- brain_node_conflicts exists because node ids derive from (entity_type,
-- label): re-asserting an entity upserts over it, so a weaker later claim used
-- to silently overwrite a stronger earlier one and the disagreement left no
-- trace. The losing claim is now recorded instead of discarded. Two facts that
-- disagree are information; only one of them surviving quietly is not.
--
-- `needs_operator` marks the one contradiction ATLAS refuses to resolve on its
-- own: a `verified` fact against a `stated` intent means reality disagrees with
-- what the operator asked for. Overwriting drops their intent, refusing hides
-- the truth, and ATLAS is entitled to neither.

ALTER TABLE brain_nodes ADD COLUMN grade TEXT NOT NULL DEFAULT '';

UPDATE brain_nodes
   SET grade = CASE
                 WHEN entity_type IN ('run', 'mission') THEN 'observed'
                 ELSE 'derived'
               END
 WHERE grade = '';

CREATE TABLE IF NOT EXISTS brain_node_conflicts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id         TEXT NOT NULL,
    incumbent_grade TEXT NOT NULL,
    incumbent_label TEXT NOT NULL,
    incoming_grade  TEXT NOT NULL,
    incoming_label  TEXT NOT NULL,
    incoming_body   TEXT NOT NULL DEFAULT '',
    run_id          TEXT NOT NULL DEFAULT '',
    needs_operator  INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_brain_node_conflicts_node
    ON brain_node_conflicts(node_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_brain_node_conflicts_operator
    ON brain_node_conflicts(needs_operator, created_at DESC);
