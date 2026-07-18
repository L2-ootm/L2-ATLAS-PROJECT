# ATLAS Ultra — Review

## Pipeline

```
1. UNDERSTAND → 2. DECOMPOSE → 3. PARALLEL INVESTIGATE → 4. SYNTHESIZE → 5. VALIDATE → 6. ARTIFACT
```

### Step 1: UNDERSTAND (inline, 5 min)
- Parse: expected behavior vs actual behavior
- Identify: error messages, symptoms, affected area
- Scope: single function? module? cross-module flow?

### Step 2: DECOMPOSE (inline, 5 min)
- Break investigation into independent investigation angles
- Examples:
  - "Auth bug" → (1) session handling, (2) middleware chain, (3) DB queries
  - "Performance issue" → (1) query analysis, (2) N+1 detection, (3) caching gaps
- Each angle → one subagent → one findings file

### Step 3: PARALLEL INVESTIGATE (subagents, 5-15 min)
- Each subagent:
  - Reads specific files (Grep, Glob, Read)
  - Traces data flow from entry to failure point
  - Documents: exact `file:line`, specific code block, technical explanation
  - Never fixes — only documents
- Subagents can use Read, Grep, Glob, Bash (read-only)

### Step 4: SYNTHESIZE (inline, 10 min)
- Read ALL findings
- Build failure chain: Step 1 → Step 2 → ... → Failure Point
- Root cause: THE specific code that causes the issue
- Related issues: other problems found during investigation

### Step 5: VALIDATE (inline, 5 min)
- Read the actual code at the identified failure point
- Confirm the finding is correct (not just plausible)
- If wrong: re-investigate, don't guess

### Step 6: ARTIFACT (inline, 5 min)
- Save to `{ARTIFACT_DIR}/ATLAS-ULTRA-REVIEW-{slug}.md` (resolved per SKILL.md Saving Results)

## Output Template

```markdown
# {Issue} — Investigation

## Root Cause: {One-line description}

**Exact Failure Point:** `file:line`

```language
// The specific code that fails
```

## Chain of Failure

1. **Entry:** {how the action starts}
2. **Step 2:** {what happens next}
3. **Step 3:** {where it breaks}

## Why It Fails

{Technical explanation — what the code does vs what it should do}

## Proof

- {Evidence 1}
- {Evidence 2}

## Related Issues

- {Issue 1 found during investigation}
- {Issue 2 found during investigation}

## Recommendations

- {Fix 1 with exact code change}
- {Fix 2 with exact code change}
```

## Investigation Patterns

| Pattern | Signal | Key Files |
|---------|--------|-----------|
| Silent failure | "clicked X, nothing happened" | error handlers, try/catch |
| Wrong data | "shows 0 but data exists" | API routes, data transforms |
| Session lost | "logged out on refresh" | auth store, session handling |
| N+1 query | slow page load | data fetching, ORM queries |
| Race condition | intermittent failure | async operations, state init |
| Type mismatch | runtime error | API contracts, form schemas |

## Subagent Prompt Template

```
You are a review subagent. Today is {DATE}.

Investigation context: {ISSUE_DESCRIPTION}

Your ONLY task — investigate this single angle:
{ANGLE}

Rules:
1. Read the specific files: {FILE_LIST}
2. Trace the data flow from entry to failure point
3. Document: exact file:line, specific code, technical explanation
4. Do NOT fix anything — only document findings
5. Write findings to {WORKSPACE}/findings/F{N}.md

Return: 3-5 line summary with exact failure point.
```

## ATLAS-native

The audit ledger is the primary forensic source. Multi-layer symptoms: find which layer record is first corrupted. Investigation subagents can run as durable actors. Related to gsd/debug: ultrareview is parallel investigation; gsd/debug is single-agent root cause.
