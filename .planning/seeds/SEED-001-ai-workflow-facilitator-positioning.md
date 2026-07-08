---
id: SEED-001
status: dormant
planted: 2026-07-07
planted_during: unknown
trigger_when: when scoping ATLAS's mission/task-planning layer, or when defining the north-star product positioning for public-facing copy (portfolio, README, marketing)
scope: unknown
---

# SEED-001: ATLAS as a complete AI-workflow facilitator — full-modularity cockpit for structured task breakdown, mission investigation, and forward-looking planning

## Why This Matters

Captured verbatim (translated) from Davi during a L2-PORTFOLIO redesign brainstorm session, while discussing how to market ATLAS on the portfolio site (2026-07-07). This is his own articulation of what ATLAS should ultimately be — a north-star positioning statement, not yet scoped into a phase or reconciled against the current roadmap/README framing (mission control / audit-first / persistent knowledge / extensible harness).

Davi's words (paraphrased close to original):

> The goal of ATLAS is to be a complete AI cockpit that facilitates any and all kinds of AI-assisted workflow and development work, with full modularity — still in development. The intent is to be a development facilitator that breaks simple and complex tasks into structured steps, investigates all aspects of a mission, breaks it into details, sees the future of a task — what will become a blocker, what will need to be done, best practices — and, based on all context acquired and acquirable, determines the plausible next steps. Native integration for: loop engineering, spec-driven development, goal architecture.

This reframes ATLAS less as "an auditable agent runtime you watch" (current README framing) and more as "a planning/facilitation brain that structures and forecasts AI-assisted work" — closer to a GSD-style loop-engineering system than a pure execution cockpit. Worth reconciling against current v0.1 scope (Mission control, audit-first, persistent knowledge/Codex, extensible harness) — likely an evolution/emphasis shift rather than a contradiction, but the "forecast blockers / plausible next steps from context" capability doesn't appear to exist yet in v0.1 and may need its own phase.

## When to Surface

**Trigger:** when scoping ATLAS's mission/task-planning layer, or when defining the north-star product positioning for public-facing copy (portfolio, README, marketing).

This seed will surface during `/gsd-new-milestone` when the milestone scope matches.

## Scope Estimate

**Unknown** — run `/gsd-capture --seed --enrich SEED-001` to estimate effort.

## Breadcrumbs

- `README.md` — current v0.1 positioning ("auditable AI agent cockpit... mission control, runtime execution, live audit streams, artifact persistence, LLM Wiki filing")
- `docs/architecture/OVERVIEW.md` — architecture context for where a task-forecasting/blocker-prediction layer would plug in
- `docs/golden-workflows.md` — existing Repo Triage / Research Brief / Self-Review workflows are the closest existing analog to "breaking a mission into structured steps"
- Related external context: `C:\Users\Davi\Desktop\Projects\L2-PORTFOLIO\components\AtlasSection.tsx` — the portfolio section being redesigned when this idea surfaced; its copy should eventually reflect whichever positioning wins

## Notes

Captured via /gsd-capture during a cross-project brainstorm (L2-PORTFOLIO), not from inside this repo's own planning session. Davi asked explicitly for this to be filed here so a future ATLAS session can evaluate and act on it.
