# ATLAS Ultra — Plan

## Pipeline

```
1. SCOPE → 2. RESEARCH → 3. DECOMPOSE → 4. PARALLEL RESEARCH → 5. SYNTHESIZE → 6. VALIDATE → 7. ARTIFACT
```

### Step 1: SCOPE (inline, 5 min)
- Parse user intent into: goal, constraints, domain, stakeholders
- Write `brief.md` with refined question, scope boundaries, assumptions
- Determine research depth: quick (2-3 subagents) / standard (4-6) / deep (6+ per round)

### Step 2: RESEARCH (inline or subagent, 10 min)
- Read existing codebase (if applicable): key files, architecture, patterns
- Read existing artifacts (if resuming): previous plans, reviews, specs
- Identify knowledge gaps that need external research

### Step 3: DECOMPOSE (inline, 5 min)
- Break the problem into N **independent** research angles
- Each angle: one sentence, one subagent, one output file
- Order: dependencies first, independent angles in parallel
- Write angle list to `brief.md`

### Step 4: PARALLEL RESEARCH (subagents, 5-15 min)
- Spawn one subagent per angle (ALL in one message)
- Each subagent:
  - Receives: angle description + brief context + workspace path
  - Produces: `findings/F{N}.md` with structured claims + sources
  - Returns: 3-5 line summary only
- Never run subagents sequentially when they're independent

### Step 5: SYNTHESIZE (inline, 10-20 min)
- Read ALL `findings/*.md`
- Write unified artifact following template (see below)
- Organize by THEME, not by subagent/angle
- Inline citations `[n]` mapping to Sources section

### Step 6: VALIDATE (inline, 5 min)
- Check: does the artifact answer the original question?
- Check: are there gaps (single-source claims, unverified assumptions)?
- Check: are recommendations actionable (not theoretical)?
- If gaps found: spawn targeted follow-up subagents (delta-queries)

### Step 7: ARTIFACT (inline, 5 min)
- Save to `{ARTIFACT_DIR}/ATLAS-ULTRA-PLAN-{slug}.md` (resolved per SKILL.md Saving Results)
- Include: Executive Summary, Body, Open Questions, Sources

## Output Template

```markdown
# {Topic} — Plan

> Generated {date} · {N} sources · {mode}

## Executive Summary
5-10 bullet key decisions and recommendations.

## Background & Scope
What was planned, boundaries, assumptions.

## Architecture / Design
[Organized by theme, with diagrams where applicable]

## Requirements
| ID | Requirement | Priority | Rationale |
|----|-------------|----------|-----------|

## Implementation Phases
### Phase 1: {Name}
- Goal
- Deliverables
- Effort estimate
- Dependencies
- Risks

## Risk Register
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|

## Success Metrics
KPIs for each phase and overall.

## Open Questions
Unresolved items requiring future research.

## Sources
[1] Title — URL (accessed date)
```

## Subagent Prompt Template

```
You are a planning subagent. Today is {DATE}.

Context: {BRIEF_CONTEXT}

Your ONLY task — research this single angle, nothing else:
{ANGLE}

Rules:
1. Run up to {N} web searches.
2. WebFetch the 3-6 most promising results.
3. Write findings to {WORKSPACE}/findings/F{N}.md in this format:

# F{N}: {ANGLE}

## Findings
### [1] <claim>
- quote: "<verbatim>"
- url: <URL>
- source_type: primary | secondary | community
- confidence: high | medium | low

## Dead ends
## Suggested follow-ups

4. Aim for 5-12 findings.
5. Return ONLY: 3-5 line summary, file path, finding count, confidence.
```

## ATLAS-native

When planning an ATLAS feature, read `.planning/` contract first. Parallel research subagents can run as durable actors for large research tasks. The plan artifact should reference audit run ids. If the plan produces a mission, mark it `[mission-ok]`.
