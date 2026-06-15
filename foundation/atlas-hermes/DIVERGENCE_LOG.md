# ATLAS ↔ Hermes Divergence Log

This file records every intentional divergence of the vendored
`foundation/atlas-hermes` tree from its upstream source. It exists so the
vendored foundation stays auditable: anyone can see exactly where ATLAS
deviates from stock Hermes and why (D-018, D-021).

**Upstream:** https://github.com/NousResearch/hermes-agent.git
**Pinned SHA:** `e8b9369a9d2df36139a5055cae3ed3c15691e03e`
**Upstream version:** 0.14.0 (tag `v2026.5.16-1302-ge8b9369a9`)
**License:** MIT (see `LICENSE`)

> Policy: divergences here are distribution/curation hardening, not source
> laundering. Upstream attribution, license headers, and historical comments
> are never removed.

---

## Divergences

### D-LOG-001 — Quarantine unsafe default skills (Phase 9.5, 2026-06-15)

**Type:** skill-tree curation (move, not delete)
**Driver:** Phase 9 inventory release blockers B1 / B4; Phase 9.5 public hardening.

Two skills present in the upstream default skill tree are model-safety
circumvention tools that must not load on a clean ATLAS install or appear in
any public/opt-in manifest:

| Skill | Moved from | Moved to |
|---|---|---|
| `godmode` (LLM jailbreak) | `skills/red-teaming/godmode` | `quarantined-skills/godmode` |
| `obliteratus` (abliterate refusals) | `skills/mlops/inference/obliteratus` | `quarantined-skills/obliteratus` |

The now-empty `skills/red-teaming/` directory was removed.
`skills/mlops/inference/` retains its legitimate siblings (`llama-cpp`, `vllm`).

Files were moved via `git mv` — content, attribution, and license headers are
unchanged. Upstream history is **not** rewritten (Phase 9.5 non-goal). See
`quarantined-skills/README.md` for the load/distribution rules.

**Net effect:** the vendored default tree no longer ships a jailbreak or an
abliteration skill. Blockers B1 and B4 are resolved for distribution purposes.
