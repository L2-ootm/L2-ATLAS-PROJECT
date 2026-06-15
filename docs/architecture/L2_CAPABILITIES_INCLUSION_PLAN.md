# L2 Capabilities Inclusion Plan

## Objective

L2 ATLAS must consolidate the useful operating assets Davi already created:

- Hermes foundation;
- L2 skills;
- GSD/imported workflow patterns;
- L2 MIND;
- L2-BOT harness;
- L2-Atlas Mission OS;
- L2-atlas-hermes recovery/snapshot discipline;
- L2-NODEX as dogfood/evidence project;
- L2 Knowledge Router ideas;
- Personal Command Center patterns.

## Capability buckets

### 1. Skills and workflows

Sources:

- Hermes skills under `<USER_HOME>/AppData/Local/hermes/skills`.
- `l2-agent-skills` repo.
- GSD/imported skills.
- L2 MIND.
- Program/application operations skills.
- L2 nightly brief / candidate reports / outreach workflows.

Target:

```txt
atlas/skills/
atlas/workflows/
atlas/runbooks/
atlas/profiles/
```

Rule:

Do not dump all skills blindly. Classify:

- core default;
- L2 internal;
- optional pack;
- personal/private;
- deprecated.

### 2. L2-BOT harness

Source:

`<USER_HOME>/Desktop/Projects/L2-BOT`

Target role:

- Discord/server operations adapter;
- channel harness reference;
- event/message routing patterns;
- moderation/admin tooling only where appropriate.

Rule:

L2-BOT remains a harness/source asset first. ATLAS should absorb patterns and build a clean channel runtime.

### 3. Subagents and model tiers

ATLAS should expose subagent orchestration as a first-class product feature.

Agent classes:

| Agent | Model tier | Role |
|---|---|---|
| Orchestrator | strongest | decomposes missions, assigns workers, verifies |
| Coder | strong/code model | implementation |
| Researcher | strong/web model | source synthesis/deep research |
| Clerk | cheap model | file organization, extraction, manifests |
| Reviewer | strong model | security/quality/spec review |
| Local/private | local model where viable | sensitive/offline tasks |

Required runtime data:

- assigned mission;
- model/provider;
- tools allowed;
- autonomy level;
- cost/token budget;
- artifacts produced;
- verification result.

### 4. Native interaction layer

Future track:

- real-time STT;
- TTS;
- wake word;
- command palette;
- UI overlays;
- active-context capture;
- Linux/Hyprland integrations;
- Windows native support;
- seamless “operator sidecar” experience.

This is a differentiator, but not the first MVP blocker.

### 5. Knowledge and memory

ATLAS must combine:

- Hermes memory;
- session search;
- LLM Wiki;
- source registry;
- entity graph;
- RAG/vector search;
- personal/company state files;
- contradiction/staleness lint.

### 6. Token/context optimization

ATLAS should know how to handle context by structure:

- codebase inspection;
- docs/wiki;
- raw chat logs;
- CRM interactions;
- email threads;
- repos/git diffs;
- long PDFs;
- previous sessions;
- task state.

It should choose:

- raw load;
- summarized load;
- wiki page;
- embedding search;
- session search;
- artifact citation;
- no load.

## First integration priority

1. Hermes foundation clone.
2. Skill/workflow inventory.
3. L2-Atlas mission/policy/log extraction.
4. L2-BOT harness audit.
5. LLM Wiki runtime.
6. Subagent orchestration model.
