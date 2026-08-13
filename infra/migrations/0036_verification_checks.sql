-- 0036: what verification this workspace actually has.
--
-- The verification gate answers "did this run check its own work" from the
-- run's audit trail. That is a per-run question and the trail forgets nothing,
-- but it also carries nothing forward: a run that finds no test suite and a run
-- that never looked are indistinguishable afterwards, and the enforced check
-- turn can only say "run a real check" without being able to name one.
--
-- This table is the durable half — a ledger of the checks a workspace has,
-- accumulated two ways:
--
--   source='detected'  a marker file in the workspace says the check exists
--                      (pyproject's [tool.pytest], package.json scripts.test,
--                      Cargo.toml, go.mod, ruff/mypy/tsconfig). Cheap, and
--                      available before any run has executed anything.
--   source='observed'  a run actually ran the command and the gate classified
--                      it as a strong signal. Slower to accumulate and worth
--                      more: it is the check as this project really invokes it,
--                      not as its config file implies.
--
-- Keyed by workspace root rather than project_id: a run reaches a root through
-- its surface session long before anyone registers a project, and the checks
-- belong to the directory either way. project_id is carried when known, for
-- reporting only.
--
-- last_status/last_run_id/last_seen_at are recorded at KIND granularity — the
-- gate classifies a command as `tests` or `lint`, so "a check of this kind last
-- ran in run X and passed" is the strongest true statement available. Do not
-- read them as being about this exact command unless source='observed'.

CREATE TABLE IF NOT EXISTS verification_checks (
    root          TEXT NOT NULL,
    kind          TEXT NOT NULL,
    command       TEXT NOT NULL,
    source        TEXT NOT NULL DEFAULT 'detected',
    detected_from TEXT NOT NULL DEFAULT '',
    project_id    TEXT NOT NULL DEFAULT '',
    last_run_id   TEXT NOT NULL DEFAULT '',
    last_status   TEXT NOT NULL DEFAULT '',
    last_seen_at  TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (root, kind, command)
);

CREATE INDEX IF NOT EXISTS idx_verification_checks_root
    ON verification_checks(root);
