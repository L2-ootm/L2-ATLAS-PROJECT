# Hermes Foundation Correction Addendum

Date: 2026-06-08

## Correction to current Phase 4.5 work

If any Phase 4.5 document says ATLAS is merely:

- built “on top of” Hermes;
- wrapping Hermes as an external service;
- routing through stock Hermes;
- adding a separate backend that calls Hermes;
- using Hermes only as a reference;

then that language is wrong and must be corrected.

## Correct framing

ATLAS should be built from Hermes, in Hermes, and by evolving Hermes into the L2/ATLAS harness.

```text
Hermes Agent foundation -> L2/ATLAS enhanced foundation -> ATLAS product/runtime/cockpit
```

Hermes is not a black-box backend. Hermes is the production-ready foundation layer.

## Why

Hermes already has the hard harness infrastructure working fast and reliably:

- CLI interface;
- streaming agent loop;
- model selection/routing;
- provider configuration;
- channels and gateways, including Discord and Telegram;
- tools and toolsets;
- skills and self-improvement;
- memory;
- sessions;
- delegation;
- cron;
- profiles;
- web/API surfaces;
- emerging desktop direction.

The L2/ATLAS harness should be **more than Hermes**, but by enhancing the Hermes foundation, not by routing through it externally or rebuilding it.

## What “more than Hermes” means

The L2/ATLAS harness combines:

- Hermes self-improving stability and harness infrastructure;
- Odysseus-inspired features, deep research, workspace patterns, and privacy/security concepts;
- FreeLLMAPI-inspired model router/provider discovery and privacy-aware routing where applicable;
- Terax-inspired lightweight Rust/native efficiency, terminal strength, and desktop/operator surface;
- ATLAS-specific mission/run/audit/policy/wiki/cockpit governance.

## Required documentation update for Claude

Claude should update Phase 4.5 outputs to use this vocabulary:

- “evolved Hermes foundation”
- “L2/ATLAS harness”
- “foundation transformation”
- “enhance/rebrand/decouple where appropriate”
- “preserve Hermes production-grade capabilities”
- “run in the evolved Hermes/ATLAS foundation”

Claude should avoid this vocabulary unless explicitly explaining a rejected approach:

- “route through Hermes”
- “thin wrapper”
- “on top of Hermes”
- “external Hermes backend”
- “separate harness”

## Required decision alignment

This addendum aligns with:

- `docs/architecture/HERMES_FIRST_FOUNDATION_PRINCIPLE.md`
- `docs/decisions/D-018-hermes-first-foundation-strategy.md`
