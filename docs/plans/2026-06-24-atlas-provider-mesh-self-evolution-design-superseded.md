# ATLAS Provider Mesh & Self-Evolution Design — Superseded Original Scope

> Superseded on 2026-06-24 by the corrected portfolio design at
> `docs/plans/2026-06-24-atlas-provider-mesh-self-evolution-design.md`.
> Retained intact as planning history. The original combined milestone, global
> phase numbering, ADR reservations, and dependency claims are not active.

**Date:** 2026-06-24
**Status:** Brainstorm approved (decomposition + sequencing). Phase-level requirements to be traced during planning.
**Decision:** Stand up a new milestone **v1.2 — ATLAS Provider Mesh & Self-Evolution**, sequenced after v1.1 (Phases 10.1–10.8) and before v2.0 (Phases 11–14). Phases numbered `10.9`–`10.15`.

---

## 1. Summary

ATLAS becomes a **dual-mode, provider-agnostic operator cockpit** rather than only a transformed Hermes runtime. The operator can run in **ATLAS-gateway mode** (the native, opinionated ATLAS agent/runtime) or **BYO-runtime mode** (attach an external agentic runtime or model gateway and let ATLAS provide cockpit, audit, permissions, and routing around it). Mode is chosen at setup and changeable afterward from the CLI or WebUI.

A **role-keyed model rulebook** lets the operator predefine, per provider, which model fills which agent role (curator, main agent, subagent, …) at which effort level. On top of the rulebook, the main agent performs **capability/cost/health-aware dynamic subagent dispatch** across every available provider and model, with a fallback cascade on the Phase 10.0 error-classification contract.

In parallel, ATLAS gains a **self-evolution loop**: an autonomous, GSD-framework-governed agent loop that keeps the vendored Hermes foundation in sync with upstream and, progressively, modifies and commits ATLAS's own code. A **foundation boundary manifest** makes the long-term "gradually rebuild the foundation to ATLAS-native" goal and the "keep upstream sync easy" goal coexist.

A **bidirectional WebUI gap audit** compares the ATLAS WebUI against the foundation's WebUI to protect what ATLAS does better and adopt what it is missing.

This design does **not** discard the v1.1 thesis. v1.1's "one ATLAS agent, many surfaces" remains the spine; the Provider Mesh generalizes the existing `AgentRuntime` ABC (P4: `native` | `claude_code`) and the D-017 `model_router` into a first-class, dual-mode routing layer beneath the surfaces.

---

## 2. Grounding: what already exists

The vendored Hermes foundation (`foundation/atlas-hermes/`) already contains a large fraction of the raw capability this milestone surfaces and generalizes:

- **Multi-provider transports** — `agent/transports/{anthropic,bedrock,codex}.py`, plus Gemini Cloud Code and Copilot ACP adapters. Codex is already a first-class transport upstream.
- **A WebUI** — `web/src/pages/` including `ModelsPage.tsx` and `ConfigPage.tsx` (the thread-3 audit target, in-tree).
- **Delegation / subagent machinery** — `tools/delegate_tool.py`, `ui-tui/src/app/delegationStore.ts`, subagent-tree rendering.
- **Model catalog** — `agent/models_dev.py`.

ATLAS-native groundwork already shipped:

- **`AgentRuntime` ABC** (`services/agent-runtime/atlas_runtime/agents/`) with `native` and `claude_code` backends; `runs.agent_runtime` column (migration 0006); `atlas mission run --agent X`. (P4, de-risk passed — local Claude Code subscription session, no API key.)
- **Phase 10.0 routing groundwork** — `0004_registry_v2.sql` (provider / model_v2 / route tables, composite key, source-scoped deactivation) and the fallback-cascade error-classification spec.
- **D-017** — ATLAS `model_registry` + `model_router`, task-class routing, audit-event metadata for all LLM calls.
- **Config control plane** — `~/.atlas/config.yaml`, `config_service`, `atlas config`, gateway `GET /v1/config`, System RUNTIME CONFIG panel.

**Consequence:** the build basis is **hybrid** — define an ATLAS-native contract (ATLAS owns the model and the UX), implement the first provider backends by delegating to the foundation's transports where they already work, and rebuild foundation modules to ATLAS-native over time.

