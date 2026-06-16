# ATLAS Fallback-Cascade Error-Classification Contract

> **Phase 10.0 design artifact — committed decision, no runtime code.**
> This document is the canonical halt-vs-cascade contract that **Phase 10.2**
> implements in the ATLAS adapter. It commits the error→action classification
> table, the OpenAI-first cascade ordering, the bounded-attempt semantics, and
> the load-bearing landmines — so 10.2 builds against a reviewed spec rather
> than rediscovering the `400`-overload and non-conformant-provider edge cases
> the hard way.

**Status:** committed design (reviewable artifact)
**Mirrors:** v1.0 Phase 7 design-phase shape (clear goal, explicit "owns no
REQ-IDs", numbered TRUE-criteria, hand-off contract to the consuming phase).

## Goal

Provide the canonical mapping from provider error conditions to cascade actions
(`HALT`, `CASCADE`, `model-scoped`) and specify the ordering, audit, and
bounded-attempt semantics of the cascade. The ATLAS adapter (see
`ADAPTER_BOUNDARY_DESIGN.md`) **owns** this cascade and is the sole entity
responsible for executing it. The Hermes `AIAgent` native `fallback_model` kwarg
is deliberately **not** used for this purpose — see ADAPTER_BOUNDARY_DESIGN.md
responsibility (b).

## Requirements ownership

**This document owns no v1 REQ-IDs; de-risks AGNT-02, AGNT-03, AUD-01
(owned by 10.2).**

It de-risks **AGNT-02** (health-ordered fallback cascade), **AGNT-03** (no silent
auth-failure cascade; provider surfaced on response), and **AUD-01**
(`provider_fallback` audit event), all owned by Phase 10.2. Precedent: v1.0
Phase 7 design-phase shape.

## Success criteria (what must be TRUE)

1. Every provider error condition is classified as exactly one of: `HALT`,
   `CASCADE`, or `model-scoped`.
2. `401` and `403` auth errors are always `HALT` — they **never** silently
   cascade to the next provider (AGNT-03).
3. The OpenAI/Codex-compatible lane goes **first**; remaining providers are
   ordered by **health/liveness**, not fixed priority (AGNT-02).
4. A **bounded total-attempt budget** (default N=3 distinct providers) prevents
   long hangs; each provider is attempted **at most once** per request.
5. The **provider actually used** is surfaced on the response (AGNT-03).
6. Every CASCADE-class advance emits `provider_fallback{from, to, reason}`
   (AUD-01).
7. A provider content refusal (200, valid response body) is **NOT an error** —
   return to the user; do not cascade.
8. A `400` error cannot be classified from status code alone — body inspection
   is required; when ambiguous, the safe default is `HALT` (LANDMINE 6).
9. Non-conformant provider responses (garbled, 200-with-error-body,
   bare-connection-error) are treated as `CASCADE`-class transport failures
   (LANDMINE 7).

## Error-classification table

| Condition | HTTP status | OpenAI SDK exception | Action | Notes |
|-----------|-------------|----------------------|--------|-------|
| Auth invalid / expired | 401 | `AuthenticationError` | **HALT** | Never cascade; surface `atlas auth add <provider>` remediation; emit audit |
| Permission denied | 403 | `PermissionDeniedError` | **HALT** | Never cascade; surface remediation; emit audit |
| Network / DNS / timeout / connection refused | — | `APIConnectionError` / `APITimeoutError` | **CASCADE** | Emit `provider_fallback{from, to, reason}` |
| Server error | 500 / 5xx | `InternalServerError` | **CASCADE** | Emit `provider_fallback` |
| Rate limited | 429 | `RateLimitError` | **CASCADE** | Mark provider `rate_limited` / temp-unavailable; emit `provider_fallback` |
| Model not found | 404 | `NotFoundError` | **model-scoped** | Cascade only to a source that carries that model; otherwise HALT "model unavailable" |
| Unsupported model / model param | 400 (body-confirmed) | `BadRequestError` | **model-scoped** | Requires body inspection to confirm; cascade to source carrying the model |
| Malformed request / our bug | 400 (body-confirmed) | `BadRequestError` | **HALT** | Cascading cannot help; surface as internal error; see LANDMINE 6 |
| Ambiguous 400 (body uninspectable) | 400 | `BadRequestError` | **HALT** | Safe default when body inspection is inconclusive; see LANDMINE 6 |
| Provider content refusal / valid-but-declined | 200 (no exception) | *(none)* | **NOT an error** | Return to user; do not cascade |
| Garbled / non-conforming response | varies | *(may not raise SDK exception)* | **CASCADE** (transport failure) | See LANDMINE 7 |

The parent class for any non-2xx response is `openai.APIStatusError`, which exposes
`.status_code` and `.response`. The classifier branches on `isinstance` against the
typed SDK subclasses (precise path) and falls back to `.status_code` ranges for
non-SDK callers. For non-conformant providers see LANDMINE 7.

## HALT semantics

A `HALT` stops the cascade immediately and surfaces the error to the user with
remediation text:

- **401 / 403:** `atlas auth add <provider>` or `atlas auth doctor`
- **400 our-bug:** internal error trace (do not surface raw provider message)
- **404 no-source-with-model:** "model `<model>` not available on any configured provider"

Auth failures (401/403) **must never silently fall through** — surfacing them as a
cascade advance would mask credential problems and confuse the operator. This is the
AGNT-03 hard gate.

Emit a structured audit event on every HALT (reason + provider + status code) so
the operator can diagnose failures after the fact.

## CASCADE semantics and ordering

### Lane membership (OpenAI-first)

The OpenAI/Codex-compatible lane goes first. Lane membership is defined by
`api_mode` value, **not** by hardcoded provider names:

```
api_mode ∈ { chat_completions, responses, codex_responses }
```

Any provider configured with one of these `api_mode` values is in the
OpenAI-compatible lane and is tried before other providers. Within the lane,
order is by **health/liveness** (most-recently-successful first), not fixed
priority.

### Remaining providers

Providers not in the OpenAI-compatible lane are ordered by **liveness/health** —
whichever provider last responded successfully goes next. No fixed priority list.

### Bounded attempt budget

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `max_providers_per_request` | 3 distinct providers | Prevents long hangs on a large configured set; tunable in 10.2 |
| Attempts per provider | 1 | Each provider is attempted at most once per request; no per-provider retry |

The adapter tracks `providers_tried` per request. When `len(providers_tried) >=
max_providers_per_request` and no provider succeeded, surface a final error
summarising all cascade reasons.

### Audit on each cascade advance

On every CASCADE-class error that advances to the next provider:

```
provider_fallback {
    from:   "<provider_id>",
    to:     "<next_provider_id>",
    reason: "<error class and code, e.g. APIConnectionError / timeout>"
}
```

Emitted via `atlas_audit` on the ATLAS event bus (AUD-01).

### Provider-used surfaced on response

On success, annotate the response with the provider that actually handled the
request (AGNT-03). Minimum: a structured field `provider_used: <provider_id>` in
the adapter's response wrapper.

## LANDMINE 6 — `400` requires body inspection; default is HALT

A single HTTP `400 BadRequestError` covers at least two distinct conditions:

1. **Unsupported model / model parameter** — the provider simply does not carry
   that model. Correct action: **model-scoped cascade** (try another provider that
   does carry the model).
2. **Malformed request / our bug** — the request body itself is invalid (wrong
   schema, unsupported parameter combination, etc.). Cascading cannot help —
   every provider will return the same 400 because the request is malformed.
   Correct action: **HALT**.

The classifier **cannot** distinguish these two conditions from the status code
alone. It must inspect the error body — specifically the `code` and/or `message`
fields from the response JSON — to determine which branch applies.

**Safe default when ambiguous:** `HALT`.

Cascading an ambiguous 400 to N providers multiplies the same error N times and
burns the entire attempt budget without helping the operator. When body inspection
is inconclusive (non-JSON body, missing `code` field, or unrecognized code value),
the classifier defaults to HALT and surfaces an internal error with the raw
provider message for operator diagnosis.

The exact disambiguation heuristic (which `code` values map to "unsupported model"
vs "our-bug") is an open implementation detail deferred to 10.2. The load-bearing
invariant to carry forward: **never cascade a 400 without confirming it is model-
scoped by body inspection**.

## LANDMINE 7 — non-conformant providers; treat garbled responses as CASCADE

OpenAI-compatible providers — local sidecars (LM Studio, Ollama, FreeLLMAPI),
OpenRouter, and similar — **do not always return the exact OpenAI status code or
error body** for a given failure condition. Observed patterns:

- A down sidecar may yield a bare TCP connection error (no HTTP response at all).
- Some providers return `200` with an error JSON body (e.g.
  `{"error": {"message": "…", "type": "…"}}`), which the OpenAI SDK may not
  raise as a typed exception.
- Some return non-standard `4xx` codes or omit the `code` field the classifier
  expects.

The classifier must therefore handle the case where the OpenAI SDK exception does
**not** fire cleanly (e.g. `httpx.ConnectError`, `json.JSONDecodeError`, or a raw
`requests.ConnectionError` bubbling through). Any **non-conforming or garbled
response** — one that does not map to a recognized typed SDK exception and does not
yield a clean HTTP response body — is treated as a **CASCADE-class transport
failure**:

```
provider_fallback {
    from:   "<provider_id>",
    to:     "<next_provider_id>",
    reason: "non-conformant response / transport error"
}
```

This maintains the defensive, loopback-only-trust posture that the v1
`model_registry.py` already applies (`fetch_gateway_models` only trusts loopback
hosts). The v1.1 cascade must keep that defensive stance: when in doubt, treat
the provider as transiently unavailable and cascade, rather than halting on an
uninspectable error.

## Refusal is not an error

A provider content refusal is a valid response, not an error:

- The provider returns HTTP `200`.
- The response body contains a refusal message (e.g. the model declines to answer).
- No OpenAI SDK exception is raised.

The adapter **must not** cascade on a refusal. It is not a transport failure, an
auth failure, or a rate-limit — it is a valid response from the provider to the
operator's request. Return the response to the user unchanged.

## Hand-off contract to Phase 10.2

10.2 implements this contract in the adapter (`ADAPTER_BOUNDARY_DESIGN.md`
responsibility (b)) and must, at minimum:

- Classify every provider error against the table above before advancing the
  cascade.
- Halt on 401/403 — no exception.
- Inspect the `400` body before deciding cascade vs HALT; use safe-default-HALT
  when ambiguous.
- Treat garbled/non-conformant responses as CASCADE transport failures.
- Build the candidate provider list with `api_mode`-lane membership (not
  hardcoded names) and health-ordered ordering.
- Enforce a bounded attempt budget (`max_providers_per_request`, default 3).
- Emit `provider_fallback{from, to, reason}` on every CASCADE advance.
- Surface the winning provider on the response.
- NOT cascade on a content refusal (200).
- Resolve open questions: exact 400 disambiguation heuristic; final attempt-budget
  value; per-call token usage availability from the response path for
  `model_call_end` audit.
