# ATLAS skill pack

Operating doctrine the agent loads when building on or extending ATLAS
itself. Distilled from the L2 loop-engineering, GSD, and ultra packs into
runtime-agnostic instructions any ATLAS runtime (native, Claude Code, Codex)
can follow by reading the file.

| Skill | Use when |
|---|---|
| `module-builder.md` | creating, validating, or wiring an ATLAS module |
| `loop-discipline.md` | any multi-step build/change on ATLAS or an operator project |
| `handoff.md` | ending a session that changed project state |
| `gsd/` | the full GSD/L2 execution loop — init, discuss, plan, execute, verify, debug, ship, progress (surfaced as `/gsd-*` by `modules/gsd`) |

These are plain markdown by design: the agent reads the relevant skill before
acting (referenced from the core policy). A future slice binds them to the
foundation's native skill loading.
