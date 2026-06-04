# AGENTS.md — L2 ATLAS PROJECT

## Mission

Build L2 ATLAS as an AI operator/company cockpit using Hermes as the main runtime foundation and L2/OpenClaw assets as reusable modules.

## Non-negotiables

- Do not copy secrets or raw personal data into this repo.
- Do not destructively reorganize existing repos.
- Do not keep Hermes as a black-box dependency; ATLAS should be built from/enhance the Hermes foundation with documented changes.
- Keep actions auditable: reason, input, tool/action, output, verification.
- Use flexible priority blocks, not rigid schedules.

## Architecture rule

Separate:

1. raw sources;
2. compiled wiki/memory;
3. runtime execution;
4. cockpit UI.

## Planning rule

Update `.planning/STATE.md` after every meaningful step.
