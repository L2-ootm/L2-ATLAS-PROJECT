# ATLAS TUI and Agent Contract Design

**Date:** 2026-06-23
**Decision:** Proceed through v1.1 Phases 10.1–10.8

ATLAS will transform a third-party terminal harness into an ATLAS-native client while retaining
one existing ATLAS agent/runtime. Terminal and web surfaces share the Project registry, Current
Focus, missions/runs, normalized event stream, global configuration, audit bus, Brain/wiki
context, and permission broker.

No donor product identity or runtime namespace ships in code, packages, paths, configuration,
environment variables, output, or generated artifacts. Provenance remains in attribution,
license notices, and design history.

The behavioral foundation is Phase 10.2: a deterministic prompt compiler, machine-readable tool
capability catalog, graph-guided RAG/context protocol, identity/bootstrap envelope, compaction and
resume rules, and rigorous eval suite. Surface implementation cannot begin by copying prompts or
tool behavior ad hoc.

Permission requests are persisted and audited by ATLAS but routed by initiating surface session.
The TUI renders a native blocking prompt; the WebUI renders a conditional right queue/sidebar and
minimal active-session header. Headless execution denies interactive requests unless an explicit
approval channel exists.

The Brain knowledge graph is the retrieval spine. It identifies related entities and paths, then
expands into wiki pages, observations, runs, artifacts, sources, and skills. Retrieval is
budgeted, provenance-bearing, trust-labeled, freshness-aware, and able to abstain.

Cross-surface conformance and adversarial testing gate cutover. Tauri/native-shell work remains
deferred until the protocol is stable.
