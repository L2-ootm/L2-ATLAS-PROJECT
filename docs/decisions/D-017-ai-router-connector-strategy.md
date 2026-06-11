# D-017 — ATLAS AI Router Connector Strategy

**Date:** 2026-06-08
**Status:** Accepted
**Scope:** Model/provider routing architecture, FreeLLMAPI sidecar integration, dynamic model discovery, and audit trail for all LLM calls.

---

## Decision

ATLAS adopts a policy-governed AI router connector architecture with the following commitments:

1. **FreeLLMAPI remains sidecar-first.** It is not vendored into ATLAS core. It runs as a separate process on loopback, configured via `model.provider = "custom"` and `model.base_url`.

2. **ATLAS owns all routing decisions.** The model router (`atlas_core.model_router`) selects models based on task class and policy labels. FreeLLMAPI is one of several possible routing targets.

3. **Hermes provider/auth infrastructure is reused where practical.** The `ProviderTransport` ABC, credential pool, custom endpoint mechanism, and OAuth flows are used directly. ATLAS does not reimplement them.

4. **A structured model registry (`atlas_core.model_registry`) is added to ATLAS core.** It holds queryable model entries with provenance, capability tags, policy labels, and health status. It is populated from configured providers and dynamic discovery (FreeLLMAPI `/v1/models`, Codex/Kilo catalogs where available).

5. **Auto-discovered models are treated as untrusted until classified.** Discovery source `DISCOVERED_*` entries carry `experimental` policy label by default. Operators promote models explicitly.

6. **Credentials stay in Hermes-compatible auth store or OS keychain.** No credential enters the ATLAS database, AuditEvent payload, or cockpit webview state.

7. **Every LLM call emits a full AuditEvent** with model ID, provider, source, task class, policy labels, latency, and token usage. The `routed_via` metadata from FreeLLMAPI response headers is captured in the payload.

8. **Routing fails safely.** If no eligible model exists for a task class and policy combination, the run is refused with a typed error. The runtime does not default to an unsafe provider.

---

## Rationale

ATLAS needs a low-cost inference lane for background, classification, summarization, and draft-generation work. Paying full provider rates for these tasks is unnecessary and expensive over the long term.

FreeLLMAPI (D-015) proved viable via smoke tests (closed-env mock PASS, real Kilo PASS with `ATLAS_REAL_SMOKE_OK`). Model benchmarks (2026-06-07) confirmed that Groq-routed models under FreeLLMAPI have acceptable latency (~250–721ms) and output quality for non-critical tasks.

The sidecar pattern keeps ATLAS clean: no TypeScript/Node dependency in the Python runtime, no vendor lock-in to FreeLLMAPI specifically, and a clear replacement path if a better free-tier gateway appears.

Hermes already has the provider transport and credential infrastructure needed. Reusing it avoids duplicate work and keeps ATLAS coherent with its Hermes foundation.

The model registry is the missing structural piece: without it, model selection is static and operators cannot discover or control which models are available for which task classes.

---

## Routing Principle: Task Class, Not Model Name

Mission definitions declare task classes (`mission_planning`, `code_generation`, `summarization`, `embeddings_experiment`). The router selects the best available, policy-compliant model at execution time.

This decouples mission definitions from provider/model changes. When a new high-quality free-tier model is discovered and promoted, it is automatically available without changing any mission configuration.

---

## Policy Labels

| Label | Enforcement |
|-------|------------|
| `free-tier-ok` | Safe to route to FreeLLMAPI, keyless, or any free provider |
| `paid-ok` | Requires configured provider credentials |
| `local-only` | Must route to a local model (Ollama, llama.cpp) |
| `trusted-provider` | Only route to providers with enterprise ToS (no training on data) |
| `experimental` | Operator explicitly accepted risk of using unvalidated model |
| `no-sensitive-data` | Apply PII/secret detection before sending prompt |

Default policy for newly discovered models: `experimental`, `no-sensitive-data`.

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Free-tier provider availability fluctuates | CONFIG fallback always present; health tracking with backoff |
| Provider ToS on free-tier routes may log prompts | `no-sensitive-data` label enforced for all free/keyless routes by default |
| FreeLLMAPI npm audit found vulnerabilities (1 critical, 1 high) | Do not distribute FreeLLMAPI; do not expose its admin port; loopback only |
| Discovered model catalog could contain malicious or mislabeled entries | `experimental` label + operator promotion gate before use in sensitive task classes |
| OAuth token exposure via discovery API | Never include OAuth tokens in discovery requests to untrusted catalog sources; use Hermes-managed auth only |
| Odysseus license (reference pillar) | **Resolved:** MIT confirmed (Phase 4.5, SHA `8449baea80db7763e713685ec98760cd8d398802`). Code may be adapted with attribution. |

---

## Follow-Up Actions

| Action | Phase |
|--------|-------|
| Add `atlas_core.model_registry` module and schema | Phase 5 adjunct or Phase 6 |
| Add `atlas_core.model_router.select()` with task-class table | Phase 5 adjunct or Phase 6 |
| Add FreeLLMAPI health probe on ATLAS runtime startup | Phase 5 adjunct (D-015 follow-up) |
| Expose `GET /models` and `GET /providers/status` via Phase 7 API | Phase 7 |
| Cockpit provider/model settings surface | Phase 8 |
| Codex/OpenCode model catalog discovery (if OAuth present) | Phase 7 or Phase 8 |
| Operator model promotion CLI (`atlas models promote <id>`) | Phase 7 |

---

## What This Decision Does NOT Authorize

- Vendoring FreeLLMAPI into ATLAS.
- Routing any sensitive, client, or L2-private data to free-tier/keyless providers.
- Bypassing the ATLAS policy engine for provider selection.
- Exposing credentials to the model registry or cockpit webview.
- Starting Phase 6, 7, or 8 implementation ahead of schedule.
