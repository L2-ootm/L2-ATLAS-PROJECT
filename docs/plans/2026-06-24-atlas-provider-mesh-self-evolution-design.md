# ATLAS Provider Mesh & Self-Evolution — Corrected Portfolio Design

**Date:** 2026-06-24
**Status:** Scoped into milestone drafts; not active work
**Active milestone remains:** v1.1 ATLAS Agent Harness & Multi-Surface Workbench
**Supersedes:** the original combined v1.2 scope retained in
`2026-06-24-atlas-provider-mesh-self-evolution-design-superseded.md`

## 1. Decision

Preserve all proposed work, but split it according to dependency and risk:

- **v1.2 draft — Provider Mesh & Runtime Interoperability:** foundation boundary,
  WebUI evidence audit, capability-aware runtime/model routing, role profiles,
  scoring, and conformant provider backends.
- **v1.3 candidate — Gated Self-Evolution:** a separately activated,
  evidence-promoted foundation-sync pilot. It is not a provider-mesh release gate.

The active `.planning/ROADMAP.md` contains only v1.1 phase headings. Future work
uses milestone-local IDs until activation, preventing GSD progress pollution and
avoiding premature global phase or ADR-number reservation.

Sources of truth:

- `.planning/milestones/v1.2-ROADMAP-DRAFT.md`
- `.planning/milestones/v1.2-REQUIREMENTS-DRAFT.md`
- `.planning/milestones/v1.3-SELF-EVOLUTION-DRAFT.md`

## 2. Why the original scope needed correction

The original design contained valuable ideas but mixed three planning layers:

1. active v1.1 execution;
2. a provider-interoperability milestone;
3. autonomous repository mutation.

That created concrete problems:

- future `Phase 10.9`–`10.15` headings were parsed as active roadmap phases;
- the boundary manifest appeared after work that depended on it;
- a future WebUI audit claimed it would feed an earlier v1.1 phase;
- proposed ADR numbers collided with Graphify decisions already pending as
  `D-025`–`D-028`;
- it proposed a second `RuntimeAdapter` ABC despite the existing `AgentRuntime`;
- it treated all external runtimes as if ATLAS could enforce their permissions;
- self-evolution made the lower-risk provider mesh depend on its highest-risk work;
- completion depended on a named review skill not installed in this workspace.

The corrected scope resolves these issues without deleting the ideas.

## 3. Existing foundation to extend

ATLAS already has:

- `AgentRuntime` in `services/agent-runtime/atlas_runtime/agents/`, including
  `native` and `claude_code`;
- D-017 model registry/router behavior;
- `registry_v2` provider/model/route tables;
- Phase 10.0 fallback error classification;
- `~/.atlas/config.yaml` and a shared config service;
- audit, policy, permission, project, session, and run concepts that v1.1 is
  consolidating across surfaces.

Therefore v1.2 evolves existing contracts. It does not create a parallel runtime
abstraction or import an external product's control plane.

## 4. Correct runtime model

### 4.1 Capability tiers

Every backend declares one enforceable tier:

| Tier | Agent loop owner | ATLAS write enforcement | Required contract |
|---|---|---:|---|
| Model gateway | ATLAS | Yes | model calls, cancellation/timeout, route metadata |
| Controlled agent runtime | External runtime | Only after conformance | normalized events, cancel, workspace binding, permission bridge |
| Opaque external runtime | External runtime | No | detection/observation/read-only or advisory integration |

ATLAS must never describe an opaque runtime as policy-enforced. Opaque backends
cannot be used for write-capable sessions through ATLAS.

### 4.2 Defaults versus bindings

A global mode/profile is a default, not mutable truth for an active run.

Resolution is:

`global default → project override → session selection → immutable run binding`

Each run records the effective runtime, capability tier, provider/model profile,
permission mode, and contract version. Configuration changes affect new sessions
unless an explicit safe transition contract exists; they never hot-switch a live run.

### 4.3 ATLAS-to-ATLAS routing

Routing through another ATLAS gateway requires:

- route/correlation trace ID;
- visited-gateway list or equivalent cycle token;
- bounded hop count;
- deterministic cycle rejection;
- audit evidence at every hop;
- bounded timeout and cancellation propagation.

## 5. Discovery and onboarding

The operator experience keeps the original extra-mile intent with tighter safety:

