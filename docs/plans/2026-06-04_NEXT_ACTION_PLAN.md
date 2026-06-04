# L2 ATLAS Next Action Plan

Date: 2026-06-04

## Objective

Convert research into build-ready structure without losing control of scope.

## Immediate sequence

### Step 1 — Foundation setup

Create/pin Hermes foundation in a controlled location.

Options to decide:

```txt
L2-ATLAS-PROJECT/foundation/hermes-agent
```

or external clean clone:

```txt
C:/Users/Davi/Desktop/Projects/_EXTERNAL_REPOS/hermes-agent
```

Recommended for now:

- clone externally first;
- record commit SHA;
- inspect architecture;
- only then decide submodule/vendor/fork layout.

### Step 2 — Hermes architecture audit

Use report:

`docs/research/raw-reports/2026-06-04_01_hermes-foundation-architecture.md`

Produce:

`docs/research/HERMES_FOUNDATION_AUDIT.md`

Must verify:

- hook system;
- tool registry;
- session store;
- delegation;
- cron;
- profiles;
- plugin surfaces;
- TUI/UI boundary;
- event capture feasibility.

### Step 3 — L2-Atlas module extraction audit

Source:

`C:/Users/Davi/Desktop/Projects/L2-Atlas/src/atlas_core`

Produce:

`docs/imports/L2_ATLAS_MODULE_EXTRACTION_PLAN.md`

Map:

- mission parser;
- task model;
- orchestrator;
- policy engine;
- executor;
- JSONL logger;
- heartbeat;
- CLI/shell;
- skills registry;
- tests.

Classify each module:

| Classification | Meaning |
|---|---|
| port | can be moved/adapted |
| rewrite | concept useful, code not worth importing |
| reference | learn only |
| discard | not useful |

### Step 4 — Core schemas

Create initial schemas for:

- Mission;
- Run;
- ToolCall;
- Artifact;
- AuditEvent;
- AgentProfile;
- Skill;
- Workflow;
- Source;
- WikiPage;
- Contact/Organization/Opportunity later.

Target:

`packages/atlas-core/src/schemas/`

### Step 5 — SQLite schema draft

Create:

`infra/migrations/0001_core.sql`

Tables:

- missions;
- runs;
- run_events;
- tool_calls;
- artifacts;
- sources;
- wiki_pages;
- audit_events;
- agent_profiles;
- skills;
- workflows.

### Step 6 — WebUI stack spike

Create:

`docs/research/WEBUI_STACK_SPIKE.md`

Compare:

- SvelteKit/Svelte 5;
- Next.js/React;
- TanStack Router/Vite option if useful.

Criteria:

- speed;
- memory;
- UI polish;
- realtime dashboard suitability;
- L2 existing code reuse;
- long-term maintainability.

### Step 7 — Missing CRM/Pulse/Channels research

Run dedicated research using prompt 05 or regenerate it if needed.

Output:

`docs/research/CRM_PULSE_CHANNELS_DEEP_DIVE.md`

## What not to build yet

- full CRM;
- WhatsApp production integration;
- native overlay;
- billing;
- multi-tenant SaaS;
- MCP marketplace UI;
- self-modifying agent behavior.

## First build target

A local developer MVP:

```txt
create mission
→ run through enhanced Hermes/ATLAS runtime
→ capture event/audit log
→ produce artifact
→ file result into wiki
→ display in simple cockpit view
```

## Verification gates

Before first code import:

- research synthesis exists;
- decisions registered;
- Hermes commit pinned;
- L2-Atlas extraction plan exists;
- no secrets copied;
- no raw personal data copied;
- git status reviewed.
