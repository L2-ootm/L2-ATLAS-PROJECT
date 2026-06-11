# Hermes Infrastructure and AI Router Bridge

Date: 2026-06-08

## Purpose

This note extends the Phase 4.5 native cockpit consolidation with a second required verification: ATLAS must validate how Hermes Agent's infrastructure is consolidated inside ATLAS in ATLAS terms, and how FreeLLMAPI-style routing can become an auto-updatable model/provider connector.

Important foundation principle: ATLAS is not building a generic agent harness from zero, and it is not merely routing through stock Hermes. Hermes Agent is the foundation codebase and production-ready harness layer. ATLAS should evolve it into the L2/ATLAS harness: decouple branding where appropriate, preserve the production-grade CLI/gateway/provider/skill/runtime capabilities, and enhance the foundation with ATLAS mission/audit/policy/wiki/cockpit features.

Reference:

`docs/architecture/HERMES_FIRST_FOUNDATION_PRINCIPLE.md`

## Core question

Can ATLAS use Hermes' proven infrastructure patterns while keeping ATLAS as the product/runtime owner?

Areas to verify:

1. Hermes provider/model infrastructure
   - provider registry;
   - OAuth/API-key auth handling;
   - credential pools;
   - custom OpenAI-compatible endpoints;
   - model selection/configuration;
   - delegation model overrides;
   - profile isolation;
   - gateway runtime behavior.

2. Hermes skills/tools/runtime infrastructure
   - toolset registry;
   - skills lifecycle;
   - plugins/MCP;
   - cron;
   - delegation;
   - session store/search;
   - memory;
   - gateway adapters.

3. ATLAS adaptation boundary
   - what should be used directly;
   - what should be wrapped;
   - what should be rewritten in ATLAS core;
   - what should remain external.

## FreeLLMAPI router opportunity

FreeLLMAPI should be evaluated as an OpenAI-compatible sidecar router, not as a core ATLAS dependency.

The target architecture is an **auto-updatable AI router connector**:

```text
ATLAS model policy -> Hermes/custom provider adapter -> FreeLLMAPI sidecar -> provider/model catalog -> routed request
```

The connector should support:

- OpenAI-compatible `/v1/models` discovery;
- OpenAI-compatible `/v1/chat/completions` routing;
- provider health checks;
- provider capability tags;
- local cache of model catalog;
- refresh on startup;
- periodic refresh;
- manual refresh command;
- provenance for each discovered model;
- support for auth-backed provider catalogs such as Codex/OpenCode/Kilo where available;
- strict policy labels such as `free-tier-ok`, `paid-ok`, `local-only`, `trusted-provider`, `experimental`, `no-sensitive-data`.

## Codex/OpenCode/OAuth model discovery angle

Hermes already supports OAuth/provider auth patterns such as OpenAI Codex OAuth and Qwen OAuth, plus API-key providers and custom endpoints.

ATLAS should investigate whether a connector can:

1. detect available authenticated provider accounts through Hermes-style auth state;
2. query their model catalogs where APIs allow it;
3. merge those catalogs with FreeLLMAPI's discovered models;
4. expose a normalized ATLAS model registry;
5. route by task class and policy rather than hardcoded model names.

Example behavior:

```text
User authenticates Codex/OpenCode/Kilo/etc.
Connector refreshes catalog.
New free or high-quality models appear.
ATLAS tags them by provider, cost, context length, modality, reliability, policy class.
Mission planner can choose them for low-risk/free-tier tasks automatically.
Sensitive/high-stakes tasks stay on trusted configured providers.
```

## Non-negotiable controls

- Never leak OAuth tokens or API keys into ATLAS audit payloads.
- Never route sensitive data to keyless/free/experimental models unless policy explicitly allows it.
- Keep provider credentials in Hermes-compatible auth/keychain mechanisms or ATLAS secure credential storage.
- Record routed provider/model metadata in AuditEvents.
- Treat model discovery output as untrusted until validated.
- Keep a local allow/deny policy for providers and models.
- FreeLLMAPI remains sidecar first. Fork/vendor only after repeated validation.

## Required Phase 4.5 output

Claude should produce or update:

- `docs/architecture/HERMES_INFRASTRUCTURE_CONSOLIDATION_AUDIT.md`
- `docs/architecture/AI_ROUTER_CONNECTOR_STRATEGY.md`
- `docs/decisions/D-017-ai-router-connector-strategy.md` if the strategy is accepted
- updates to `.planning/phases/08-cockpit/CONTEXT.md` for provider/model settings UX
- updates to future Phase 6/7/8 dependencies if router/model registry affects API contracts

## Strategic verdict

This is worth adding to Phase 4.5. The native cockpit direction and the model/router direction are connected: the cockpit needs a provider/model settings surface, but the real value is deeper, an ATLAS-governed model registry and router that can discover new options automatically while respecting policy.
