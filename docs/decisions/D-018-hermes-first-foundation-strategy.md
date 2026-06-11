# D-018 — Hermes-as-foundation L2/ATLAS harness strategy

Date: 2026-06-08
Status: Accepted, corrected

## Decision

ATLAS will not build a generic agent harness from zero, and it will not merely route through stock Hermes as an external black-box service.

Hermes Agent is the foundation codebase and production-ready harness layer that ATLAS will evolve into an L2/ATLAS version in our own terms.

The intended direction is:

```text
Hermes Agent foundation -> L2/ATLAS enhanced foundation -> ATLAS product/runtime/cockpit
```

Not:

```text
ATLAS app -> routes through stock Hermes
```

## Rationale

Hermes has already uncovered and implemented much of the best harness architecture for this category:

- fast CLI interface;
- reliable streaming agent loop;
- model/provider selection;
- provider credentials and auth;
- custom provider endpoints;
- tool calling and toolsets;
- skills and self-improvement;
- memory;
- sessions and search;
- delegation/subagents;
- cron/background jobs;
- gateway/platform adapters;
- Discord, Telegram, email, and other channels;
- web/API surfaces;
- profile isolation;
- emerging desktop/native direction.

Rebuilding these from zero would be wasteful and less reliable. Treating Hermes as only an external route would also be wrong, because ATLAS needs deep integration, rebranding, governance, audit, policy, cockpit, and L2-specific modules.

The correct move is to enhance the Hermes foundation into a stronger L2/ATLAS harness.

## What ATLAS adds

ATLAS adds the next level:

- mission/run lifecycle;
- audit-first persistence;
- policy and capability governance;
- easy permission configuration;
- sandboxing strategy;
- source/wiki/memory runtime;
- deep research workflows;
- built-in chat and cockpit UX;
- model-router policy;
- FreeLLMAPI-style model discovery where safe;
- Odysseus-inspired workspace/deep-research/privacy features;
- Terax-inspired lightweight Rust/native efficiency;
- L2-specific workflows, channels, and business modules.

## Implementation principle

Before building any subsystem, ask:

```text
Can this be implemented by evolving the Hermes foundation instead of creating a separate harness?
```

Default answer: yes, unless a written technical reason says no.

## Change classification

Every non-trivial foundation change should be classified as one of:

1. Preserve from Hermes.
2. Enhance in L2/ATLAS foundation.
3. Upstream candidate for Hermes/Nous.
4. L2 product-specific module.
5. Experimental donor feature from Odysseus/Terax/FreeLLMAPI.
6. Reject.

## Relationship to external pillars

- Hermes: foundation harness and self-improving stable runtime.
- ATLAS: evolved L2 operating/product layer inside that foundation.
- Odysseus: feature, deep research, privacy, and workspace inspiration.
- FreeLLMAPI: model-router/provider-discovery sidecar reference.
- Terax: lightweight Rust/native desktop efficiency and operator-surface reference.

Combined direction:

```text
L2/ATLAS harness = evolved Hermes foundation
                 + Odysseus features/deep-research/privacy concepts
                 + FreeLLMAPI router/provider discovery
                 + Terax lightweight Rust/native efficiency
                 + ATLAS mission/audit/policy/wiki/cockpit governance
```

## Non-goals

- No new generic agent harness from zero.
- No thin app that only routes through stock Hermes.
- No duplicate CLI/gateway/provider/skills/cron/memory/delegation systems without a written reason.
- No blind fork without provenance, license, divergence, and upstream/product classification.
- No loss of Hermes' reliability and self-improving strengths.

## Required follow-up

Phase 4.5 must correct any architecture language that says ATLAS is merely “on top of Hermes,” “wrapping Hermes,” or “routing through Hermes.”

Future Phase 6/7/8 planning must treat Hermes as the foundation being transformed into the L2/ATLAS harness.

Reference:

`docs/architecture/HERMES_FIRST_FOUNDATION_PRINCIPLE.md`
