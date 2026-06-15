# Quarantined skills — NOT loaded, NOT distributed

This directory is **not** a skill load path. Nothing here is part of the ATLAS
default skill tree, any opt-in pack, or any public distribution manifest.

Skills land here when they are present in the upstream Hermes source for
attribution/history reasons but are unsafe to ship as an ATLAS default or
opt-in capability. They are kept (rather than deleted) so the vendored
foundation remains a faithful, auditable copy of upstream and so the exclusion
decision is explicit and reviewable.

## Why these were quarantined

| Skill | Origin | Reason |
|---|---|---|
| `godmode` | upstream `skills/red-teaming/godmode` | LLM jailbreak skill (Parseltongue / GODMODE / ULTRAPLINIAN). Shipping a jailbreak in an ATLAS default is a policy/reputational non-starter. Release blocker B1. |
| `obliteratus` | upstream `skills/mlops/inference/obliteratus` | Model-safety circumvention (abliterates refusals via diff-in-means steering). Same family as B1. Release blocker B4. |

See `docs/imports/SKILL_INVENTORY.md` §6 (blockers) and
`foundation/atlas-hermes/DIVERGENCE_LOG.md` for the canonical record.

## Rules

- Do not reference any path under this directory in a public-facing manifest or pack.
- Do not wire this directory into any skill discovery/load path.
- Do not remove upstream attribution or license headers from the files here.
- If a future authorized red-team/research milestone needs these, it must add an
  explicit authorization-acknowledgement gate first — never a default load.
