# Attribution — vendored Hermes foundation

The contents of `foundation/atlas-hermes/` are a vendored copy of the
**Hermes Agent** project, used as the ATLAS runtime foundation (D-018, D-021).

- **Upstream project:** Hermes Agent — NousResearch
- **Upstream URL:** https://github.com/NousResearch/hermes-agent.git
- **Pinned SHA:** `e8b9369a9d2df36139a5055cae3ed3c15691e03e`
- **Upstream version:** 0.14.0 (tag `v2026.5.16-1302-ge8b9369a9`)
- **License:** MIT — full text in `foundation/atlas-hermes/LICENSE`
- **Contributor history:** preserved in `foundation/atlas-hermes/.mailmap`

## Relationship to ATLAS

ATLAS evolves this foundation rather than wrapping stock Hermes; it does not
route through an unmodified upstream install. The two-layer branding policy
(D-021) applies: the ATLAS/L2 brand is the experience layer plus this vendored,
ATLAS-extended foundation. Per-file upstream attribution, license headers, and
historical comments are retained throughout the vendored tree.

All intentional deviations from upstream are recorded in
[`DIVERGENCE_LOG.md`](./DIVERGENCE_LOG.md).

## Other vendored / referenced pillars

Confirmed permissive (Phase 4.5 license review), referenced at the
architecture level only — not vendored into this tree:

| Pillar | License |
|---|---|
| Terax AI | Apache-2.0 |
| Odysseus | MIT |
| FreeLLMAPI | MIT |
| Twenty CRM (sidecar, unbranded, pinned upstream) | AGPL-3.0 (sidecar-only; no copyleft obligation on ATLAS) |
