# ATLAS Ultra — Execute

## Pipeline

```
1. SCOPE → 2. PLAN → 3. WAVE DECOMPOSE → 4. PARALLEL EXECUTE → 5. VERIFY → 6. COMMIT → 7. ARTIFACT
```

### Step 1: SCOPE (inline, 5 min)
- What is being built? (feature, fix, refactor)
- What are the constraints? (time, dependencies, breaking changes)
- What exists already? (read relevant files)

### Step 2: PLAN (inline, 10 min)
- Decompose into atomic units of work
- Each unit: one file or one logical change
- Order: dependencies first, independent units in parallel
- Identify verification criteria for each unit

### Step 3: WAVE DECOMPOSE (inline, 5 min)
Group work units into waves:
- **Wave 1**: Foundation (types, interfaces, schemas) — must complete first
- **Wave 2**: Core logic (implementations) — can parallelize within wave
- **Wave 3**: Integration (wiring, API routes, UI) — depends on Wave 2
- **Wave 4**: Polish (tests, docs, cleanup) — depends on Wave 3

### Step 4: PARALLEL EXECUTE (subagents or inline)
For each wave:
- If work units are independent: spawn subagents (one per unit)
- If work units are dependent: execute sequentially inline
- Each subagent: reads files, makes changes, writes results
- **Never** let subagents modify files that other subagents are modifying in the same wave

### Step 5: VERIFY (inline, 10 min)
- Run tests (if test suite exists)
- Run type checker (tsc, mypy, etc.)
- Run linter (eslint, ruff, etc.)
- Manual verification: does the feature work?
- Check for regressions in related areas

### Step 6: COMMIT (inline, 5 min)
- Stage relevant files
- Write conventional commit message: `type(scope): description`
- Types: feat, fix, refactor, test, docs, chore
- One logical change per commit

### Step 7: ARTIFACT (inline, 5 min)
- Save execution log to `{ARTIFACT_DIR}/ATLAS-ULTRA-EXECUTE-{slug}.md` (resolved per SKILL.md Saving Results)

## Output Template

```markdown
# {Feature} — Execution Log

## Goal
{What was built}

## Waves Executed

### Wave 1: {Name}
- Unit 1: {description} — done
- Unit 2: {description} — done

### Wave 2: {Name}
- Unit 3: {description} — done
- Unit 4: {description} — done

## Verification
- [ ] Tests pass
- [ ] Type check passes
- [ ] Lint passes
- [ ] Manual verification: {what was checked}

## Commits
- `{commit_hash}`: `{commit_message}`

## Files Changed
- `{file1}`: {what changed}
- `{file2}`: {what changed}
```

## Subagent Prompt (for parallel execution)

```
You are an execution subagent.

Your ONLY task — implement this specific change:
{CHANGE_DESCRIPTION}

Rules:
1. Read the relevant files first: {FILE_LIST}
2. Make ONLY the specified change — nothing else
3. Follow existing code patterns and conventions
4. Write changes to the specified files
5. Return: 3-5 line summary of what was changed

Do NOT:
- Refactor unrelated code
- Add features not requested
- Change files not specified
- Skip verification
```

## ATLAS-native

Wave 1 tasks marked `[actor-ok]` can run as durable actors. Every commit cites the audit run id. The execution log feeds into gsd/ship.md. If running as a mission, the mission judge enforces verification.
