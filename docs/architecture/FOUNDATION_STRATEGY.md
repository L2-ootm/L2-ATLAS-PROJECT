# Foundation Strategy — Enhanced Hermes Runtime

> **Supersession note — 2026-06-11:** This document is historical/contextual.
> For the current architecture, use `docs/architecture/OVERVIEW.md` and accepted ADRs
> D-018, D-021, and D-022. Do not treat pre-D-022 diagrams or phase layout in this
> document as canonical if they conflict with those sources.

## Decision

L2 ATLAS should **not** be a separate product that merely routes through Hermes as a black-box subprocess.

L2 ATLAS should be built from the **Hermes framework foundation**, enhancing it into the ATLAS runtime.

## Meaning

Hermes provides the working foundation:

- cross-platform CLI;
- stable agent loop;
- tool system;
- skills;
- memory;
- gateway/channels;
- cron;
- MCP;
- profiles;
- delegation/subagents;
- provider routing;
- session store;
- TTS/STT hooks;
- web/file/terminal/browser tools.

ATLAS adds the product/runtime layer:

- beautiful operator cockpit;
- stronger mission model;
- richer subagent orchestration;
- L2 MIND decision engine;
- L2 workflow skills and GSD/OpenClaw patterns;
- L2-BOT harness integration;
- LLM Wiki knowledge runtime;
- pulse monitoring;
- CRM/relationship runtime;
- native overlay/voice/STT track;
- token/context optimization engine;
- self-improvement governance;
- AI company/operator dashboard.

## Implementation implication

When implementation starts, clone Hermes into the ATLAS project/foundation and work from there.

Recommended structure:

```txt
L2-ATLAS-PROJECT/
├── foundation/hermes-agent/      # cloned Hermes foundation
├── atlas/                        # ATLAS additions/overrides/runtime modules
├── apps/web/                     # cockpit
├── packages/atlas-core/          # schemas/policies shared with foundation
├── services/wiki-runtime/
├── services/pulse-runtime/
└── docs/
```

Alternative if clone-in-repo is too heavy:

```txt
_EXTERNAL_REPOS/hermes-agent      # clean upstream clone
L2-ATLAS-PROJECT/foundation       # patches, integration docs, submodule/worktree pointer
```

## Divergence policy

Every major change to Hermes foundation must be classified:

| Type | Meaning |
|---|---|
| upstreamable | should become PR to Hermes |
| plugin/tool | can live outside core |
| ATLAS-only | product-specific behavior |
| experimental | spike, not production |

Each divergence needs a decision record under:

`docs/decisions/`

## Subagent strategy

ATLAS must support subagents across capability tiers:

- cheap models for mechanical work;
- stronger models for architecture/review;
- local models for private/offline tasks where viable;
- specialist profiles for coding, research, ops, CRM, writing, security;
- orchestrator/worker topology with audit trails.

## Product stance

Hermes is the engine foundation. ATLAS is the upgraded operating system, cockpit, and company-grade product layer.
