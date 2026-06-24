# D-023 — One ATLAS Agent, Multi-Surface Workbench

**Date:** 2026-06-23
**Status:** Accepted
**Refines:** D-018, D-019, D-021, D-022
**Defers:** v1.1 Tauri/native shell until the surface protocol is stable

## Context

ATLAS already has an agent/runtime, Project registry, Current Focus, missions/runs, audit bus,
configuration service, MemoryRouter, wiki, knowledge-graph view, and persisted tool approvals.
The terminal experience needs a stronger interaction harness, but importing another agent,
provider layer, memory store, configuration system, or policy engine would create conflicting
authorities.

A third-party terminal project provides useful rendering, session, permission-dialog, task, and
interaction patterns. It is a donor/reference for the ATLAS TUI only.

## Decision

1. ATLAS has one agent/runtime and multiple clients: CLI, TUI, WebUI, API, and a future native
   shell.
2. Donor terminal code is transformed into ATLAS-owned code. Runtime packages, symbols, commands,
   configuration keys, environment variables, state paths, network identifiers, generated
   artifacts, and UI strings use ATLAS names only.
3. Donor provenance remains explicit in `ATTRIBUTION.md`, third-party notices, retained license
   text, and design-history documentation.
4. Every execution is represented by an ATLAS surface session bound to a global workspace or a
   registered Project root.
5. `~/.atlas/config.yaml` and ATLAS auth/model registries are authoritative across surfaces.
6. ATLAS policy and persistence own permission requests. Only the initiating surface session may
   render and resolve its actionable queue. Other surfaces may observe terminal audit outcomes.
7. The agent prompt is compiled from versioned layers. Stable identity/policy/tool invariants are
   cache-stable; dynamic project, mission, wiki, Brain, skill, and run context is separately
   budgeted, redacted, provenance-tagged, and replayable.
8. The Brain knowledge graph is the retrieval spine. Retrieval expands from graph entities and
   relationships into wiki pages, observations, runs, artifacts, and skills. Low-confidence
   retrieval abstains.
9. No new general-purpose agent/RAG framework is adopted. Existing ATLAS/Hermes extension seams,
   frozen Pydantic contracts, SQLite/FTS5/vector fallback, and Rust gateway remain the stack.

## Consequences

- v1.1 is restructured as Phases 10.1–10.8.
- Tool-call and prompt/context conformance are stabilized before surface implementation.
- The WebUI and TUI receive one normalized event protocol.
- Tauri work resumes only after terminal/web parity and permission isolation are proven.
- A small attribution burden and donor-upstream diff process remain, but no second runtime is
  shipped.