---

## 3. Locked decisions from this brainstorm

These are the decisions that shape the phases. Each should be promoted to a numbered ADR (`D-025`+) during planning.

1. **Dual-mode is first-class.** ATLAS ships both `ATLAS-gateway` mode (native, opinionated) and `BYO-runtime` mode (attach external runtime/gateway). Mode is set at setup and changeable from CLI and WebUI. Neither mode is a second-class afterthought.
2. **Two adapter shapes.** The attach/routing layer supports both:
   - **Agentic-CLI runtime adapters** — external agents that run their own loop (claude code, codex, opencode, mimocode, native Hermes). ATLAS spawns them (subprocess/SDK), streams their events into the audit bus, and wraps cockpit + permissions. Generalizes the `claude_code` path.
   - **Model-gateway routing** — providers that expose models, not an agent loop (openclaw, OpenAI-compatible endpoints, another ATLAS gateway, FreeLLMAPI). ATLAS's own agent runs the loop and calls them. Extends D-017 / `registry_v2`.
   - **Route-through is the default posture for attached external frameworks.** When the operator already runs a framework that works for them, ATLAS routes through it as-is and adds cockpit/audit/permissions/routing around it. Moving a workload onto the ATLAS-native runtime is an opt-in, reversible choice — never automatic and never implied as the required end state. (This is distinct from the *foundation*, which is deliberately rebuilt to ATLAS-native over time — decision 5.)
3. **Role-keyed model rulebook.** Per provider, the operator predefines a role→model+effort map (curator, main agent, subagent classes, …). Example: Codex profile = `curator: gpt-5.4-mini`, `main: gpt-5.5 @ medium effort`. Stored in `~/.atlas/config.yaml` under the existing config control plane; surfaced in CLI + WebUI.
4. **Scored dynamic dispatch.** On top of the static rulebook, the main agent decides at runtime which model to dispatch each subagent to, scored by capability, cost, and live health, across all available providers/models. Manual rulebook assignment is the floor; scoring fills the gaps and drives fallback.
5. **Hybrid build basis with a stated end state.** ATLAS owns the rulebook/adapter/router contract and UX now; foundation transports are an early backend. Over time the foundation is rebuilt to ATLAS-native entirely.
6. **Self-evolution is an autonomous, gated agent loop.** The end state is ATLAS updating and committing its own code (and the foundation) autonomously under the project's GSD/loop-engineering discipline. Near-term it runs gated (test-green required, atomic commits, branch/PR, boundary-manifest scoping, rollback, kill switch) and becomes progressively unsupervised. The framework is the guardrail.
7. **Boundary manifest is the enabling primitive.** Every foundation module is classified `foundation-tracked` (mirrors upstream, auto-syncable), `atlas-owned` (rebuilt native, no longer tracks upstream), or `diverged-frozen` (modified, manual reconciliation). Rebuilding a module flips `tracked → owned` and drops it from the upstream-sync surface.
8. **WebUI work is a differential audit, not a rebuild.** Identify what the ATLAS WebUI does better (protect) and what the Hermes WebUI has that ATLAS is missing and could benefit from (adopt/adapt/skip backlog).
9. **Extra-mile / extra-marathon delivery doctrine is binding (§4).** Every task ships the version that detects rather than asks, pre-stages the operator's next action while keeping the easy "use what already works" path the default (heavier paths opt-in), and renders a designed, branded surface with designed empty/error states — gated by the `l2-extra-marathon` review. Functional-but-placeholder is not done.

### Constraints carried from prior decisions

- **D-001 / D-018:** foundation is used directly and transformed, not wrapped. Provider Mesh additions are ATLAS-owned (`packages/atlas-core`, `services/agent-runtime`, gateway, `web-ui-react`); foundation edits stay extension-point-scoped until a module is deliberately rebuilt.
- **D-002:** audit-first. Every runtime attach, route decision, model selection, fallback, and self-evolution commit emits audit events.
- **D-022:** Rust gateway stays dispatch-only; routing state and rulebook live in Python/SQLite; budgets hold (CLI <100ms/<50MB, daemon <80MB idle, binary <20MB).
- **10.0.7 foundation-debrand** interacts with thread 2: debranding rewrites foundation identity, which the upstream-sync classifier must treat as a known, scripted divergence rather than a conflict.

