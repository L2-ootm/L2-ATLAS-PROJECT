# ATLAS Ultra — ultramigrate

Systematic migration planning and execution.

## Pipeline

```
1. INVENTORY → 2. DECOMPOSE MODULES → 3. PLAN MIGRATION WAVES → 4. PARALLEL MIGRATE → 5. VERIFY COMPATIBILITY → 6. VERIFY DATA INTEGRITY → 7. ARTIFACT
```

### Step 1: INVENTORY (inline or subagent, 10 min)
- Map all modules, dependencies, interfaces, data formats
- Identify source and target states for each component
- Document current API contracts and data schemas
- Set migration scope: what's in, what's deferred

### Step 2: DECOMPOSE MODULES (inline, 5 min)
- Group into waves by dependency order
- Identify: independent modules (can parallel), dependent modules (must sequence)
- Map inter-module dependencies for wave ordering
- Each module → one migration unit

### Step 3: PLAN MIGRATION WAVES (inline, 10 min)
- Define per wave:
  - **Source state**: what exists now
  - **Target state**: what should exist after migration
  - **Compatibility layer**: how old and new coexist during transition
  - **Rollback trigger**: when to abort and revert
  - **Verification**: how to confirm success

### Step 4: PARALLEL MIGRATE (subagents, varies)
- Each subagent migrates one independent module
- Each subagent:
  - Reads current source code
  - Reads target specification
  - Makes migration changes
  - Runs module-level tests
  - Returns summary with deviations from plan
- **Never** let subagents modify shared interfaces in the same wave

### Step 5: VERIFY COMPATIBILITY (inline or subagent, 10 min)
- Run integration tests
- Check API contracts between migrated and unmigrated modules
- Verify backward compatibility during transition
- Test the compatibility layer

### Step 6: VERIFY DATA INTEGRITY (inline or subagent, 10 min)
- Check no data loss during migration
- Verify schema transformations are correct
- Test rollback procedures
- Confirm no data drift between source and target

### Step 7: ARTIFACT (inline, 5 min)
- Save to `{ARTIFACT_DIR}/ATLAS-ULTRAMIGRATE-{slug}.md`

## Output Template

```markdown
# {Migration} — Migration Plan

> Generated {date} · {N} modules · {M} waves

## Executive Summary
3-5 bullet summary of migration approach and key risks.

## Module Map
| # | Module | Source State | Target State | Dependencies | Wave |
|---|--------|--------------|--------------|--------------|------|

## Migration Waves

### Wave 1: {Name}
**Goal**: {what this wave achieves}

| Module | Source | Target | Compatibility Layer | Rollback Trigger |
|--------|--------|--------|---------------------|------------------|

**Verification**: {how to confirm wave success}

### [Repeat for each wave]

## Compatibility Matrix
| Old Module | New Module | Interface | Compatibility Method |
|------------|------------|-----------|---------------------|

## Data Integrity Verification
| Check | Method | Status |
|-------|--------|--------|

## Rollback Procedures
| Wave | Rollback Trigger | Rollback Steps | Recovery Time |
|------|------------------|----------------|---------------|

## Execution Log
| Wave | Module | Status | Deviations |
|------|--------|--------|------------|

## Open Questions
Items requiring further investigation.

## Sources
Migration patterns and references used.
```

## ATLAS-native

Python-to-Rust migration of CLI, policy, executor, mission parser, state modules. Independent module migrations tagged `[actor-ok]` for parallel durable actor execution. The migration artifact feeds into `gsd/execute.md` for wave-by-wave implementation.

## Subagent Prompt Template

```
You are a migration subagent. Today is {DATE}.

Migration context: {MIGRATION_DESCRIPTION}

Your ONLY task — migrate this single module:
{MODULE_DESCRIPTION}

Source: {SOURCE_PATH}
Target: {TARGET_SPEC}
Compatibility plan: {COMPATIBILITY_PLAN}

Rules:
1. Read the current source code
2. Read the target specification
3. Make migration changes following the compatibility plan
4. Run module-level tests (if available)
5. Document any deviations from the plan
6. Write summary to {WORKSPACE}/findings/F{N}.md

Return: 3-5 line summary, deviations count, test status.
```
