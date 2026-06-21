# Loop Engineering Synthesis — Wiring ATLAS to Its Full Potential

**Date:** 2026-06-19
**Sources:** ATLAS runtime analysis, L2-CONTEXT-LOOP-ENGINEERING framework, SOTA research (15+ systems), GSD skill patterns
**Status:** Research complete, awaiting operator decision

---

## The Problem

Three systems exist that need each other:

1. **ATLAS Runtime** — the execution engine. Runs agents, emits audits, transitions states. But doesn't verify, hand off, reduce entropy, or enforce stop conditions.

2. **L2-CONTEXT-LOOP-ENGINEERING** — the discipline. Defines how loops should be designed, verified, handed off, and stopped. But has no executor, no persistence, no API.

3. **The Vision** — graph memory, RAG integration, living knowledge. Specs exist. Implementation doesn't.

None of them are wired to each other. The command center (WP-0 through WP-3) built the plumbing but not the connections. The loop engineering patterns exist as markdown but not as code. The graph is a visualization, not a memory system.

The goal: wire them into one coherent system where ATLAS executes, the framework disciplines, and the graph remembers.

---

## What the SOTA Says

The 2026 agentic landscape has converged on a few patterns that work:

**File-based configuration is the standard.** Claude Code (CLAUDE.md), Codex (AGENTS.md), OpenHands, SWE-agent all use hierarchical markdown files for agent instructions. ATLAS's AGENTS.md + CLAUDE.md already fits this pattern.

**Verification is the defining innovation.** Claude Code's stop hooks, Codex's test iteration, Devin's computer use — the best systems treat verification as a hard gate, not optional polish. ATLAS has tests but no post-execution verification gate.

**Fresh-context review is the most reliable quality gate.** Claude Code's writer/reviewer pattern: one agent writes, another reviews in clean context. The reviewer isn't biased by the implementation reasoning. ATLAS has no review step.

**Handoff is checkpoint-based.** Claude Code's `/continue`, `/resume`, checkpoints before every change. Devin's PR-based handoff. ATLAS has checkpoint.md but it's not structured per any protocol.

**Knowledge graphs remain an unexploited opportunity.** No major coding agent uses graph databases for code context. Aider's RepoMap is the closest. ATLAS's Graphify vision — if built — would be ahead of the SOTA.

**"Model UX" is a new evaluation axis.** Cognition (Devin) identified that RL-trained agents overthink and excessively self-verify. The balance between thoroughness and speed matters. ATLAS should track this.

---

## The 7-Layer Wiring Plan

### Layer 1: Handoff Protocol (P0)

**What:** Every run completion writes a structured HANDOFF.md encoding continuation state.

**Why:** Without this, every new run starts from scratch. The compounding loop (WP-5) can't work. The operator's context is lost between sessions.

**How:**

New file: `services/agent-runtime/atlas_runtime/handoff_service.py`

```
write_handoff(project_path, focus, mission, run, audit_events) -> Path
read_handoff(project_path) -> dict | None
```

Follows the L2-CONTEXT-LOOP-ENGINEERING protocol (10 sections):
1. Executive state (mission status, run outcome)
2. Current objective (from Focus)
3. What changed (files modified, created, deleted)
4. Verification evidence (tests run, build status, lint results)
5. Decisions made (from audit events)
6. Known risks (from RunOutcome if available)
7. Do not repeat (failed approaches from prior runs)
8. Next actions (derived from Focus.priorities + run outcome)
9. Files to inspect first (modified files + neighboring files)
10. Acceptance criteria (from Mission.intent)

**Where it wires in:**
- `run_executor.py` line ~45: after `complete_run()`, call `handoff_service.write_handoff()`
- `context_service.py`: when assembling context, check for `HANDOFF.md` in project cwd and include it
- This is the bridge between ATLAS execution and L2-CONTEXT-LOOP-ENGINEERING discipline

**Effort:** 1-2 days

---

### Layer 2: Stop Conditions (P0)

**What:** The executor evaluates safety conditions before and during agent execution.

**Why:** Right now the only stop is cancellation. A long-running agent can hang forever. A prompt with embedded credentials passes straight through. An agent can silently expand scope beyond the Focus.