- perform local, read-only detection first;
- show what ATLAS can prove before requesting configuration;
- never run paid/network health probes at startup without opt-in;
- cache network probe results under explicit timeout, traffic, and cost budgets;
- prebuild safe configuration proposals rather than silently applying them;
- keep the least invasive supported path as the default;
- make migration explicit and reversible;
- design offline, unavailable, denied, unhealthy, and misconfigured states.

For external agent products, “route through” is allowed only at the capability
tier proven by conformance. A detected CLI is not automatically trusted with writes.

## 6. v1.2 draft structure

### PM-01 — Foundation Boundary Manifest & Upstream Delta

Runs first because it defines the foundation/backend boundary. It classifies all
foundation modules and generates reproducible reports. v1.2 does not auto-apply
or commit upstream changes.

### PM-02 — Bidirectional WebUI Gap Audit

Runs early in parallel. It protects ATLAS strengths and creates an evidence-backed
adopt/adapt/skip backlog for provider/profile work. It feeds `PM-04` and `PM-06`,
not the already active v1.1 Phase 10.7.

### PM-03 — Provider Mesh Contract & Dual-Mode Control Plane

Versions `AgentRuntime` capabilities, extends model routing, establishes capability
tiers and immutable run binding, and adds ATLAS route-cycle guards.

### PM-04 — Role-Keyed Model Rulebook

Defines provider/model/effort mappings per role through the existing config
control plane and records exact bindings for replay.

### PM-05 — Capability, Cost & Health Scoring

Fills rulebook gaps with deterministic, explainable scoring and drives the existing
fallback classification. Manual assignments remain authoritative.

### PM-06 — Provider Backends & Conformance

Ships only backends whose declared tier can be tested honestly. External MiMo,
OpenCode, Codex, or similar products remain integrations; their runtime, config,
auth, telemetry, and identity are not imported.

Dependency spine:

`PM-01 + v1.1 10.3/10.4/10.5/10.8 → PM-03 → PM-04 → PM-05 → PM-06`

`PM-02` runs early and supplies evidence to `PM-04` and `PM-06`.

## 7. v1.3 self-evolution candidate

The original autonomous loop is preserved as `EV-01`, but activation requires:

- stable v1.2 boundary reports;
- green project conformance/security/test gates;
- branch isolation, rollback, audit, and kill-switch proof;
- explicit compute/network/token budgets;
- a canonical decision defining the autonomy ceiling.

Promotion is evidence-based:

`observe → propose → validate → publish candidate → possible tracked auto-merge`

The initial release ceiling is observe/propose unless a later decision authorizes
more. General ATLAS self-modification remains beyond the foundation-sync pilot.

## 8. Decisions

Do not reserve canonical ADR numbers while the milestone is a draft. Use:

- **PM-DEC-01:** capability-tiered dual-mode provider mesh;
- **PM-DEC-02:** role rulebook plus bounded explainable scoring;
- **PM-DEC-03:** hybrid foundation backend governed by a boundary manifest;
- **EV-DEC-01:** self-evolution is separately activated and evidence-promoted;
- **L2-DOCTRINE-01:** detect locally, pre-stage safe actions, design failure states,
  preserve reversibility, and verify with installed quality gates.

At milestone activation, allocate non-conflicting canonical ADR IDs and record the
mapping from draft keys.

## 9. Quality and anti-bloat gates

Use available gates rather than a nonexistent named skill:

- requirement traceability and plan verification;
- `gsd-code-review`;
- `gsd-secure-phase` for runtime/control-plane work;
- `gsd-verify-work`;
- `gsd-ui-review` for changed operator surfaces;
- dependency and artifact-size review;
- measured startup, idle-memory, probe-traffic, latency, and cost budgets.

D-022 remains binding: Rust-first for new infrastructure, Python limited to the
approved Hermes/plugin/adapter surfaces, and no new framework dependency without
a decision.

## 10. Activation and numbering

When v1.1 is complete:

1. archive v1.1 through the milestone workflow;
2. review the v1.2 draft against the final v1.1 contracts;
3. allocate canonical phase numbers;
4. promote and normalize draft requirements;
5. allocate canonical ADR IDs without collision;
6. plan `PM-01` and `PM-02`;
7. keep `EV-01` outside v1.2.

Until then, these drafts are portfolio planning, not executable active phases.
