# Hermes-as-Foundation Principle

Date: 2026-06-08
Status: Active architecture principle

## Correction

ATLAS is not merely built **on top of** Hermes, and it should not **route through** Hermes as an external black-box harness.

ATLAS should be built **from Hermes, in Hermes, and by evolving Hermes** into an L2-owned foundation.

The intended direction is:

```text
Hermes Agent foundation -> L2/ATLAS enhanced foundation -> ATLAS product/runtime/cockpit
```

Not:

```text
ATLAS app -> routes requests through stock Hermes
```

And not:

```text
ATLAS builds a new harness from zero
```

## Executive statement

Hermes Agent is the production-ready foundation layer. It already solved much of the difficult harness work:

- fast and reliable CLI agent interface;
- streaming interaction loop;
- model/provider selection;
- provider credentials and auth patterns;
- custom OpenAI-compatible providers;
- tool calling and toolsets;
- skills and self-improvement;
- persistent memory;
- session store/search;
- delegation/subagents;
- cron/background jobs;
- MCP/plugins;
- profiles;
- gateway/platform adapters;
- Discord, Telegram, email, and other channels;
- web/API surfaces;
- emerging desktop/native direction.

Therefore, ATLAS should not recreate a harness. ATLAS should transform Hermes into an L2 version in our own terms: decoupled from Hermes branding where needed, enhanced with ATLAS governance and product features, and evolved into a stronger harness.

## Principle

```text
Do not route through stock Hermes. Do not rebuild from zero.
Use Hermes as the foundation codebase and evolve it into the L2/ATLAS harness.
```

This means ATLAS is not a thin wrapper around Hermes. It is an enhanced foundation strategy:

- start from Hermes' proven runtime;
- keep the parts that are already best-in-class;
- rebrand and productize in L2 terms where permitted;
- add ATLAS mission/run/audit/policy/wiki/cockpit layers inside the evolved foundation;
- upstream generic improvements when useful;
- keep L2-specific capabilities as ATLAS modules;
- avoid losing compatibility without a written reason.

## What “in Hermes” means

“In Hermes” means Hermes is the living foundation layer, not an external dependency hidden behind a route.

ATLAS should use Hermes' internal extension points, source structure, config, tools, skills, gateway, session, and provider infrastructure as the starting point. Where Hermes already has the correct architecture, we preserve it. Where ATLAS needs more, we enhance it.

Examples:

- The CLI should be an evolved L2/ATLAS CLI derived from Hermes' proven CLI, not a new shell invented from scratch.
- Channels should use/evolve Hermes gateway infrastructure, not a separate Discord/Telegram/email harness.
- Model/provider selection should use/evolve Hermes provider infrastructure, then add ATLAS policy and FreeLLMAPI router intelligence.
- Skills should remain compatible with Hermes-style skills where practical, with ATLAS classification and governance added.
- Cron/delegation/session/memory should be enhanced, not duplicated.
- The cockpit should control the evolved Hermes/ATLAS runtime, not call stock Hermes as a black-box service.

## What ATLAS adds to the foundation

ATLAS takes Hermes to another level by adding what Hermes does not fully provide as an L2 operating product:

1. **Mission and run lifecycle**
   - explicit objectives;
   - run states;
   - resumability;
   - cancellation;
   - operator-visible execution state.

2. **Audit-first runtime**
   - durable AuditEvents;
   - ToolCall records;
   - model-call metadata;
   - approval history;
   - artifact capture;
   - JSONL export.

3. **Policy and permissions**
   - easy-to-configure permissions;
   - workspace boundaries;
   - channel/user capability profiles;
   - provider/model routing constraints;
   - sandboxing and approval scopes.

4. **Knowledge and deep research**
   - LLM Wiki runtime;
   - source registry;
   - compiled knowledge pages;
   - deep research workflows;
   - contradiction/staleness linting;
   - evidence-grade artifacts.

5. **Self-improving L2 operations**
   - Hermes-style skill learning;
   - L2-curated skill packs;
   - workflow extraction;
   - reusable operational procedures;
   - memory boundaries.

6. **Native and web cockpit**
   - built-in chat;
   - mission command center;
   - run timeline;
   - approval UI;
   - provider/model settings;
   - audit and artifact viewer;
   - Terax-inspired lightweight Rust/native efficiency.

7. **Model/router intelligence**
   - FreeLLMAPI sidecar lessons;
   - auto-updatable model catalog;
   - provider health and discovery;
   - routing by task class;
   - privacy/cost/trust labels;
   - safe use of free/keyless/experimental models only under policy.

## Relationship to other pillars

Hermes remains the foundation. Other projects contribute targeted improvements:

- **Hermes:** foundation harness, self-improvement, stability, channels, CLI, tools, model routing, memory, skills, cron, gateway.
- **Odysseus:** new workspace features, deep research inspiration, privacy/security concepts, admin/non-admin capability lessons, built-in chat/workspace patterns.
- **FreeLLMAPI:** model-router sidecar, free-tier/provider discovery, privacy lessons where applicable, OpenAI-compatible routing.
- **Terax:** lightweight Rust/native desktop efficiency, fast terminal/operator surface, PTY/session handling, local-first UX.

Combined direction:

```text
L2/ATLAS harness = evolved Hermes foundation
                 + Odysseus workspace/deep-research/privacy concepts
                 + FreeLLMAPI router/provider discovery
                 + Terax lightweight Rust/native efficiency
                 + ATLAS mission/audit/policy/wiki/cockpit governance
```

## Branding and ownership

The final product should be an L2/ATLAS version, not a stock Hermes instance with an ATLAS label.

This includes:

- decoupling from Hermes branding where appropriate and permitted;
- preserving license obligations;
- documenting provenance;
- separating upstreamable improvements from L2 product-specific changes;
- keeping the final UX, naming, policies, cockpit, modules, and operating model in L2 terms.

## Fork/enhance posture

The posture is not “wrapper first.” The posture is **foundation evolution**.

Use this classification for changes:

1. **Preserve from Hermes** — already correct and production-grade.
2. **Enhance in foundation** — core improvement to the L2/ATLAS harness.
3. **Upstream candidate** — generic improvement that Nous/Hermes could benefit from.
4. **L2 product module** — ATLAS-specific behavior, brand, workflow, cockpit, policy, or business logic.
5. **Experimental donor feature** — concept from Odysseus/Terax/FreeLLMAPI that must be validated before entering foundation.
6. **Reject** — concept that adds bloat, risk, or divergence without enough value.

## Boundary rule

Before building anything, ask:

```text
Can this be implemented by evolving the Hermes foundation instead of creating a separate harness?
```

Default answer should be yes unless there is a documented reason.

## Non-negotiables

- Do not describe ATLAS as a thin app “on top of Hermes.”
- Do not describe ATLAS as routing through stock Hermes.
- Do not build a parallel generic harness.
- Do not duplicate Hermes' CLI, gateway, provider, skills, cron, memory, or delegation systems without a written reason.
- Do not blindly fork without provenance, license, divergence notes, and upstream/product classification.
- Do not let donor projects turn ATLAS into a loose bundle of cloned apps.
- Preserve Hermes' reliability and self-improving strengths while making the L2/ATLAS version more capable.

## Decision impact

Phase 4.5 must correct any language that frames ATLAS as merely wrapping or routing through Hermes.

Future Phase 6, 7, and 8 planning must treat Hermes as the foundation being transformed into the L2/ATLAS harness. The API and cockpit should expose the evolved Hermes/ATLAS runtime, not a separate backend that calls Hermes as an external service.
