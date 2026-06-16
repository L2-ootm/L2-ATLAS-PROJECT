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

---

### D-LOG-002 — `atlas_audit` bundled plugin shim (back-filled Phase 10.0, 2026-06-16)

**Type:** foundation extension-point / registered-plugin shim
**Driver:** ATLAS audit emission AGNT-04, AUD-01/02 (Phase 10.2); D-021 §9 two-layer
branding; D-018 evolved-foundation discipline.

`foundation/atlas-hermes/plugins/atlas_audit/__init__.py` is a one-line delegation
shim that loads the ATLAS audit bus into every Hermes foundation boot:

```python
from atlas_audit import register  # noqa: F401
```

This shim makes `atlas_audit` a **bundled plugin** of the evolved foundation so the
audit bus registers on every agent boot without per-machine project-plugin opt-in.
The canonical implementation lives in the `atlas_audit` package under
`services/agent-runtime/` — the foundation's shim delegates into it. The foundation
itself contains no audit logic; it only carries the one-line bridge.

**Why a plugin shim and not a direct import:** the one-way dependency rule
(`services/agent-runtime` depends on `foundation/`, never the reverse) means the
foundation cannot `import atlas_audit` directly in its core code without inverting
the dependency direction. The registered-plugin mechanism is the sanctioned path for
foundation→ATLAS references and is the precedent for any future v1.1 extension
points (AGNT-01 hard gate: extend via hooks, never rewrite the agent loop).

**Naming note:** earlier planning notes referenced this divergence as `DIV-F-002`.
That label does not appear in this log and is **not** the canonical id scheme. The
canonical scheme is `D-LOG-NNN` (this file). Downstream phases (10.2+) must use
`D-LOG-NNN` exclusively.

**Net effect:** ATLAS audit events (`model_call_start`, `model_call_end`,
`provider_fallback`) are emitted on every agent conversation without requiring the
operator to manually register the plugin. Foundation stays upstream-mergeable: the
shim is additive and the upstream Hermes plugin-loader ignores unknown plugins
gracefully.
