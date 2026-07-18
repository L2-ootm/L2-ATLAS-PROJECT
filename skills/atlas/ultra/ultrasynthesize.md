# ATLAS Ultra — ultrasynthesize

Cross-source intelligence fusion.

## Pipeline

```
1. COLLECT INPUTS → 2. CLASSIFY THEMES → 3. DECOMPOSE THEME ANALYSIS → 4. PARALLEL THEME SYNTHESIS → 5. CROSS-REFERENCE → 6. RESOLVE CONFLICTS → 7. ARTIFACT
```

### Step 1: COLLECT INPUTS (inline, 5 min)
- Read all input artifacts, list them with paths and types
- Identify source count, date ranges, and coverage areas
- Note any gaps in the input set

### Step 2: CLASSIFY THEMES (inline, 5 min)
- Identify recurring themes across inputs
- Group related findings into theme clusters
- Prioritize themes by: frequency × impact × confidence

### Step 3: DECOMPOSE THEME ANALYSIS (inline, 5 min)
- Each theme → one subagent → one synthesis file
- Each subagent receives: theme description, all relevant input excerpts, synthesis instructions
- Order: core themes first, peripheral themes in parallel

### Step 4: PARALLEL THEME SYNTHESIS (subagents, 10-15 min)
- Each subagent merges claims about their theme from multiple sources
- Each subagent:
  - Reads all input files relevant to their theme
  - Merges overlapping claims
  - Surfaces disagreements between sources
  - Flags single-source claims
  - Identifies gaps in coverage
  - Writes theme synthesis to findings file

### Step 5: CROSS-REFERENCE (inline, 10 min)
- Check theme agreement and conflicts
- Identify cross-theme dependencies
- Verify no contradictions between theme syntheses

### Step 6: RESOLVE CONFLICTS (inline, 10 min)
- Present both sides of each conflict
- Recommend resolution based on source quality and recency
- Build priority matrix: theme × confidence × actionability

### Step 7: ARTIFACT (inline, 5 min)
- Save to `{ARTIFACT_DIR}/ATLAS-ULTRASYNTH-{slug}.md`

## Output Template

```markdown
# {Topic} — Synthesis Report

> Generated {date} · {N} input sources · {M} themes

## Executive Summary
5-10 bullet key findings from the synthesis.

## Input Sources
| # | Source | Type | Date | Coverage |
|---|--------|------|------|----------|

## Theme Analysis

### Theme 1: {Name}
**Confidence**: high | medium | low

#### Merged Findings
{Consolidated claims from all sources}

#### Disagreements
{Where sources conflict}

#### Single-Source Claims
{Claims from only one source — treat with caution}

#### Gaps
{What's missing}

### [Repeat for each theme]

## Conflict Resolution
| # | Conflict | Source A | Source B | Resolution | Rationale |
|---|----------|----------|----------|------------|-----------|

## Priority Matrix
| Theme | Confidence | Actionability | Priority |
|-------|------------|---------------|----------|

## Gap Report
| # | Gap | Impact | Recommendation |
|---|-----|--------|----------------|

## Open Questions
Items requiring further investigation.

## Sources
All input sources with dates and types.
```

## ATLAS-native

Fuse findings from multiple ULTRARESEARCH rounds, ULTRAREVIEW investigations, and ULTRAAUDIT sweeps into a master action plan. Theme synthesis subagents can run as durable actors for complex multi-theme fusion.

## Subagent Prompt Template

```
You are a theme synthesis subagent. Today is {DATE}.

Theme: {THEME_NAME}

Input files: {FILE_LIST}

Your ONLY task — synthesize findings about this single theme:
{SYNTHESIS_INSTRUCTIONS}

Rules:
1. Read ALL input files
2. Organize by theme, not by source file
3. Merge overlapping claims
4. Surface disagreements between sources
5. Flag single-source claims
6. Identify gaps in coverage
7. Write to {WORKSPACE}/findings/F{N}.md

Return: 3-5 line summary of theme synthesis, confidence level.
```
