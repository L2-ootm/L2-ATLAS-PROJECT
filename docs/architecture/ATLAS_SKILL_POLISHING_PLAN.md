# ATLAS Skill Polishing Plan

## Decision

Not every existing Hermes/OpenClaw/L2 skill should ship as-is. ATLAS needs a polished skill/workflow layer with product-grade metadata, scopes, tests, safety classification, and UI discoverability.

## Skill sources

- Hermes installed skills: `C:/Users/Davi/AppData/Local/hermes/skills`
- OpenClaw/GSD imported skills
- `l2-agent-skills`
- L2 MIND
- L2-BOT harness runbooks
- Command Center workflows
- Program/application operations
- L2 nightly brief / reports / outreach workflows

## Classification

| Class | Meaning | Ships by default? |
|---|---|---|
| core | essential ATLAS behavior | yes |
| operator | useful for technical operators | yes, optional pack |
| l2-internal | specific to Davi/L2 operations | no public default |
| personal/private | depends on Davi personal data | never public |
| experimental | useful but unstable | hidden/dev only |
| deprecated | stale or superseded | no |

## Required metadata

Each ATLAS skill/workflow should eventually have:

```yaml
name: skill-name
version: 0.1.0
class: core | operator | l2-internal | personal-private | experimental | deprecated
autonomy_level: L0 | L1 | L2 | L3 | L4 | L5
risk: low | medium | high
requires_tools: []
requires_secrets: []
input_schema: {}
output_schema: {}
verification: []
owner: atlas | l2 | user
public_safe: true | false
```

## Polishing requirements

Before a skill becomes ATLAS-grade:

1. Clear trigger conditions.
2. Exact operating steps.
3. Tool requirements.
4. Safety boundaries.
5. Verification steps.
6. Example mission invocation.
7. Expected artifacts.
8. Failure modes.
9. UI display metadata.
10. Test or dry-run path where possible.

## Skill packs

Initial packs:

### Core ATLAS Pack

- mission planning;
- file/source ingest;
- LLM Wiki maintenance;
- run audit;
- decision logging;
- source lint;
- recovery/snapshot;
- context optimization.

### Developer Operator Pack

- codebase inspection;
- plan writing;
- TDD;
- code review;
- GitHub PR workflow;
- repo hygiene;
- subagent development.

### L2 Systems Pack

- L2 MIND;
- L2-BOT harness;
- L2 outreach;
- L2 nightly brief;
- Nodex evidence workflow;
- application/evidence workflows.

### Business Ops Pack

- CRM update;
- email summary;
- meeting brief;
- proposal drafting;
- relationship follow-up;
- pulse brief.

## First audit task

Generate an inventory of all skills with:

- name;
- path;
- description;
- class guess;
- public-safe guess;
- polish required;
- ATLAS relevance.

Output:

`docs/imports/SKILL_INVENTORY.md`