---

## 4. Delivery doctrine — extra mile, extra marathon

**This doctrine is binding for every task in this milestone, and for ATLAS work generally.** It is not a phase; it is the bar every phase is held to. It operationalizes the L2 `l2-extra-marathon-review` standard.

**The bar.** The default for any task is the *extra mile*: don't ship the mechanically-correct minimum — ship the version that anticipates the operator's next action and removes the friction before they hit it. For designated high-leverage aspects (operator first-impression, onboarding, anything the operator touches repeatedly), the bar is the *extra marathon*: the surface should feel pre-thought, autonomous, and finished.

**What "extra mile / extra marathon" concretely means here:**

1. **Detect, don't ask.** Inspect the environment and tell the operator what is true before asking them to configure it. Never make the operator hand-enter what ATLAS can discover.
2. **Pre-stage the next action — and keep the easy path the default.** When ATLAS knows what the operator will likely want, prepare it as a ready-to-apply artifact (attach/route config, profile, or setup) — one action to apply, or autonomous apply under the Phase 10.14 self-evolution gates. Pre-staging never means forcing a heavier path: where a lighter "use what already works" option exists, it is the default and the heavier option is opt-in.
3. **First-class, branded UX — no placeholder surfaces.** Every operator-facing control is designed and branded to the ATLAS celestial-heraldic language (D-024), not a raw form or stub. A feature is not "done" while its surface is a `<Migrating>`-class placeholder.
4. **Fail beautifully.** Empty/loading/offline/error states are designed, explain themselves, and offer the next step — never a blank or a raw trace.
5. **Audited and reversible.** The extra-mile automation still respects D-002 (audit) and stays rollback-safe; "autonomous" never means "unaccountable."

