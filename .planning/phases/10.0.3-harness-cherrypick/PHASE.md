# 10.0.3 — Harness Cherry-Pick: PI & OpenCode Pattern Intake

> Status: **planned** (in-flight; sequence item #5). **Research intake — produces a doc, not code.**
> Owner concern: `docs/research/`. Informs #6 de-brand and the paused v1.1 harness phases (10.1–10.4).

## Intent

ATLAS's harness is a vendored, diverged Hermes (D-018). Two other open agent harnesses — **PI** and
**OpenCode** — have patterns worth adopting. There are **no local clones** (verified: OpenCode appears
only as a provider benchmark; PI is unreferenced), so this is a deliberate research intake: survey their
patterns from public sources, map each to an ATLAS gap, and classify adopt / adapt / skip with rationale.
The principle (per GATEWAY-BRIEF): *cherry-pick patterns, not fork code* — ATLAS stays a standalone
runtime that ingests good ideas.

## Scope

**In scope — produce `docs/research/HARNESS_CHERRYPICK_PI_OPENCODE.md`:**
- Survey dimensions to evaluate each harness against:
  - Session / permission model (approval gates, read-only-by-default, sandbox).
  - Tool manifest / tool registry shape (cross-ref ATLAS Tool Manifest v0, phase 10.0.4).
  - Provider/model routing + fallback (cross-ref ATLAS model_router, 10.3).
  - Agent loop / plan mode / multi-step execution + checkpointing.
  - TUI / client architecture (cross-ref ATLAS TUI, 10.4).
  - Context / memory management (cross-ref memory router, item #1).
  - Extensibility (plugins, MCP, skills).
- For each pattern: short description, ATLAS current state, verdict **adopt / adapt / skip**, rationale,
  and the ATLAS phase that would own it.
- License posture note per source (can we reference ideas vs reuse code — ideas/page-sets aren't
  copyrightable; direct code/asset reuse is license-gated, mirror the Odysseus stance in STATE).

**Out of scope:**
- Cloning or vendoring either repo.
- Implementing any adopted pattern (each becomes a follow-up in its owning phase).

## Approach

1. Web research on PI and OpenCode public docs/repos for the survey dimensions (verify current state;
   do not rely on memory for fast-moving projects).
2. Map findings to ATLAS gaps using the existing analysis docs (GATEWAY-BRIEF, FOUNDATION-AND-CHANNELS).
3. Write the classified intake doc; cross-reference owning phases.

## Acceptance

- `docs/research/HARNESS_CHERRYPICK_PI_OPENCODE.md` exists with every surveyed pattern classified
  adopt/adapt/skip + rationale + owning phase, and a per-source license posture note.
- No code changes; no repo clones added to the tree.

## Notes
- Treat as the harness analog of the Odysseus baseline: *borrow the direction, write our own code.*
