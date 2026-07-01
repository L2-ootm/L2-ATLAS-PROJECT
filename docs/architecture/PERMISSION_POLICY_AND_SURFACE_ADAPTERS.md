# Permission Policy and Surface Adapters

ATLAS has one permission authority. Python evaluates trusted tool facts and owns the SQLite
broker; Rust exposes transport-only routes; CLI, Go, Web, API/headless, messaging, and future
desktop clients are adapters. An adapter may render a request and submit a decision. It may not
classify risk, widen policy, mint an approval, or execute a guarded tool.

## Authority flow

```text
agent/tool request
  → tool_service.invoke
  → immutable hardline floor
  → master policy ceiling
  → matching narrowing profile
  → matching scoped allow
  → execute now | broker-owned pending request | terminal deny
  → audit + normalized surface event + policy receipt
```

`tool_service.invoke` is the production chokepoint. `policy.decide` is deterministic and
side-effect free. `permission_broker` owns pending state, nonce validation, atomic claims,
expiry, allow scopes, recovery, and terminal outcomes. Surface code never bypasses this chain.

## Operator configuration

`PermissionConfig` is part of the revisioned, masked control-plane configuration.

- `manual`: read-class work is allowed; guarded work asks.
- `smart`: read-class work is allowed; the trusted advisor may allow or deny, otherwise it asks.
- `full_autonomy`: non-hardline work is allowed unless a rule or boundary denies it.
- Ordered master rules select tools, capabilities, risks, command patterns, normalized paths,
  surfaces, agents, workspaces/projects, and channels.
- Profiles select a surface/workspace/project/agent/channel and may only narrow the master
  ceiling. Config validation rejects widening before persistence.
- `workspace_only` confines target paths to the canonical active root.
- The protected maintenance scope requires all of: an enabled config flag, explicit trusted
  user maintenance intent, a declared ATLAS maintenance capability, and a target inside a
  declared maintenance root. It never bypasses hardline checks.

Precedence is fail-closed: hardline deny → master deny/boundary → master ceiling → narrowing
profile → scoped allow → effective preset. A later stage cannot overturn a deny.

## Hardline floor

The versioned code-owned floor blocks catastrophic filesystem roots, block-device and partition
mutation, shutdown/boot/firmware operations, fork bombs/resource exhaustion, unsafe privilege
escalation, credential-store mutation, and attempts to disable the guard itself. It is evaluated
under every preset, surface, profile, maintenance request, and allow scope. Configuration cannot
edit or disable it.

## Decision lifecycle

An actionable record contains approval id, owning surface-session id, nonce, expiry, normalized
redacted arguments, workspace, risk, requester provenance, and the server-authored policy
receipt.

1. The broker persists a pending request for one live owner.
2. Only that surface path can list it:
   `GET /v1/surface-sessions/{session_id}/approvals`.
3. Surface-specific reads and decisions carry the create/resume token in the
   `X-Atlas-Surface-Owner` header; missing or stale tokens fail with
   `surface_owner_mismatch`.
4. The owner submits the nonce to the nested `approve` or `reject` route.
5. Approval may apply once, for the owning session, or as a durable narrowly scoped rule.
6. The atomic claim has one winner. Foreign, stale, expired, replayed, concurrent-loser, or
   disconnected claims fail closed.
7. Silence, missing channels, and bounded-wait timeout deny.
8. Recovery reconciles interrupted execution and preserves an auditable terminal outcome.

`GET /v1/tools/approvals` is a read-only compatibility/audit projection. It accepts no decision
authority. It is scheduled for removal with the compatibility layer on 2026-09-30; consumers
should use audit events for history.

## Adapter obligations

Every usable adapter must:

- create or resume one surface session with stable workspace/run identity;
- retain its owner token outside logs and display payloads;
- heartbeat while active or blocked on a decision;
- replay normalized events from the last sequence and handle all registered kinds;
- list only its nested owned queue;
- submit approval id, nonce, and explicit scope once;
- treat unknown events, ownership conflict, expiry, disconnect, and timeout visibly and
  fail-closed;
- render the server receipt rather than recomputing policy; and
- cancel/close through the shared session lifecycle.

CLI JSON commands are the service boundary. Rust is dispatch-only. The Go TUI and React WebUI
use the same nested routes. Messaging integrations can embed the same request/choice/receipt
data in their native channel UI, and the future desktop shell can consume the same contract
without a new policy engine.

## Receipts, audit, and redaction

`PermissionExplainReceipt` records decision, reason code, source layer, matched rule,
effective preset/profile, normalized target facts, and maintenance-scope use. Receipts and
normalized events exclude API keys, owner tokens, passwords, raw secrets, raw arguments, and
chain-of-thought. Cross-surface audit may expose terminal provenance but never grants decision
authority.

## Provenance

The hardline-first guard ordering, bounded channel wait, four-choice approval semantics,
session-local isolation, and timeout-deny behavior were transformed from the behavior model in
the vendored Hermes foundation. ATLAS did not import Hermes approval state, globals, storage, or
product identity. ATLAS owns the schemas, evaluator, broker, database, routes, and UI.
