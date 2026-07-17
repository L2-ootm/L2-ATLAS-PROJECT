# ATLAS bundled modules

Each subdirectory containing a `module.yaml` is a manifest module. Modules
here ship with the checkout; operator/agent-installed modules live in
`<ATLAS home>/modules/`. Design contract:
`docs/plans/2026-07-16-module-framework-design.md`.

- `atlas module sync` — discover and register (activation state preserved).
- `atlas module list` / `activate <id>` / `deactivate <id>` — registry control.
- `atlas module create <id>` — scaffold a new module in the user directory.

v1 capabilities are declarative only: slash `commands` (propagate to the
WebUI palette/slash and the terminal automatically) and schema-driven WebUI
`pages` (rendered by ATLAS-owned components — the visual constraint). No
module code executes.
