# GSD/L2 — Goal · Slice · Deliver

The L2 Systems execution doctrine, native to ATLAS. A ground-up rebrand and
refit of the GSD ("Get Stuff Done") framework for the ATLAS structure:
missions instead of orchestrator scripts, durable actors instead of ad-hoc
subagents, the audit ledger instead of trust, and the LLM Wiki instead of
loose learning notes.

**The doctrine in one line:** verified progress over apparent progress —
every goal becomes a bounded slice, every slice ends delivered or honestly
blocked, never "should work".

## The loop

```
GOAL ──► DISCUSS ──► PLAN ──► EXECUTE ──► VERIFY ──► SHIP
  ▲          │          │         │           │        │
  └──────────┴──────────┴─── PROGRESS (route anytime) ─┘
                              DEBUG (on any failure)
```

| Step | Skill | Produces |
|---|---|---|
| Bootstrap | `init.md` | `.planning/` contract: PROJECT.md, ROADMAP.md, STATE.md |
| Context | `discuss.md` | Phase CONTEXT.md — decisions locked before planning |
| Plan | `plan.md` | PLAN.md — tasks with done-conditions, goal-backward checked |
| Build | `execute.md` | Atomic commits + SUMMARY.md, deviations recorded |
| Prove | `verify.md` | VERIFICATION.md — evidence-tiered, UAT owed listed |
| Close | `ship.md` | Milestone audit, handoff, wiki filing |
| Anytime | `progress.md` | Situational report + route to the next step |
| On failure | `debug.md` | Root cause with proof before any fix |

## ATLAS-native mapping

| Upstream GSD concept | GSD/L2 on ATLAS |
|---|---|
| Orchestrator + subagent fleet | ATLAS mission (judged long-horizon loop) + durable actors (`atlas_actor` spawn/status/wait) |
| Slash commands in one CLI | `/gsd-*` module commands on every surface (WebUI palette, Chat composer, terminal) via `modules/gsd` |
| "Tests pass" claims | Evidence tiers: registered → configured → reachable → **verified-live**, with audit run ids as citations |
| Learnings markdown | LLM Wiki filing with provenance (when running inside ATLAS) |
| Session handoff | `skills/atlas/handoff.md` (pack-level, shared) |
| `.planning/` contract | Unchanged — GSD/L2 is drop-in compatible with existing GSD planning directories |

## How to invoke

- **Any surface:** `/gsd` (progress + routing), `/gsd-init`, `/gsd-discuss`,
  `/gsd-plan`, `/gsd-execute`, `/gsd-verify`, `/gsd-debug`, `/gsd-ship` —
  contributed by the `gsd` module (`atlas module sync` once per checkout).
- **Any runtime:** the skills are plain markdown; native ATLAS, Claude Code,
  or Codex follow them by reading the file. No harness-specific machinery.

## Rules that outrank convenience

1. Read state before editing; the repo is the memory, not the conversation.
2. One slice at a time, smallest coherent scope, deferred work written down.
3. Atomic commits; a commit that mixes concerns is a defect.
4. Claims carry evidence or the label "not verified".
5. Failures are reported with the output, never smoothed over.
6. Stop and surface: destructive actions, secrets, goal drift, or the same
   failure twice with no new information.
