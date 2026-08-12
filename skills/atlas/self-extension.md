# Skill: self-extension

Read this when a missing capability is what stops you from finishing the work.
Roadmap and rationale: `docs/plans/2026-08-12-atlas-self-extension-roadmap.md`.

## Before building anything, answer these four

1. **Is it actually missing?** Search first, in this order:
   `atlas_module op=list` (active modules and their workflows/collections), the
   tool catalog, `atlas mcp list`, the skills inventory. Most "missing"
   capabilities exist under another name, and a duplicate is worse than the
   original friction.
2. **Will it be needed again?** Look for evidence, not intuition — prior run
   summaries, failure patterns, the brain graph, your own scratchpad. Once →
   disposable. Repeatedly → a candidate for something durable.
3. **Is it bounded?** If it needs new credentials, network write access, or
   more than a couple hundred lines, it is a feature request, not a
   self-extension. Say so, record it, and continue with what you have.
4. **What is the cheapest thing that unblocks you?** Usually a shell command, a
   query, or a workflow entry — not a new tool.

**The default answer is disposable.** Durability is a promotion that has to be
argued for, never a starting state.

## What you may build today (and how)

| Need | Build it as |
|---|---|
| A rule that must hold in future runs | A module `context` doctrine file |
| A repeatable procedure | A module `workflow` |
| Data that must survive the run | A module `collection` + records |
| An operator entry point | A module `command` |
| An external integration | An `mcp` declaration (operator enables it) |
| A one-off script | A scratchpad entry, `kind=tool`, TTL `next_startup` |

Use `atlas module create` for a new module; see `module-builder.md`.

## What you may not do

- Do not edit ATLAS source, migrations, the permission broker, the hardline
  policy, the audit bus, or the prompt layers to unblock yourself. Those are
  the boundary, not an obstacle.
- Do not import generated code into the runtime. A generated script is a saved
  command you run as a subprocess, nothing more.
- Do not request, store, or print a secret. Reference existing `${VAR}` names.
- Do not enable an MCP server yourself. Register it, then tell the operator
  what to enable and why.
- Do not claim a capability works because you created it. Registered,
  configured, reachable and verified-live are four different states — name the
  one you actually proved.

## Record what you built

Write a scratchpad `kind=finding` entry with: what was missing, what you built,
whether it is disposable or durable, and why. The third time the same
disposable gets rebuilt, that record is the evidence that it should be
promoted — and without it, nobody ever notices the pattern.