**Worked example — provider/gateway onboarding (the operator's example, now the reference standard):**

- **Autodetect** across `atlas setup`, the CLI, and the WebUI: probe the environment for installed agentic CLIs and reachable gateways (claude code, codex, opencode, mimocode, openclaw, OpenAI-compatible endpoints, another ATLAS). ATLAS *already knows* what is installed before the operator opens the providers surface.
- **Two clearly-offered paths per detected service — route-through is the default:**
  - **Route through the installed framework (default, easy path):** ATLAS attaches the service via its agentic-CLI adapter / gateway router and drives it as-is. The operator keeps the framework they already trust and know works; ATLAS adds cockpit, audit, permissions, and routing around it. Nothing about their existing setup is changed or "converted."
  - **Migrate to ATLAS-native (opt-in):** the operator can *choose* to bring that workload onto the ATLAS-native runtime/rulebook. This is an explicit, reversible choice — never automatic, never the only option, and never implied as the "correct" end state for every service.
  - For each path ATLAS pre-builds the exact ready-to-apply artifact (the attach/route config for route-through; the native profile for migrate), so whichever the operator picks is one action — or autonomous apply under the Phase 10.14 gates.
- **Branded provider controls:** each provider/gateway renders as a designed, branded button/card (state-aware: detected / not-installed / attached-route-through / migrated-native / unhealthy), not a checkbox in a list.

**How the doctrine is enforced.** Every phase's success criteria below carry the doctrine where it applies (autodetect, prepared setup, branded surface, designed states). The `l2-extra-marathon` review is the gate before a phase is called done — a phase that meets its functional criteria but ships a placeholder surface, makes the operator hand-enter discoverable state, or leaves raw error states is **not** complete.

---

## 5. Architecture concepts

### 4.1 Mode and the mesh

```
                    ┌──────────────────────────────────────────┐
                    │  ATLAS surfaces (CLI · TUI · WebUI · API) │
                    └──────────────────────────────────────────┘
                                      │  (v1.1 shared surface/session protocol)
                                      ▼
                    ┌──────────────────────────────────────────┐
                    │           Provider Mesh control plane      │
                    │  mode: ATLAS-gateway | BYO-runtime         │
                    │  rulebook (role→model+effort, per provider)│
                    │  scorer (capability · cost · health)       │
                    │  fallback cascade (10.0 error classes)     │
                    └──────────────────────────────────────────┘
                          │                              │
            agentic-CLI adapters             model-gateway router (D-017)
            (RuntimeAdapter ABC)             (registry_v2 routes)
                          │                              │
   ┌──────────┬──────────┼───────────┐        ┌──────────┼─────────────┐
 native    claude    codex  opencode  mimo   openclaw  OpenAI-compat  another
 hermes     code                              gateway   endpoints      ATLAS
 (found.)  (P4✓)                                                       gateway
```

### 4.2 The rulebook

A **provider profile** is a named, versioned config object: `{ provider, roles: { curator: {model, effort}, main: {model, effort}, subagent_default: {model, effort}, … }, constraints }`. Profiles live in `~/.atlas/config.yaml` (frozen schema, atomic cross-process writes — the existing control plane). A run binds a profile (from Focus/mission default or explicit override). The rulebook is the **deterministic floor**: given a profile and a role, the model is known and auditable.

### 4.3 The scorer

For roles the rulebook leaves open (notably dynamic subagent dispatch), the scorer ranks candidate `(provider, model)` pairs by **capability** (declared fit for the task class), **cost** (token economics), and **health** (live availability/latency from probes + recent failure signal). The choice and its rationale are emitted as audit metadata ("chose X because …"), so dispatch stays explainable. The same scorer drives the **fallback cascade**: on an error classified by the 10.0 table, demote the failed candidate and re-pick.

### 4.4 The boundary manifest and self-evolution loop

The **manifest** (`foundation/atlas-hermes/.atlas-boundary.yaml` or equivalent) lists every foundation module with a `status` (`tracked` | `owned` | `diverged-frozen`), an upstream path, and the last-synced upstream ref. The **self-evolution loop** runs as a scheduled agent under GSD discipline:

1. Fetch upstream Hermes commits since the last-synced ref.
2. Classify each commit's touched paths against the manifest.
3. For `tracked`-only commits: apply on a branch, run the gate (full test suites), atomic-commit, open PR (and, at higher autonomy, auto-merge on green).
4. For commits touching `owned`/`diverged-frozen`: do not auto-apply; emit a flagged reconciliation report.
5. Audit every action; respect the kill switch; keep a rollback path.

Autonomy is a dial, not a binary: the loop ships gated (proposes; human merges), graduates to auto-merge-tracked-on-green, and ultimately generalizes from foundation-sync to ATLAS self-modification under the same gates.

---

## 6. Phase breakdown

> Requirement IDs are seeds to be traced/confirmed during `/gsd-plan-phase`. Success criteria are the verification bar.

### Phase 10.9 — Provider Mesh Contract & Dual-Mode Control Plane

**Goal:** Establish the ATLAS-native contract for attaching and selecting runtimes, and make dual-mode a real, switchable operator setting — before any per-provider backend or rulebook UX is built.

**Scope:**
- `RuntimeAdapter` ABC for agentic-CLI runtimes (lifecycle: spawn, stream→audit, cancel, permission bridge, capability declaration), generalized from the P4 `AgentRuntime` ABC.
- Extension of the model-gateway router on `registry_v2` for API-class providers.
- Dual-mode setting (`ATLAS-gateway` | `BYO-runtime`) in `~/.atlas/config.yaml`, set by `atlas setup` and mutable via `atlas config` + WebUI.
- Mesh registry: enumerate attached runtimes/gateways, their kind, health, and capability declarations.

**Success criteria:**
1. A documented, versioned `RuntimeAdapter` contract exists; the existing `native` and `claude_code` runtimes implement it without behavior regression.
2. Mode is persisted, surfaced, and switchable from CLI and WebUI; switching is audited and takes effect without a stale-state restart hazard.
3. The model-gateway router accepts at least one external gateway as a configured backend behind the `registry_v2` route tables.
4. Every attach/detach/mode-change/route emits audit events (D-002).
5. **Doctrine (§4):** `atlas setup`, the CLI, and the WebUI autodetect installed agentic CLIs and reachable gateways and present detected state before asking the operator to configure anything.

**Depends on:** 10.13 (manifest, for the foundation-as-backend boundary), v1.1 10.3/10.4 (surface session + config control plane).

---

### Phase 10.10 — Role-Keyed Model Rulebook

**Goal:** Let the operator define, per provider, which model+effort fills which agent role, and bind that profile to runs.

**Scope:**
- Provider-profile schema (`roles: {curator, main, subagent classes…}`, effort levels, constraints), versioned, in `~/.atlas/config.yaml`.
- Profile resolution: Focus/mission default → explicit override; resolved inside the single run path (mirrors A4 `resolve_provider`).
- CLI (`atlas config profile …` / surfaced in `mission run`) + WebUI editor (extends the Models/Config surfaces; informed by 10.15).

**Success criteria:**
1. A profile assigning distinct models+effort per role validates, persists atomically, and is masked-safe (secrets stay references).
2. A run resolves and records the exact role→model bindings it used; the binding is replayable and auditable.
3. CLI and WebUI edit the same profile through one contract; a change from one surface is visible to the other without restart or last-writer-wins loss.
4. Absent/partial profiles degrade to an explicit documented default, never to silent provider choice.
5. **Doctrine (§4):** the WebUI profile editor is a designed, branded surface (not a raw form) with designed empty/validation/error states; detected providers are pre-populated so the operator edits rather than enters from scratch.

**Depends on:** 10.9.

---

### Phase 10.11 — Capability/Cost/Health Scoring & Dynamic Subagent Dispatch

**Goal:** Give the main agent the ability to choose subagent models by fit, and make routing resilient via a scored fallback cascade.

**Scope:**
- Capability/cost/health signals: capability declarations per `(provider, model)`, cost model, health probes + recent-failure signal.
- Scorer that ranks candidates and is consumed by (a) dynamic subagent dispatch and (b) the fallback cascade on the 10.0 error-classification table.
- Explainability: the chosen candidate and rationale are emitted as audit metadata.

**Success criteria:**
1. For an open (rulebook-unset) subagent role, the scorer picks a candidate and records capability/cost/health inputs + rationale.
2. A classified provider error demotes the candidate and re-picks per the cascade; the transition is test-covered and audited.
3. Manual rulebook assignment always overrides the scorer; scoring only fills gaps.
4. Health probing degrades safely (a dead provider is demoted, not fatal) and never leaks credentials.

**Depends on:** 10.10, 10.0 fallback-cascade spec.

---

### Phase 10.12 — Provider Backends

**Goal:** Ship the concrete backends behind the contract.

**Scope:**
- Agentic-CLI adapters: codex, opencode, mimocode (claude code already exists); native Hermes via foundation-transport delegation (the hybrid backend).
- Model gateways: openclaw + OpenAI-compatible endpoints + "another ATLAS gateway" behind the router.
- Per-backend capability declarations feeding 10.11; per-backend auth handled as ATLAS-owned references (no secrets in masked config).

**Success criteria:**
1. Each shipped agentic-CLI adapter runs a reference mission end-to-end with events normalized into the audit bus and permissions honored.
2. Each shipped gateway backend serves completions through the router with route + cost + health recorded.
3. Native-Hermes-via-foundation delegation works without foundation edits beyond declared extension points (D-001/D-018).
4. Adding a backend = implementing the adapter contract + declaring capabilities + (optional) a manifest entry — documented as the extension recipe.
5. **Doctrine (§4) — the reference standard for this milestone:** for each detected service ATLAS offers two clearly-labeled paths — **route-through the installed framework (default, easy, nothing converted)** and **migrate-to-ATLAS-native (opt-in, reversible)** — pre-building the ready-to-apply artifact for whichever the operator picks (one-action apply, or autonomous apply under the Phase 10.14 self-evolution gates), and renders each provider/gateway as a designed, branded, state-aware control (detected / not-installed / attached-route-through / migrated-native / unhealthy) — never a bare list item or placeholder.

**Depends on:** 10.9, 10.10, 10.11. (Backends can land incrementally; claude code is the proven reference.)

---

### Phase 10.13 — Foundation Boundary Manifest & Upstream-Delta Tooling

**Goal:** Make the diverging foundation classifiable and the upstream delta computable — the primitive that lets gradual rebuild and easy sync coexist.

**Scope:**
- Boundary manifest covering every foundation module (`tracked` | `owned` | `diverged-frozen`, upstream path, last-synced ref).
- Upstream watcher (fetch upstream commits since ref) + delta classifier (map touched paths → manifest status).
- A reproducible report: "what changed upstream, what applies cleanly to `tracked`, what conflicts with `owned`/`diverged-frozen`."
- Integration with the 10.0.7 debrand so scripted identity rewrites are known transforms, not conflicts.

**Success criteria:**
1. Every foundation module has a manifest status; coverage is verified (no unclassified files).
2. The classifier deterministically partitions an upstream delta into tracked/owned/diverged buckets.
3. The report is reproducible and machine-readable (consumable by 10.14).
4. Flipping a module `tracked → owned` removes it from the tracked surface and is reflected in the next delta report.

**Depends on:** none hard (de-risks 10.9's foundation backend and is a prerequisite for 10.14). Can start early.

---

### Phase 10.14 — Autonomous Gated Self-Evolution Loop

**Goal:** Run the self-update as an autonomous, GSD-governed, gated agent loop that proposes, tests, and commits — progressively unsupervised.

**Scope:**
- Scheduled agent loop consuming the 10.13 delta report.
- Gates: full test suites green, atomic commit per change, branch/PR, boundary-manifest scoping (only `tracked` auto-applied), rollback path, kill switch.
- Autonomy dial: `propose-only` → `auto-merge-tracked-on-green` → (future) ATLAS self-modification under the same gates.
- Audit + reconciliation reports for everything touching `owned`/`diverged-frozen`.

**Success criteria:**
1. The loop applies a `tracked`-only upstream delta on a branch, runs the gate, and produces an atomic-committed PR; nothing lands on main without the configured autonomy level allowing it.
2. A delta touching `owned`/`diverged-frozen` halts auto-apply and emits a flagged reconciliation report.
3. The kill switch stops the loop cleanly; a bad apply is rollback-recoverable; every action is audited.
4. The autonomy level is an explicit, audited setting; raising it requires the lower level to have a green track record (documented promotion criteria).

**Depends on:** 10.13, and a stable mesh tree (10.9–10.12) so the test gate is meaningful. Highest risk — sequenced last.

---

### Phase 10.15 — Bidirectional WebUI Gap Audit

**Goal:** Know precisely what the ATLAS WebUI does better than the Hermes WebUI (protect it) and what Hermes has that ATLAS is missing and could benefit from (adopt/adapt/skip).

**Scope:**
- Feature inventory of the foundation WebUI (`foundation/atlas-hermes/web/`) and the ATLAS WebUI (`services/web-ui-react`).
- Bidirectional gap analysis → a backlog tagged adopt/adapt/skip with rationale and rough effort.
- Output feeds v1.1 Phase 10.7 (Web Agent Surface) and the Models/Config surfaces touched by 10.10.

**Success criteria:**
1. A complete two-column inventory (ATLAS-better vs Hermes-has / ATLAS-missing) exists with evidence (file/route references).
2. A ranked adopt/adapt/skip backlog exists with rationale; "skip" items state why (e.g., wedge-plan scope guard).
3. The audit is research-only (no UI rebuild) and explicitly hands off to 10.7 / 10.10.
4. **Doctrine (§4):** designed, branded, state-aware provider controls are captured as a named adopt deliverable in the backlog (handed to 10.12 / 10.10), not left implicit.

**Depends on:** none. Independent — runs early/in parallel; mirrors the harness-cherrypick precedent (`docs/research/HARNESS_CHERRYPICK_PI_OPENCODE.md`).

---

## 7. Dependency spine and sequencing

```
10.15 (WebUI audit) ─── independent, run early/parallel ──┐
                                                          │ feeds 10.7 + 10.10
10.13 (boundary manifest) ── de-risks ──► 10.9 (mesh contract + dual-mode)
        │                                      │
        │                                      ▼
        │                                 10.10 (role rulebook)
        │                                      │
        │                                      ▼
        │                                 10.11 (scoring + dispatch + fallback)
        │                                      │
        │                                      ▼
        │                                 10.12 (provider backends)
        │                                      │
        └──────────────► 10.14 (autonomous self-evolution loop) ◄── needs stable tree
```

**Recommended order:** 10.15 (parallel) · 10.13 → 10.9 → 10.10 → 10.11 → 10.12 → 10.14.

Rationale: the manifest (10.13) is cheap and de-risks both the hybrid foundation backend and thread 2; the mesh contract (10.9) must precede rulebook/scoring/backends; the autonomous loop (10.14) is last because its test gate is only meaningful against a stable mesh tree and it carries the highest blast radius.

---

## 8. Risks and open questions

- **Autonomous commit blast radius (10.14).** Mitigations: manifest scoping, test gate, atomic commits, branch/PR, rollback, kill switch, audited autonomy dial with promotion criteria. Open: where the autonomy ceiling sits for self-modification (vs foundation-sync) and what human-in-the-loop checkpoint, if any, is permanent.
- **Hybrid coupling vs ATLAS ownership.** Leaning on foundation transports early speeds 10.12 but deepens coupling the rebuild must later unwind. The manifest keeps this explicit; open question is the rebuild order (which transports go ATLAS-native first).
- **Debrand × upstream-sync interaction (10.0.7 ↔ 10.13/10.14).** The classifier must treat scripted debrand rewrites as known transforms. Confirm 10.0.7 lands (or its rewrite rules are formalized) before 10.14 raises autonomy.
- **"openclaw" + "mimocode" definitions.** Treated here as a model-gateway and an agentic-CLI respectively. Confirm exact integration surface (CLI flags / API shape / auth) during 10.12 planning.
- **Effort-level semantics across providers.** "medium effort" maps differently per provider (reasoning effort, thinking budget, etc.). The rulebook schema needs a normalized effort abstraction with per-provider translation (10.10).
- **Budget pressure (D-022).** Health probes, scoring, and the self-evolution loop add background work; keep the Rust gateway dispatch-only and confirm daemon idle stays <80MB.

---

## 9. Decisions to log during planning

- **D-025** — Dual-mode Provider Mesh (ATLAS-gateway | BYO-runtime); two adapter shapes (agentic-CLI `RuntimeAdapter` + model-gateway router); generalizes P4 `AgentRuntime` ABC + D-017.
- **D-026** — Role-keyed model rulebook + capability/cost/health scorer + scored fallback cascade.
- **D-027** — Hybrid build basis with stated end state (foundation rebuilt to ATLAS-native over time); foundation boundary manifest as the enabling primitive.
- **D-028** — Autonomous gated self-evolution loop under GSD discipline; autonomy dial with promotion criteria.
- **D-029** — Extra-mile / extra-marathon delivery doctrine (§4): detect-don't-ask, pre-stage the next action, first-class branded surfaces, designed failure states; `l2-extra-marathon` review is the per-phase completion gate. Binding for the milestone.

---

## 10. Roadmap integration

Add to `.planning/ROADMAP.md` a new milestone block after v1.1 and before v2.0:

> **📋 v1.2 ATLAS Provider Mesh & Self-Evolution (Phases 10.9–10.15)** — dual-mode provider-agnostic cockpit, role-keyed model rulebook + scored dispatch, autonomous self-evolution loop, and a WebUI gap audit. Spine: 10.13 + 10.15 (early) → 10.9 → 10.10 → 10.11 → 10.12 → 10.14.

Renumber nothing in v2.0 (Phases 11–14 unaffected). Trace requirements into `.planning/REQUIREMENTS.md` per phase during `/gsd-plan-phase`.

---

## 11. Out of scope

- v1.1 work (10.1–10.8) — this milestone sequences after it and consumes its surface/session/config/permission contracts.
- Native/Tauri shell — remains deferred per v1.1 until the surface protocol is stable.
- CRM/Pulse/Voice (v2.0).
- A WebUI rebuild — 10.15 is audit-only; build lands in 10.7 / 10.10.