**How:**

Modify: `services/agent-runtime/atlas_runtime/run_executor.py`

Add pre-execution checks:
- **Secret stop:** scan prompt with `SECRET_PATTERNS` before passing to agent. If match found, fail the run immediately with a clear message.
- **Scope-expansion stop:** compare the mission intent against Focus boundaries. If the intent mentions systems/files outside the project workspace, warn and log.
- **Max-runtime watchdog:** `threading.Timer` that checks elapsed time. If run exceeds threshold (configurable, default 30min), set a flag. The executor checks this flag after each agent step and fails the run with a clear timeout message.

Add post-execution checks:
- **Done stop:** verify the agent's terminal state is consistent (succeeded + no error audit events, or failed + failure audit event).
- **Dirty-state stop:** if the agent modified files, check git status. If unrelated files were modified, log a warning in the handoff.

**Where it wires in:**
- `run_executor.py`: add `_check_stop_conditions()` before `agent.execute()` and `_check_post_conditions()` after
- `RunOutcome`: add `stop_reason: str | None` field

**Effort:** 1-2 days

---

### Layer 3: Claim Taxonomy (P0)

**What:** Every run outcome classifies its claims as evidence, inference, uncertainty, or not-run.

**Why:** Without this, "tests passed" is an assertion, not evidence. The operator can't tell what was actually verified vs what the agent believes. The L2 framework requires this classification.

**How:**

Modify: `packages/atlas-core/atlas_core/schemas/core.py`

Extend `RunOutcome`:
```python
class RunOutcome(BaseModel, frozen=True):
    status: Literal["succeeded", "failed"]
    summary: str
    evidence: list[str] = []        # commands run, outputs captured
    inferences: list[str] = []      # deduced from evidence
    uncertainties: list[str] = []   # could not verify
    stop_reason: str | None = None  # if stopped by a condition
```

Modify: `services/agent-runtime/atlas_runtime/run_executor.py`

After agent execution, classify the outcome:
- If the agent ran tests and they passed → evidence
- If the agent claims something without running a check → inference
- If the agent couldn't verify something → uncertainty
- If the agent skipped a verification step → not-run

**Where it wires in:**
- `core.py`: extend RunOutcome
- `run_executor.py`: populate fields after agent execution
- `handoff_service.py`: use claim classification in HANDOFF.md verification section
- `context_service.py`: surface uncertainties in the next run's context

**Effort:** 1 day

---

### Layer 4: Deep Context Assembly (P1)

**What:** Extend `assemble_context()` to query multiple memory layers, not just Focus + Project + Runs.

**Why:** The current brief is shallow. The agent doesn't see wiki pages, audit history beyond the mission, skill recommendations, or handoff state from prior sessions. A deeper brief produces better agent decisions.

**How:**

Modify: `services/agent-runtime/atlas_runtime/context_service.py`

Add layers (each optional, gated on availability):

| Layer | Source | What it adds |
|-------|--------|-------------|
| Handoff | `HANDOFF.md` in project cwd | Prior session state, what to avoid, next actions |
| Wiki | `atlas_wiki` (try/except import) | Relevant wiki pages for the mission topic |
| Audit | `audit_events` across missions | Historical patterns, common failures |
| Skills | Focus.framework matched to skill registry | Recommended skills for the task type |
| Graph | `graph_engine` (future) | Related entities, provenance chains |

The brief structure becomes:
```
# ATLAS Operator Context

## Current Focus
{focus.title} — {focus.framework}
Priorities: {focus.priorities}
Drivers: {focus.drivers}

## Prior Session State
{handoff executive state + do not repeat + next actions}

## Project
{project.name} at {project.root_path}

## Recent Runs
{last 5 runs with status + claim classification}

## Relevant Knowledge
{wiki pages matched to focus topic}

## Historical Patterns
{audit event patterns — common failures, repeated approaches}

## Recommended Skills
{skills matching focus.framework}
```

**Where it wires in:**
- `context_service.py`: extend `assemble_context()` with new layers
- Each layer is a try/except import — graceful degradation when optional deps missing
- Provenance tracking extends to all layers (`AgentContext.sources`)

