# D-015 — FreeLLMAPI Sidecar Gateway

**Status:** Accepted for integration spike  
**Date:** 2026-06-07  
**Scope:** ATLAS/Hermes low-cost inference routing, provider fallback, and audit capture.

## Context

ATLAS needs a low-cost/free inference lane for non-critical work: classification, summarization, draft generation, background agents, embeddings experiments, and cheap fallback routing. The repository `tashfeenahmed/freellmapi` provides a local OpenAI-compatible gateway that aggregates multiple free-tier/keyless/provider-backed LLM routes behind `/v1/chat/completions`, `/v1/models`, `/v1/responses`, and `/v1/embeddings`.

Repository inspected:

```text
https://github.com/tashfeenahmed/freellmapi
commit (initial audit): 43415fd
commit (latest as of 2026-06-08): bfea8a894718130609fc15a798a424e23fbf8a68
license: MIT
```

Project report:

```text
docs/research/FREELLMAPI_INTEGRATION_SPIKE_2026-06-07.md
```

Operational smoke docs:

```text
docs/operations/FREELLMAPI_CLOSED_ENV_SMOKE.md
docs/operations/FREELLMAPI_REAL_KILO_SMOKE.md
```

## Decision

Use FreeLLMAPI as a **sidecar OpenAI-compatible provider gateway**, not as vendored ATLAS core code.

Initial architecture:

```text
ATLAS / Hermes
  -> http://127.0.0.1:<port>/v1
  -> FreeLLMAPI sidecar
  -> configured upstream provider or keyless/free route
```

Do not vendor FreeLLMAPI into ATLAS at this stage.

## Evidence

### Closed-environment test

Script:

```text
scripts/freellmapi_closed_env_smoke.py
```

Result:

```text
PASS: FreeLLMAPI routed model=auto through the local mock custom provider.
```

This proved local sidecar routing works with no external LLM calls and no provider keys.

### Real-provider test

Script:

```text
scripts/freellmapi_real_kilo_smoke.py
```

Provider/model:

```text
platform: kilo
model: stepfun/step-3.7-flash:free
```

Result:

```text
chat status: 200
content: ATLAS_REAL_SMOKE_OK
```

Routing metadata:

```json
{
  "_routed_via": {
    "platform": "kilo",
    "model": "stepfun/step-3.7-flash:free"
  }
}
```

## Consequences

### Positive

- Gives ATLAS a real low-cost/free inference lane.
- Compatible with Hermes custom OpenAI provider configuration.
- Keeps provider keys isolated from ATLAS core DB initially.
- Can expose routed provider/model metadata for ATLAS audit events.
- Avoids pulling Node/Electron dependency burden into the Python/Rust runtime.

### Negative / Risk

- Free-tier availability is unstable.
- Provider ToS varies; keyless/free routes may log prompts/outputs.
- Another local process must be supervised.
- Not suitable for private L2/client material unless the upstream route is explicitly trusted.
- npm audit found advisories during intake; review before distribution/forking.

## Policy

Use FreeLLMAPI only for task classes explicitly marked safe for free-tier routing:

- non-sensitive summarization;
- classification;
- draft generation;
- low-risk background exploration;
- synthetic tests;
- non-private embeddings experiments.

Do **not** use it for:

- secrets;
- client/private L2 data;
- production commitments;
- high-stakes admissions/security/business material;
- tasks requiring stable frontier-model reliability.

## Required follow-up

Add a Phase 4.5 or Phase 5 sub-plan to prove:

1. ATLAS/Hermes can call FreeLLMAPI through a custom OpenAI-compatible provider.
2. FreeLLMAPI health is checked before routing.
3. ATLAS classifies task routing as `free-tier-ok` vs `paid-required`.
4. `_routed_via` / `X-Routed-Via` / fallback metadata is captured in `AuditEvent.data`.
5. Failure is clean: if sidecar is down/exhausted, ATLAS falls back or refuses clearly.

## Disposition

Accepted for spike. Sidecar first, managed sidecar second, fork/vendor last.

### Fork/vendor trigger criteria (added 2026-06-10, D-021 §7)

Fork or vendor only if **at least two** of the following hold; otherwise FreeLLMAPI stays a pinned, supervised, unbranded sidecar:

1. Upstream unmaintained > 90 days while provider routes rot (breaking ATLAS task classes).
2. A production-relevant security advisory remains unpatched upstream > 30 days.
3. ATLAS requires a routing/gateway feature upstream has explicitly rejected.
4. An ATLAS distribution must bundle the gateway (no external-install option viable).
