# System Overview — L2 ATLAS

## Core loop

```txt
Source / Goal / Event
        ↓
ATLAS Mission Intake
        ↓
Planner + Policy Engine
        ↓
Enhanced Hermes Runtime
        ↓
Tool / Channel / File / Web / MCP Action
        ↓
Audit + Artifact Capture
        ↓
Wiki / Memory / Dashboard Update
        ↓
Pulse / Next Action
```

## Runtime boundaries

### ATLAS owns

- product data model;
- mission schema;
- cockpit UI;
- audit trail;
- autonomy policy;
- wiki maintenance rules;
- integration abstractions;
- CRM/relationship model;
- pulse monitors;
- product packaging.

### Hermes owns initially

- LLM provider calls;
- tools;
- skills;
- gateway/platform adapters;
- cron;
- MCP;
- memory/session primitives;
- delegation/subagents.

### Old L2-Atlas contributes

- Mission Control model;
- markdown task parsing;
- safe execution policy concepts;
- JSONL audit/logging;
- pulse/heartbeat idea;
- shell/CLI harness;
- future voice/STT/TTS/overlay vision.

## First MVP architecture

```txt
apps/web
  Cockpit UI

apps/api
  Mission/run/source/wiki API

services/agent-runtime
  ATLAS/Hermes runtime + audit capture

services/wiki-runtime
  LLM Wiki ingest/query/lint

packages/atlas-core
  shared schemas and policies

wiki/
  persistent markdown knowledge layer
```

## First technical decision

ATLAS starts from the Hermes codebase/foundation and enhances it into the ATLAS runtime.

Because ATLAS is intended to run on an enhanced Hermes foundation, direct framework changes are allowed when they serve the ATLAS product. Still document each major divergence:

1. why upstream Hermes behavior is insufficient;
2. what ATLAS adds;
3. whether the change should be upstreamable, plugin-based, or ATLAS-only;
4. migration/compatibility impact;
5. decision recorded in `docs/decisions/`.
