# ATLAS Ultra — ultraaudit

Deep system audit with parallel subagent angles.

## Pipeline

```
1. SCOPE → 2. MAP SYSTEM → 3. DECOMPOSE AUDIT ANGLES → 4. PARALLEL AUDIT → 5. CROSS-CHECK → 6. SYNTHESIZE → 7. ARTIFACT
```

### Step 1: SCOPE (inline, 5 min)
- Parse audit target: system boundary, audit type (security/architecture/reliability/compliance/performance), depth
- Define what's in scope and what's out
- Set audit depth: quick (2-3 angles) / standard (4-6) / deep (6+ angles)

### Step 2: MAP SYSTEM (inline or subagent, 10 min)
- Read codebase structure, identify modules, layers, entry points, data flows
- Map external dependencies and their trust boundaries
- Identify critical paths and single points of failure

### Step 3: DECOMPOSE AUDIT ANGLES (inline, 5 min)
- Break into independent audit angles. Typical:
  - **Security**: authentication, authorization, secrets handling, input validation
  - **Architecture**: coupling, cohesion, dependency direction, layer violations
  - **Reliability**: error handling, retry logic, fallback paths, graceful degradation
  - **Compliance**: data handling, logging, audit trails, regulatory requirements
  - **Performance**: hot paths, N+1 queries, memory allocation, concurrency
  - **Data integrity**: schema validation, referential integrity, transaction boundaries
- Each angle → one subagent → one findings file

### Step 4: PARALLEL AUDIT (subagents, 10-20 min)
- Each subagent audits one angle using Code Investigation template (read-only)
- Each subagent:
  - Reads specific files relevant to their angle
  - Applies audit framework (OWASP, Well-Architected, etc.)
  - Documents findings with severity (CRITICAL/HIGH/MEDIUM/LOW), location (file:line), evidence, impact, remediation
  - Never fixes — only documents
- Subagents can use Read, Grep, Glob, Bash (read-only)

### Step 5: CROSS-CHECK (inline, 10 min)
- Check for overlapping findings, contradictions, gaps
- Verify severity ratings are consistent across angles
- Identify findings that span multiple angles (cross-cutting concerns)

### Step 6: SYNTHESIZE (inline, 10 min)
- Write unified audit report organized by severity
- Merge duplicate findings
- Prioritize remediation by: severity × blast radius × effort

### Step 7: ARTIFACT (inline, 5 min)
- Save to `{ARTIFACT_DIR}/ATLAS-ULTRAAUDIT-{slug}.md`

## Output Template

```markdown
# {System} — Audit Report

> Generated {date} · {N} audit angles · {audit_type}

## Executive Summary
3-5 bullet summary of most critical findings.

## System Map
Brief description of what was audited.

## Findings by Severity

### CRITICAL
| # | Finding | Location | Evidence | Impact | Remediation |
|---|---------|----------|----------|--------|-------------|

### HIGH
| # | Finding | Location | Evidence | Impact | Remediation |
|---|---------|----------|----------|--------|-------------|

### MEDIUM
| # | Finding | Location | Evidence | Impact | Remediation |
|---|---------|----------|----------|--------|-------------|

### LOW
| # | Finding | Location | Evidence | Impact | Remediation |
|---|---------|----------|----------|--------|-------------|

## Architecture Scorecard
| Dimension | Score | Notes |
|-----------|-------|-------|

## Compliance Matrix (if applicable)
| Requirement | Status | Evidence |

## Remediation Priority
| # | Finding | Severity | Effort | Priority |
|---|---------|----------|--------|----------|

## Open Questions
Items requiring further investigation.

## Sources
Audit frameworks and references used.
```

## ATLAS-native

Audit the mission lifecycle, actor spawning, gateway routing, audit ledger integrity, skill loading, and goal state machine. Check for: secrets in config, missing input validation, orphaned actors, stale skill references.

Overlap with existing:
- `ultrareview` is reactive (specific bug); `ultraaudit` is proactive (system sweep)
- `gsd/debug` is single-agent root cause
- `l2-extra-marathon-review` is quality gates for a deliverable

## Subagent Prompt Template

```
You are an audit subagent. Today is {DATE}.

Audit context: {AUDIT_DESCRIPTION}

Your ONLY task — audit this single angle:
{AUDIT_ANGLE}

Framework: {FRAMEWORK}

Rules:
1. Read the specific files: {FILE_LIST}
2. Apply the audit framework systematically
3. Document findings with:
   - Severity: CRITICAL / HIGH / MEDIUM / LOW
   - Location: exact file:line
   - Evidence: specific code or configuration
   - Impact: what could go wrong
   - Remediation: how to fix
4. Do NOT fix anything — only document
5. Write findings to {WORKSPACE}/findings/F{N}.md

Return: count of findings by severity, most critical finding summary.
```
