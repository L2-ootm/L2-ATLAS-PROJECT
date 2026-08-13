# Skill: self-extension

**Use when:** a capability, tool, script, module or integration you need is
missing — or you are about to write the same throwaway code a second time and
want it to survive the turn instead of being retyped and re-checked.

Roadmap and rationale: `docs/plans/2026-08-12-atlas-self-extension-roadmap.md`.

## The trigger is reuse, not blockage

This skill used to say "read this when a missing capability is what *stops* you".
That trigger never fires. A live run on 2026-08-13 was asked to set itself up to
check JSON files for duplicate keys on demand, and answered it with two
`execute_code` calls and zero `atlas_*` calls — correctly, by the old rule,
because nothing stopped it. With code execution in hand almost nothing does.

So the moment to catch is not "I am blocked". It is **"I am about to write this
again"**: the operator says they will ask repeatedly, or you are reaching for
the same twenty lines you already wrote this session. Ad-hoc code is cheapest
exactly once. The second time you pay to rewrite it, re-read it, and re-establish
that it works — a disposable you can re-invoke has already paid for itself, and
it leaves a record that a later run can find.

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
4. **What is the cheapest thing over the whole session?** For a genuine one-off,
   a shell command or a query — not a new tool. But count the reruns: ad-hoc
   code is cheapest only the first time, and from the second it costs a rewrite
   and a fresh check every turn.

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
| A one-off script | Write it into the ATLAS scratch directory with your normal file tool (the path is in this turn's **Scratch** section) and run it with your terminal tool. ATLAS adopts it, expires it, and records it. `atlas_scratchpad op=materialize` does the same in one call and lets you state a rationale — better, but not required. |

Use `atlas module create` for a new module; see `module-builder.md`.

`op=materialize` is the whole L2 path: give it a title, a body, a language and a
`rationale`, get back an `invocation` line, and run that with your terminal tool
under the normal permission rules. The file lives under
`<ATLAS home>/scratch/tools`, never in the working tree, and it is deleted on
the next startup unless someone pins it. You may mint five per run — hitting
that cap means you are building around a problem instead of naming it.

**The `rationale` is required and it is read.** Answer questions 1 and 2 in it:
what you searched, and why this is a one-off rather than something durable. It
is stored on the entry, shown to the operator next to the tool, and written to
the audit trail permanently — so when the same disposable is built a third time,
the case for promoting it is already assembled. Write it for that reader, not to
satisfy the field. "Needed a script" tells them nothing; "checked `atlas_module
op=list` and the tool catalog, nothing parses this log format, and only this
mission needs it" tells them everything.

Your open scratchpad entries come back to you automatically at the start of a
run that resumes the same session (the **Open Scratchpad** section of the
brief). Write the plan before the long task; you will be handed it back rather
than having to remember to ask.

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
