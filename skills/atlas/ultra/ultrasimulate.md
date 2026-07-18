# ATLAS Ultra — Simulate

## Pipeline

```
1. LOAD PLAN → 2. DECOMPOSE → 3. PARALLEL SIMULATE → 4. TRACE DEPS → 5. SYNTHESIZE → 6. ARTIFACT
```

### Step 1: LOAD PLAN (inline, 5 min)
- Read the target plan/artifact (ULTRAPLAN, ULTRAREVIEW recommendations, or any structured plan)
- Parse into discrete tasks with: file list, code changes, dependencies
- Identify the plan's assumptions (table names, function signatures, consumer counts, import chains)
- Set simulation depth: quick (2 subagents) / standard (4) / deep (4+ parallel rounds)

### Step 2: DECOMPOSE (inline, 5 min)
- Split into independent simulation angles — one per phase or concern:
  - **Phase simulation**: walk through each task, predict exact code changes and failures
  - **Dependency tracing**: map all import chains for deletion/modification targets
  - **Blocker prediction**: identify runtime crashes, logic errors, integration failures
  - **Visual impact**: what changes on screen (for frontend plans)
- Each angle → one subagent → one findings file

### Step 3: PARALLEL SIMULATE (subagents, 10-20 min)
- Each subagent reads the plan AND the actual source files
- Simulates execution task-by-task as if implementing it
- For each task predicts:
  - **Exact code changes** needed (file, line, before/after)
  - **What breaks** when changes are made (runtime, build, type errors)
  - **Cascade effects** (downstream consumers, import chains)
  - **Likely mistakes** the implementer will make
  - **Verification gaps** (what tests won't catch)
- Subagents MUST read actual source code — never simulate from plan assumptions alone

### Step 4: TRACE DEPENDENCIES (subagent or inline, 10 min)
- For every file the plan says to DELETE:
  - Trace ALL imports (who imports this file?)
  - Trace ALL transitive imports (who imports the importers?)
  - Identify hidden chains the plan misses
- For every file the plan says to MODIFY:
  - Trace ALL consumers (what imports this file?)
  - Check for circular dependencies
  - Check for type-only imports that would break
- For every file modified by MULTIPLE phases:
  - Map the collision (which phases touch the same file?)
  - Predict merge conflicts in parallel execution

### Step 5: SYNTHESIZE (inline, 10-15 min)
- Read ALL simulation findings and dependency maps
- Categorize blockers: CRITICAL / HIGH / MEDIUM / LOW
- Rank by: severity × probability × blast radius
- Identify cross-phase issues that span multiple simulation angles
- Extract decisions needed before implementation can start
- Produce the simulation master report

### Step 6: ARTIFACT (inline, 5 min)
- Save simulation reports to `{ARTIFACT_DIR}/simulation/`:
  - `PHASE{N}-simulation.md` — per-phase detailed simulation
  - `DEPENDENCY-map.md` — import chain analysis
  - `SIMULATION-MASTER-REPORT.md` — unified findings

## Simulation Angles

| Angle | Subagent Type | What It Does |
|-------|--------------|--------------|
| Phase Simulation | general | Walks through each task, reads source, predicts failures |
| Dependency Tracing | explore | Traces all import chains for deletion/modification targets |
| Blocker Prediction | general | Identifies runtime crashes, logic errors, integration gaps |
| Visual Impact | explore | Analyzes UI changes, component modifications, new elements |

**Standard depth**: 4 subagents (1 per angle)
**Deep depth**: 4+ subagents, with additional rounds for multi-phase plans

## Blocker Classification

| Severity | Definition | Example |
|----------|-----------|---------|
| CRITICAL | Runtime crash, data loss, or security hole | `timingSafeEqual` throws on unequal buffers |
| HIGH | Build failure, broken integration, missing dependency | `zod` not installed, wrong table name in SQL |
| MEDIUM | Logic error, performance issue, UX regression | Status value mismatch, no error display in modals |
| LOW | Cosmetic, documentation, minor inconsistency | File count off by 2, missing comment |

## Output Template

```markdown
# {Project/Plan} — Implementation Simulation

> Generated {date} · {N} parallel simulations · {M} total blockers
> CRITICAL: {c} · HIGH: {h} · MEDIUM: {m} · LOW: {l}
> Hidden dependency chains: {d}

## Executive Summary
3-5 bullet summary of most dangerous findings.

## Phase-by-Phase Simulation

### Phase {N}: {Name}

#### Blockers Found
| # | Severity | Blocker | Location | Impact |
|---|----------|---------|----------|--------|
| 1 | CRITICAL | {description} | {file:line} | {what breaks} |

#### What the Implementer Will Most Likely Get Wrong
1. {mistake 1}
2. {mistake 2}

#### Predicted Cascade Effects
{how failures propagate}

### [Repeat for each phase]

## Hidden Dependency Chains

| # | Severity | Chain | Plan Coverage |
|---|----------|-------|---------------|
| 1 | CRITICAL | {importer} → {dependency} | {gap description} |

## File Collision Map

| File | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|------|---------|---------|---------|---------|
| {file} | {change} | {change} | — | — |

## Visual Impact (if applicable)
| Change | Visual Impact | Risk |
|--------|--------------|------|

## Decisions Needed Before Implementation
| # | Decision | Options | Recommendation |
|---|----------|---------|----------------|

## Revised Execution Order
{updated order accounting for discovered blockers}

## Summary Statistics
| Metric | Count |
|--------|-------|
| Total blockers | {n} |
| CRITICAL | {n} |
| Hidden chains | {n} |
| File collisions | {n} |
| Decisions needed | {n} |
```

## Subagent Prompt Templates

### Phase Simulation Subagent

```
You are an implementation simulator. Today is {DATE}.

Project: {PROJECT_NAME} ({PROJECT_PATH})

Your task: SIMULATE the execution of {PHASE_OR_SECTION} of the {PLAN_NAME}.

Walk through each step as if you were implementing it, and predict every problem.

Read the plan at {PLAN_PATH}.
Then read EVERY source file that the phase touches — do not skip any.

For EACH task in the phase, simulate:
1. What code changes are needed (exact lines, before/after)
2. What breaks when you make those changes
3. What downstream effects cascade
4. What the implementer will likely get wrong
5. What tests/verification will catch vs miss

Write to {WORKSPACE}/simulation/PHASE{N}-simulation.md:

# Phase {N} Simulation
## Task {N.M}: {Task Name}
### Expected changes
### What breaks
### Cascade effects
### Likely mistakes
## Blockers Summary
[runtime crashes, build failures, logic errors, integration gaps]

Return: count of blockers, severity breakdown.
```

### Dependency Tracing Subagent

```
You are a dependency chain analyzer. Today is {DATE}.

Project: {PROJECT_NAME} ({PROJECT_PATH})

Your task: Find ALL hidden import/dependency chains the plan doesn't account for.

Read the plan at {PLAN_PATH}.
For every file the plan says to DELETE, trace ALL imports using Grep.
For every file the plan says to MODIFY, trace ALL consumers.
Check for circular dependencies and type-only import risks.

Write to {WORKSPACE}/simulation/DEPENDENCY-map.md:

# Dependency Chain Map
## Deletion Impact
### {file} → [all importers]
## Modification Impact
### {file} → [all consumers]
## Circular Dependencies
## Hidden Chains the Plan Misses

Return: total chains found, count of hidden/missed chains.
```

### Visual Impact Subagent

```
You are a UI/visual impact analyst. Today is {DATE}.

Project: {PROJECT_NAME} ({PROJECT_PATH})

Your task: Identify EVERY visual/UI change from the plan implementation.

Read the plan at {PLAN_PATH}.
Read the actual UI source files (components, CSS, layouts).
For EACH plan item, determine: does it change any visual output?

Write to {WORKSPACE}/simulation/visual-impact.md:

# Visual Impact Analysis
## New Visual Elements
[what will appear on screen]
## Modified Visual Elements
[what will look different]
## Unchanged Elements
[confirm no visual regression]
## Visual Risks
[changes that might break existing polish]

Return: count of visual changes, risk level.
```

## Cross-Mode Dependencies

```
ultrasimulate is typically used:
  AFTER  → ultraplan (simulate the plan before executing)
  AFTER  → ultrareview (simulate the proposed fixes)
  BEFORE → ultraexecute (simulate first, then execute with confidence)

Output feeds into:
  ultraexecute → implementation with known risks mitigated
  ultrareview  → post-implementation verification of predicted issues
```

## Resumability

Simulation artifacts are per-phase. If a phase simulation is complete (file exists), skip it and move to the next. The master report is always regenerated from all phase files.

## ATLAS-native

Simulation subagents read from the ATLAS source tree. They need read access to `services/`, `foundation/`, `skills/`, and `.planning/`. Check for ATLAS-specific hidden chains: module registrations, gateway route bindings, skill loading paths.
