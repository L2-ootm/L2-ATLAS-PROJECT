# Skill: module-builder

Build a new ATLAS module the operator can toggle, without touching ATLAS
source. Contract: `docs/plans/2026-07-16-module-framework-design.md`.

## What a module can do (v1)

- **Slash commands** — appear automatically in the WebUI palette/slash and the
  terminal. A command is a name + description + prompt template (`$ARGUMENTS`
  is replaced by the operator's arguments).
- **Pages** — schema-driven WebUI pages rendered by ATLAS-owned components.
  Block kinds: `heading`, `markdown`, `metrics` (label/value items), `actions`
  (buttons that dispatch a slash command into Chat). No module code executes;
  never promise interactive behavior the block schema cannot express.

## Procedure

1. Scaffold: `atlas module create <id> --name "<Display Name>"` — creates
   `<ATLAS home>/modules/<id>/module.yaml`, syncs, and activates it.
2. Edit `module.yaml`: tighten the description, write real command templates
   (one narrow job per command), design the page blocks.
3. Re-sync: `atlas module sync` (activation state is preserved). Fix any
   `problem:` lines it reports — they mean the manifest was rejected.
4. Verify end-to-end, do not assume:
   - `atlas module list` shows the module active;
   - the gateway serves it: `GET /v1/commands` contains your command;
   - the WebUI sidebar shows the module under MODULES and `/m/<id>` renders.
5. Command names must be unique: built-ins (init, review, dream, distill,
   goal, mission, deep-research) and earlier modules win collisions — your
   command silently disappears if it collides, so check `/v1/commands`.

## Constraints

- Module ids and command names: `[a-z0-9-]`, lowercase.
- Keep templates self-contained: they run through the normal chat pipeline
  with no extra context beyond what the template says.
- Do not edit ATLAS source, the registry DB, or other modules' directories to
  make a module work. If the block schema is insufficient, say so and record
  the gap instead of hacking around the constraint.
