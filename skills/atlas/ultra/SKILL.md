---
name: ultra
description: |
  ATLAS Ultra doctrine — unified framework for methodical, proof-based, subagent-native work.
  Routes to the right mode (plan, review, design, execute, research, simulate, audit, synthesize, migrate) based on intent.
  Core principle: every task produces a structured artifact with verifiable evidence.
  Use when: "ultra", "ultraplan", "ultrareview", "ultradesign", "ultraexecute", "ultrasimulate",
  "ultraaudit", "ultrasynthesize", "ultramigrate",
  or any task requiring systematic investigation, planning, design, execution, or implementation simulation.
---

# ATLAS Ultra — Unified Doctrine for Subagent-Native Work

## Core Doctrine (7 Principles)

Every ultra task follows these principles regardless of mode:

### 1. Methodical Steps
Never skip phases. Never wing it. Every mode has a defined pipeline. Follow it.

### 2. Proof-Based Findings
Every claim must have evidence. Code references: `file:line`. Data references: specific values. External sources: URLs with dates. No assertions without proof.

### 3. Structured Output
Every artifact follows a template. Templates ensure completeness and consistency across sessions. No freeform prose as the primary output.

### 4. Pattern Recognition
Apply known patterns to new situations before inventing solutions. Reference patterns from existing code, industry standards, or prior investigations.

### 5. Quality Gates
Every mode has verification steps. Don't declare done until quality gates pass. If a gate fails, iterate — don't skip.

### 6. File Persistence
Every investigation produces a permanent artifact on disk. Artifacts are versioned, referenceable, and resumable.

### 7. Subagent-Native
Parallelize when tasks are independent. Isolate when context is heavy. Use as many subagents as the task warrants — not a fixed number. Each subagent gets ONE angle, ONE file, ONE summary.

## Mode Router

Based on user intent, route to the appropriate mode:

| Intent Signal | Mode | File |
|---|---|---|
| "plan", "design", "spec", "architecture", "strategy" | `ultraplan` | `ultraplan.md` |
| "investigate", "debug", "root cause", "review", "forensics" | `ultrareview` | `ultrareview.md` |
| "build", "create", "UI", "frontend", "dashboard" | `ultradesign` | `ultradesign.md` |
| "implement", "execute", "ship", "build this" | `ultraexecute` | `ultraexecute.md` |
| "research", "analyze", "compare", "survey" | `ultraresearch` | `ultraresearch.md` |
| "simulate", "dry-run", "predict blockers", "walk through", "foreshadow" | `ultrasimulate` | `ultrasimulate.md` |
| "audit", "sweep", "security scan", "compliance check" | `ultraaudit` | `ultraaudit.md` |
| "synthesize", "fuse", "merge findings", "cross-reference" | `ultrasynthesize` | `ultrasynthesize.md` |
| "migrate", "port", "upgrade", "transition" | `ultramigrate` | `ultramigrate.md` |

**When ambiguous**: Ask the user which mode, or infer from context and confirm.

## Subagent Orchestration Pattern

All modes use the same subagent pattern:

```
Task → Decompose into N independent angles
  → Spawn N subagents (one per angle)
  → Each subagent: researches ONE angle, writes ONE file, returns ONE summary
  → Synthesize all findings into unified artifact
  → Quality gate: verify completeness, check gaps
  → Persist final artifact
```

**How many subagents?** As many as the task warrants:
- Simple task: 0 subagents (inline work)
- Medium task: 2-4 subagents
- Complex task: 5-8 subagents
- Massive task: batched rounds of 6 subagents each

**Never force a fixed number.** The task determines the count.

## Artifact Naming

All ultra artifacts follow: `ATLAS-ULTRA-{MODE}-{slug}.{md}`

Examples:
- `ATLAS-ULTRAPLAN-modular-cashflow.md`
- `ATLAS-ULTRAREVIEW-auth-bug.md`
- `ATLAS-ULTRADESIGN-dashboard-v2.md`
- `ATLAS-ULTRAEXECUTE-phase-1.md`
- `ATLAS-ULTRARESEARCH-payment-gateways.md`
- `ATLAS-ULTRAAUDIT-security-sweep.md`
- `ATLAS-ULTRASYNTH-cross-source.md`
- `ATLAS-ULTRAMIGRATE-python-to-rust.md`

Simulation artifacts use a subdirectory: `{ARTIFACT_DIR}/simulation/PHASE{N}-{slug}.md`

## Cross-Mode Dependencies

Modes can chain:
```
ultraresearch → ultraplan → ultrasimulate → ultraexecute → ultrareview
                                              ultraaudit ─┘
                                              ultrasynthesize ─┘
```

Each mode's output is input for the next. Artifacts persist between modes.

**Simulation gate**: Before executing a complex plan, run `ultrasimulate` to predict blockers. This catches critical issues (runtime crashes, missing dependencies, broken imports) before they waste implementation time.

## Resumability

Every mode supports resumption:
- Check which steps are complete (file exists = done)
- Skip completed steps
- Pick up from last incomplete step
- Append to existing artifact (don't overwrite)

## Saving Results

Artifacts save to the project's ultra output directory, resolved in this order:

1. **If `.mimocode/artifacts/` exists** → use `.mimocode/artifacts/ultra/`
2. **If `.planning/` exists** → use `.planning/ultra/`
3. **Otherwise** → create `.ultra/` in the project root

This keeps ultra artifacts alongside the project's own planning infrastructure when it exists, or in a dedicated `.ultra/` directory when it doesn't.

```
# Resolution logic:
if [ -d ".mimocode/artifacts" ]; then
  ARTIFACT_DIR=".mimocode/artifacts/ultra"
elif [ -d ".planning" ]; then
  ARTIFACT_DIR=".planning/ultra"
else
  ARTIFACT_DIR=".ultra"
fi
mkdir -p "$ARTIFACT_DIR"
```

All mode files reference this as `{ARTIFACT_DIR}` — never hardcode the path.

## ATLAS Integration

Ultra modes integrate with the ATLAS runtime:

- **Missions**: Any ultra mode can run as an ATLAS mission. Tag the mode file with `mission-ok` when the pipeline is autonomous enough for a judged run.
- **Durable actors**: Parallel subagent steps can use ATLAS durable actors (`atlas_actor` spawn/status/wait) instead of ephemeral subagents. Tag parallelizable steps with `[actor-ok]` in mode files.
- **Audit ledger**: Every ultra artifact cites the audit run id for reproducibility.
- **Skill loading**: Ultra modes load via the ATLAS skill system — the agent reads the relevant `.md` file.
- **Handoff**: Ultra artifacts follow `skills/atlas/handoff.md` format for session continuity.

## GSD Chain

Ultra modes chain into the GSD execution doctrine:

```
ultraplan → gsd/init → gsd/discuss → gsd/plan → gsd/execute → gsd/ship
```

- `ultraplan` produces strategic plans; `gsd/plan` produces tactical phase plans
- `ultraexecute` wraps `gsd/execute` per wave (wave decomposition is the differentiator)
- `ultrareview` is parallel multi-angle investigation; `gsd/debug` is single-agent root cause
- `ultraaudit` is proactive system sweep; `gsd/verify` is per-deliverable quality gate