**Effort:** 2-3 days

---

### Layer 5: Entropy Reduction (P1)

**What:** After each phase completion or N runs, trigger an entropy scan and produce a report.

**Why:** Without this, code/docs/product drag accumulates. Dead code, duplicate logic, contract drift, temporary scaffolding — all grow unchecked. The L2 framework defines 8 entropy classes.

**How:**

New file: `services/agent-runtime/atlas_runtime/entropy_service.py`

```
scan_entropy(project_path) -> EntropyReport
write_report(report, output_path) -> Path
```

The scan:
1. Run `git diff --stat` to see what changed since last scan
2. Check for unreferenced imports, unused functions (static analysis)
3. Check for files with TODO/FIXME/HACK markers older than 7 days
4. Check for test files without corresponding source files
5. Check for source files without corresponding test files
6. Check for documentation that references moved/deleted files
7. Classify findings into the 8 L2 entropy classes
8. Produce a report at `.planning/reports/entropy-scan-YYYY-MM-DD.md`

**Where it wires in:**
- `run_executor.py`: after N successful runs (configurable, default 10), enqueue an entropy scan
- The entropy report is included in the next context assembly as a "recent entropy" section
- The operator can trigger manually via `atlas entropy scan`

**Effort:** 2-3 days

---

### Layer 6: Graph Engine Integration (P2)

**What:** Wire the graph engine (when built) into the audit event pipeline.

**Why:** The graph should update incrementally as the system operates. Every audit event is a signal about entity relationships. Without this wiring, the graph is a static snapshot, not a living system.

**How:**

Modify: `services/agent-runtime/atlas_runtime/audit_service.py`

After `conn.commit()` in `emit()`:
```python
if _graph_engine is not None:
    try:
        _graph_engine.on_audit_event(event)
    except Exception:
        pass  # graph mutation failure never crashes audit
```

Modify: `.planning/phases/10.0.3-graphify-living-graph/SPEC.md`

Add node types:
- `handoff` — HANDOFF.md documents (session continuation state)
- `skill` — registered skills (from skill inventory)
- `entropy_report` — entropy scan results

Add edge types:
- `handoff_of` — HANDOFF.md belongs to a run
- `skill_applied` — skill used in a run
- `entropy_of` — entropy report scoped to a phase/run

**Where it wires in:**
- `audit_service.py`: thin hook after commit
- `graph_engine.py`: `on_audit_event()` method creates/updates nodes
- The graph becomes a live operational map, not just a file visualization

**Effort:** 1 day (hook) + WP-1 through WP-4 from the graph phase plan

---

### Layer 7: Loop Spec → Mission Mapping (P2)

**What:** L2 loop specs become executable as ATLAS missions.

**Why:** The framework defines how loops should work. ATLAS has the engine to run them. But there's no bridge — a loop spec in the L2 repo doesn't translate to an ATLAS mission automatically.

**How:**

New CLI command: `atlas loop run <spec_path>`

Reads a loop spec file (markdown with YAML frontmatter), extracts:
- Purpose → Mission.intent
- Context loader → Focus.framework
- Verification → post-execution checks
- Stop conditions → pre-execution checks
- Output → expected artifacts

Creates a Mission + Focus, assembles context, and executes through the standard executor path.

Modify: `L2-CONTEXT-LOOP-ENGINEERING/patterns/l2-production-loop-contract.md`

Add mapping table:
| Loop Section | ATLAS Implementation |
|-------------|---------------------|
| Purpose | Mission.intent |
| Trigger | CLI command or daemon endpoint |
| Context loader | context_service.assemble_context() |
| Allowed actions | AgentRuntime.execute() within workspace boundary |
| Forbidden actions | policy.py workspace boundary + tool allowlist |
| Verification | Post-execution claim classification + stop conditions |
| Output | RunOutcome + HANDOFF.md |
| Handoff | handoff_service.write_handoff() |
| Entropy | entropy_service.scan_entropy() |
| Idempotency | start_run guards, cancellation idempotency |
| Stop conditions | run_executor._check_stop_conditions() |
| Autonomy defaults | Configurable per Focus.framework |

**Effort:** 1-2 days

