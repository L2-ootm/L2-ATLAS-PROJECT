---
id: DIV-001
phase: 01-hermes-foundation-audit
friction: system-prompt-augmentation
tier: in-core edit (ATLAS-only)
classification: ATLAS-only
status: PENDING — deferred to Phase 4 implementation
created: 2026-06-05
---

# DIV-001 — System Prompt Augmentation

## Friction

ATLAS requires persistent operator identity and policy context injected into the Hermes system prompt
(e.g., ATLAS runtime ID, audit-mode declaration, constraints on tool use). This content must persist
across turns — not be re-injected ephemerally per turn.

## Cloned-Source Evidence

`agent/system_prompt.py` builds the system prompt in three tiers: stable (core persona + profiles),
context (cwd-dependent files), and volatile (memory/skills per session). No plugin hook intercepts
this construction. The `pre_llm_call` hook can inject **ephemeral** context (appended to the user
message per turn) but cannot modify the cached stable system prompt.

There is no `ATLAS_SYSTEM_PROMPT_EXTENSION` config key or comparable plugin contract.

## Divergence Policy Analysis

Per the divergence policy (plugin > tool > hook > skill > ATLAS-only > in-core):
- **Plugin**: ❌ No hook targets the stable system prompt.
- **Tool / Hook / Skill**: ❌ All limited to ephemeral per-turn injection.
- **ATLAS-only**: ✅ An ATLAS-managed config file (e.g., `AGENTS.md` or `CLAUDE.md` in the working
  directory) can inject content via the context-file tier (`build_context_files_prompt`). Hermes
  loads `.hermes/AGENTS.md` or `AGENTS.md` from `TERMINAL_CWD`. This is **ATLAS-only** and
  does not require forking Hermes.
- **In-core edit**: If the context-file approach is insufficient (e.g., must appear in the stable
  cached block, not the context tier), a minimal patch to `agent/system_prompt.py` is required.

## Decision

**Preferred path:** ATLAS injects operator context via `AGENTS.md` / context-file mechanism (ATLAS-only,
no Hermes core edit). This lands in the context tier — not cached in the stable block, but loaded
per session.

**Fallback:** If context-tier injection proves insufficient (token budget or cache concerns), file a
Phase 4 in-core patch to `agent/system_prompt.py` to read an ATLAS-owned config key from the
plugin/config system.

**Classification:** ATLAS-only (context-file approach) → escalate to in-core if context tier is
insufficient in Phase 4 testing.

## Phase 4 Action

- [ ] Test whether `AGENTS.md` in the working directory provides adequate system-prompt coverage
- [ ] If not, write minimal patch to `agent/system_prompt.py` and document as upstreamable
