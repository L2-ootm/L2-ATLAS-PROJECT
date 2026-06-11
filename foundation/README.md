# foundation/

The vendored, evolving ATLAS foundation (D-018, D-021 §9).

- `atlas-hermes/` — Hermes Agent vendored at SHA `e8b9369a9…` (MIT, see
  `ATTRIBUTION.md`). This tree IS the ATLAS harness substrate: it is evolved
  in place, never wrapped as a black box (D-018). Every change is logged in
  `DIVERGENCE_LOG.md`.
- Install (editable, with the atlas packages):
  `python -m pip install -e packages/atlas-core -e services/agent-runtime -e services/wiki-runtime -e foundation/atlas-hermes`
- Boot smoke: `python scripts/foundation_boot_smoke.py` — verifies the
  foundation imports and the `atlas_audit` bundled plugin registers its
  6 hooks.

The read-only reference clone stays at `_EXTERNAL_REPOS/hermes-agent`
(gitignored) for diffing against upstream.