---

## Implementation Order

| Priority | Layer | Depends On | Effort | Impact |
|----------|-------|-----------|--------|--------|
| **P0** | Layer 1: Handoff | None | 1-2 days | Enables compounding loop, cross-session continuity |
| **P0** | Layer 2: Stop Conditions | None | 1-2 days | Safety gate, prevents hangs and scope creep |
| **P0** | Layer 3: Claim Taxonomy | None | 1 day | Evidence discipline, operator trust |
| **P1** | Layer 4: Deep Context | Layer 1 (handoff reads) | 2-3 days | Better agent decisions, richer briefs |
| **P1** | Layer 5: Entropy Reduction | Layer 3 (claim tracking) | 2-3 days | Prevents code/docs/product drag |
| **P2** | Layer 6: Graph Integration | WP-1 from graph phase | 1 day + graph work | Living operational map |
| **P2** | Layer 7: Loop Spec Mapping | Layers 1-3 | 1-2 days | Framework becomes executable |

**Total P0:** 3-5 days (handoff + stops + claims)
**Total P1:** 4-6 days (deep context + entropy)
**Total P2:** 2-3 days (graph hook + loop mapping)

---

## What This Unlocks

### Immediate (After P0)
- Runs produce HANDOFF.md → next run inherits context
- Stop conditions prevent hangs, credential leaks, scope creep
- RunOutcome has evidence classification → operator trusts the system
- The command center dashboard can show claim classifications and stop reasons

### Short-term (After P1)
- Context assembly pulls from 6 memory layers → agents make better decisions
- Entropy scans prevent accumulation → codebase stays clean
- The compounding loop (WP-5) works: run outcome → handoff → next context → better run

### Medium-term (After P2)
- Graph updates on every audit event → living operational map
- Loop specs become executable missions → the framework is no longer just documentation
- ATLAS is ahead of the SOTA: graph-based agent context + loop engineering discipline + audit-first execution

---

## SOTA Comparison (After Wiring)

| Capability | Claude Code | Codex | Devin | ATLAS (after wiring) |
|------------|------------|-------|-------|---------------------|
| Execution engine | Built-in | Cloud sandbox | Linux desktop | Python + Rust gateway |
| Context loading | CLAUDE.md | AGENTS.md | Session memory | 6-layer memory router |
| Verification | Stop hooks + goal conditions | Test iteration | Computer use | Claim taxonomy + stop conditions + entropy |
| Handoff | Checkpoints + /continue | PR-based | PR + recordings | HANDOFF.md (10-section protocol) |
| Knowledge graph | None | None | None | Graphify (living, SQLite-backed) |
| Audit trail | None (session only) | Citations | Screen recordings | AuditEvent bus + JSONL export |
| Entropy reduction | None | None | None | 8-class entropy scan |
| Loop engineering | Implicit (good patterns) | Implicit | Implicit | Explicit (production loop contract) |
| Idempotency | Checkpoint-based | Task isolation | PR-based | Atomic transitions + cancellation semantics |
| Safety | Auto mode classifier + sandbox | Container isolation + malware refusal | Sandboxed desktop | Workspace boundary + tool allowlist + secret redaction + stop conditions |

ATLAS would be the only system with all of these integrated. The SOTA has pieces; ATLAS would have the whole.

---

## Open Questions for the Operator

1. **P0 scope:** Should handoff, stop conditions, and claim taxonomy be built as part of the command center (WP-5 compounding loop), or as a separate phase?

2. **Entropy cadence:** How often should entropy scans run? Every N runs? On phase completion? On operator trigger only?

3. **Max runtime default:** What's the right timeout for agent execution? 15min? 30min? 60min? Should it be configurable per Focus?

4. **Graph integration timing:** Should the graph hook (Layer 6) be built now (when the graph engine doesn't exist yet), or deferred until WP-1 of the graph phase plan is done?

5. **Loop spec format:** Should L2 loop specs use the existing markdown format, or should ATLAS define a machine-readable format (YAML frontmatter + markdown body)?

6. **Deep context priority:** Which memory layer should be wired first? Handoff (most impactful for continuity) or Wiki (most impactful for knowledge)?
