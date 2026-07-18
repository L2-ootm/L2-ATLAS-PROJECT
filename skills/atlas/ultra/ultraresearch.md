# ATLAS Ultra — Research

## Pipeline

```
1. BRIEF → 2. PLAN ANGLES → 3. PARALLEL RESEARCH → 4. REFLECT → 5. SYNTHESIZE → 6. VALIDATE → 7. ARTIFACT
```

### Step 1: BRIEF (inline, 5 min)
- Refine the research question
- Define scope boundaries (what's in, what's out)
- Set depth: quick (2-3 subagents) / standard (4-6) / deep (6+ per round)
- Write `brief.md`

### Step 2: PLAN ANGLES (inline, 5 min)
- Decompose question into N **independent** research angles
- Each angle: one sentence, clearly bounded
- Pull from lenses: facts, recent developments, data, counter-arguments, practitioners, key players
- For deep mode: show angle list to user for confirmation

### Step 3: PARALLEL RESEARCH (subagents, 5-15 min)
- Spawn ALL subagents in ONE message
- Each subagent:
  - Runs 4-8 web searches
  - WebFetches 3-6 most promising results
  - Writes `findings/F{N}.md` with structured claims
  - Returns 3-5 line summary only
- Never run sequentially when independent

### Step 4: REFLECT (inline, 5 min)
- Read ALL `findings/*.md`
- Check: which parts of brief have no evidence?
- Check: which claims rest on single source?
- Check: where do sources conflict?
- If gaps + budget remaining: spawn delta-query subagents (one round max)

### Step 5: SYNTHESIZE (inline, 10-20 min)
- Write unified report following template
- Organize by THEME, not by subagent
- Inline citations `[n]` for every non-obvious claim
- Mark single-source claims: `[single source]`
- Mark speculation: `[speculative]`

### Step 6: VALIDATE (inline, 5 min)
- Critique pass: read as hostile reviewer
- Unsupported claims? Stale data? Missing counter-view?
- Fix in place before finalizing

### Step 7: ARTIFACT (inline, 5 min)
- Save to `{ARTIFACT_DIR}/ATLAS-ULTRA-RESEARCH-{slug}.md` (resolved per SKILL.md Saving Results)

## Multi-Round Research

For topics requiring progressive depth:

```
Round 1: Panoramic → REPORT-panoramic.md
Round 2: Technical depth → REPORT-technical.md
Round 3: Infrastructure → REPORT-infrastructure.md
...
```

Each round:
- Reads previous round's "Open Questions"
- Explores NEW angles (never repeats)
- Tracks cumulative findings: F1 → F2 → ... → F{N}
- Each round produces its own report

## Output Template

```markdown
# {Topic} — Research Report

> Generated {date} · depth: {mode} · {N} sources

## Executive Summary
5-10 bullet key findings. Each cites [n].

## Background & Scope
What was researched, boundaries, assumptions.

## <Body Sections — by THEME>
Synthesize across findings. Inline citations.
- conflicts: present both sides with dates
- single-source claims: flag with [single source]
- speculation: flag with [speculative]

## Comparison Table (if applicable)
| Option | Dimensions | Sources |

## Open Questions
Unresolved gaps, items needing deeper research.

## Sources
[1] Title — URL (published date, accessed date)
```

## Subagent Prompt Template

```
You are a research subagent. Today is {DATE}.

Research context: {BRIEF_CONTEXT}

Your ONLY task — research this single angle:
{ANGLE}

Rules:
1. Run up to {N} web searches. Start with 2-3 differently-phrased queries.
2. WebFetch the 3-6 most promising results.
3. Judge sources: official/primary > reputable > forums > content farms.
4. Write findings to {WORKSPACE}/findings/F{N}.md:

# F{N}: {ANGLE}

## Findings
### [1] <claim>
- quote: "<verbatim>"
- url: <URL>
- source_type: primary | secondary | community
- published: <date>
- confidence: high | medium | low

## Dead ends
## Suggested follow-ups

5. Aim for 5-12 findings.
6. Return: 3-5 line summary, file path, finding count, confidence.
```

## ATLAS-native

Research subagents can run as durable actors for deep research. Multi-round research feeds into ultraplan or ultrasynthesize. Source quality: ATLAS internal docs are primary sources.
