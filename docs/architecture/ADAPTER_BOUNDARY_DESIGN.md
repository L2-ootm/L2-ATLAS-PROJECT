# ATLAS Adapter / Foundation Boundary Design

> **Phase 10.0 design artifact — committed decision, no runtime code.**
> This document is the adapter/foundation boundary that **Phase 10.2** implements
> against. It commits the composition model, the one-way dependency direction, the
> five adapter responsibilities, the wrap-not-rewrite hard gate, and the
> DIVERGENCE_LOG reconciliation — so 10.2 builds against a reviewed spec rather
> than rediscovering the naming drift and cascade-ownership questions the hard way.

**Status:** committed design (reviewable artifact)
**Mirrors:** v1.0 Phase 7 design-phase shape (clear goal, explicit "owns no
REQ-IDs", numbered TRUE-criteria, hand-off contract to the consuming phase).

## Goal

Define the boundary between the ATLAS runtime adapter and the vendored Hermes
foundation (`AIAgent`). The adapter wraps the foundation by **composition**
(import + instantiate `AIAgent`), with a **one-way dependency** that keeps the
foundation re-syncable against upstream and all ATLAS-specific logic — credential
resolution, fallback cascade, audit emission, and transcript redaction — in
ATLAS-owned code. This boundary is the adapter/foundation contract that 10.2
builds against.

## Requirements ownership

**This document owns no v1 REQ-IDs; de-risks AGNT-01..06 (owned by 10.2).**

It de-risks **AGNT-01** (wrap, never rewrite), **AGNT-02** (fallback cascade),
**AGNT-03** (provider surfaced on response / no-silent-auth-cascade), **AGNT-04**
(audit emission), **AGNT-05** (tool-approval gates preserved), and **AGNT-06**
(transcript redaction), all of which are **owned by Phase 10.2**. Precedent: v1.0
Phase 7 was a design/enabling phase that owned no REQ-IDs and de-risked the
phases that consumed it.

## Success criteria (what must be TRUE)

1. The ATLAS adapter lives in `services/agent-runtime/atlas_runtime/` (e.g.
   `chat/adapter.py`) and wraps the Hermes `AIAgent` by **composition** — it
   imports `AIAgent` from `foundation/atlas-hermes/run_agent.py` and instantiates
   it; it does **not** subclass it.
2. The dependency is **one-way**: `services/agent-runtime` depends on
   `foundation/`; the foundation **never** imports from `services/`. The only
   path by which the foundation references ATLAS-owned code is the registered-
   plugin shim precedent (D-LOG-002: `atlas_audit`).
3. The **AGNT-01 hard gate** holds: no parallel second chat runtime. Any
   foundation change is an extension point recorded in `DIVERGENCE_LOG.md`, never
   a rewrite of the Hermes agent loop.
4. The adapter fulfils exactly the five responsibilities listed below (a–e) and
   no more; all other agent-loop concerns belong to the foundation.
5. The cascade is **adapter-driven** (not delegated to Hermes' native
   `fallback_model` kwarg), so error classification, health-aware ordering, and
   `provider_fallback` audit emission all stay in ATLAS code.
6. The DIVERGENCE_LOG uses the **`D-LOG-NNN`** canonical id scheme; the
   `DIV-F-*` references in older CONTEXT docs are superseded.

## Adapter location

```
services/agent-runtime/atlas_runtime/chat/adapter.py   (or agent_adapter.py)
```

The module lives in `services/agent-runtime/`, making its dependency on
`foundation/atlas-hermes` a standard upward dependency: service-layer depends on
foundation, never the reverse.

## Composition model

```python
# Illustrative — not the final implementation
from foundation.atlas_hermes.run_agent import AIAgent   # import, not subclass

class AtlasAgentAdapter:
    def __init__(self, provider_cfg, route_policy, run_id):
        creds = resolve_credentials(provider_cfg)         # from auth store
        self._agent = AIAgent(                            # composition
            base_url=creds.base_url,
            api_key=creds.api_key,
            provider=creds.provider_id,
            api_mode=creds.api_mode,
            model=route_policy.model,
            # callbacks wired here (see responsibility (d)):
            clarify_callback=self._on_clarify,
            ...
        )
```

The `AIAgent.__init__` at `run_agent.py:350–417` is a keyword forwarder into
`agent.agent_init.init_agent`. The load-bearing constructor kwargs the adapter
must supply are: `base_url`, `api_key`, `provider`, `api_mode`, `model`,
`max_iterations`, `enabled_toolsets`, the streaming/approval callbacks
(`tool_progress_callback`, `clarify_callback`, `step_callback`,
`stream_delta_callback`, `status_callback`), `fallback_model`, and
`credential_pool`. The native `fallback_model` and `credential_pool` hooks exist
but the adapter does **not** use them for cascade — see responsibility (b).

## One-way dependency rule

```
services/agent-runtime  ──depends-on──▶  foundation/atlas-hermes
                                         (receives resolved creds + callbacks)
           ▲
           │  (never reversed)
           │
foundation/atlas-hermes  ──can-only-reach-ATLAS──▶  via registered-plugin shim
                                                      (D-LOG-002, atlas_audit)
```

- `services/agent-runtime` imports `AIAgent` and `atlas_audit` (same env, direct
  package import — not via the plugin path).
- `foundation/atlas-hermes` **never** imports from `services/`. The only
  foundation→ATLAS path is the bundled `plugins/atlas_audit/__init__.py` shim,
  which is a one-line delegation into the `atlas_audit` package installed in the
  shared env (D-LOG-002). This keeps the foundation re-syncable against upstream
  NousResearch Hermes.

## Five adapter responsibilities

The adapter owns exactly these five concerns and no others:

### (a) Credential resolution and AIAgent construction

Resolve `(provider, base_url, api_key, model, api_mode)` from the auth store
(via `auth_store_path()` — see AUTH_STORE_DESIGN.md) and the active route policy.
Construct `AIAgent` with the resolved values. The foundation receives only already-
resolved credentials — it never reads `~/.atlas/auth.json` directly.

### (b) Fallback cascade

Own the fallback cascade — **adapter-driven, not Hermes-`fallback_model`-driven**.
The adapter drives the cascade by selecting a candidate provider list, calling
`AIAgent` once per provider, and classifying each error response as HALT, CASCADE,
or model-scoped. The full contract is in **[FALLBACK_CASCADE.md](FALLBACK_CASCADE.md)**.

The deliberate decision to keep cascade adapter-driven (rather than handing a
`fallback_model` dict to Hermes) ensures that health-aware provider ordering,
OpenAI-first lane selection, error body inspection for `400` disambiguation,
`provider_fallback` audit emission, and bounded attempt budget all live in ATLAS
code — not in undocumented Hermes cascade semantics.

Cross-reference: `FALLBACK_CASCADE.md` is the canonical error→action table. The
adapter is the **owner** of that cascade; any change to cascade behavior is a
change to the adapter, not the foundation.

### (c) ATLAS audit emission

Emit ATLAS audit events on the event bus:

- `model_call_start` — on every `AIAgent` invocation: `{provider, model, run_id, …}`
- `model_call_end` — on completion or error: `{provider, model, run_id, token_usage, …}`
- `provider_fallback` — on each CASCADE-class advance: `{from, to, reason}`

Emit via the **`atlas_audit` package under `services/agent-runtime/`** directly
(same environment — not via the plugin shim path, which exists for the foundation's
own boot-time registration). The plugin shim at `foundation/atlas-hermes/plugins/
atlas_audit/__init__.py` is a one-line `from atlas_audit import register` that
delegates into the same package; the adapter imports the package directly.

### (d) Preserve Hermes tool-approval gates

**Preserve** Hermes tool-approval gates (AGNT-05) — do **not** bypass them. Wire
the ATLAS UI/TUI hooks to the `clarify_callback` and approval callbacks that Hermes
exposes, rather than disabling or monkey-patching the gate mechanism. The agent loop
and iteration budget belong to the foundation; the adapter must not replicate them.

### (e) Transcript redaction before persistence

Before persisting any conversation transcript or response fragment, run it through
the redaction filter. Reuse `SECRET_PATTERNS` from
`packages/atlas-core/atlas_core/schemas/core.py` (the single source of truth for
SEC-01 — the same set used by the auth store). Do **not** invent a new regex set.
This satisfies AGNT-06: no secret material reaches the ATLAS audit JSONL, SQLite,
or the cockpit transcript view.

## Adapter vs foundation responsibility table

| Concern | Adapter (`services/agent-runtime`) | Foundation (`foundation/atlas-hermes`) |
|---------|-------------------------------------|----------------------------------------|
| Credential resolution from `~/.atlas/auth.json` | **adapter** | ✗ (receives resolved creds) |
| Provider/model route policy | **adapter** | ✗ |
| Fallback cascade + error classification | **adapter** | ✗ (native `fallback_model` not used) |
| ATLAS audit emission (`model_call_*`, `provider_fallback`) | **adapter** (calls `atlas_audit` directly) | only via bundled plugin shim (D-LOG-002) |
| Transcript redaction | **adapter** | ✗ |
| ATLAS branding (no Hermes/Codex leak in output) | **adapter** | ✗ |
| Agent loop / tool execution | ✗ | **foundation** (`AIAgent.run_conversation()`) |
| Tool-approval gates / iteration budget | ✗ (preserve via callbacks) | **foundation** |

## AGNT-01 hard gate — "wrap, never rewrite"

No parallel second chat runtime. If the Hermes foundation can be wrapped, it must
be wrapped. Any gap in the `AIAgent` surface that cannot be covered by the adapter
contract above is resolved by **adding an extension point to the foundation** (a
callback, a hook, or a registered plugin), recorded in `DIVERGENCE_LOG.md` as a
`D-LOG-NNN` entry — never by reimplementing the agent loop.

The `AIAgent` constructor already exposes `fallback_model`, `credential_pool`, all
streaming callbacks, and approval gates precisely because upstream Hermes
anticipated the adapter pattern. Use these surfaces before considering any
foundation change.

## LANDMINE 3 — DIVERGENCE_LOG naming reconciliation

The CONTEXT document and some earlier planning notes reference the `atlas_audit`
plugin shim as **`DIV-F-002`**. This reference is **incorrect and superseded** by
the actual log. The live `foundation/atlas-hermes/DIVERGENCE_LOG.md` uses the
canonical id scheme **`D-LOG-NNN`** — and as of Phase 10.0, the `atlas_audit`
plugin shim was **not yet recorded** in the log (only `D-LOG-001` was present,
covering the Phase 9.5 skill quarantine).

The `DIV-F-*` label scheme does not appear in the log itself and is therefore not
the actual canonical id scheme. The correct canonical id scheme is **`D-LOG-NNN`**.

This document records the reconciliation: the `atlas_audit` bundled plugin shim is
now back-filled as **`D-LOG-002`** (see `foundation/atlas-hermes/DIVERGENCE_LOG.md`).
Any future foundation extension point introduced by v1.1 must use `D-LOG-NNN`
numbering and must never reference the `DIV-F-*` label.

10.2 must treat `D-LOG-NNN` as the only valid divergence id scheme.

## Hand-off contract to Phase 10.2

10.2 implements this design and must, at minimum:

- Locate the adapter in `services/agent-runtime/atlas_runtime/chat/adapter.py`
  (or `agent_adapter.py`).
- Use `AIAgent` by **composition** only — no subclassing.
- Implement the cascade as **adapter-driven** per `FALLBACK_CASCADE.md` — do not
  delegate to Hermes' `fallback_model` kwarg.
- Emit `model_call_start`, `model_call_end`, `provider_fallback` on every call via
  `atlas_audit` (direct import, same env).
- Wire the `clarify_callback` and approval callbacks; do not disable them.
- Run transcript through `SECRET_PATTERNS` redaction before any persistence.
- Add `D-LOG-NNN` entries for any new foundation extension points.
- Resolve open question: per-call token usage availability from
  `AIAgent.run_conversation()` response path (needed for `model_call_end`).
