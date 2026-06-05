---
phase: 01-hermes-foundation-audit
requirement: FOUND-04
donor_repo: C:/Users/Davi/Desktop/Projects/L2-Atlas
donor_path: src/atlas_core/
audit_date: 2026-06-05
schema_target: SCHEMA-01 (Phase 2 Pydantic v2)
---

# L2-Atlas Module Extraction Plan

Audit of 6 `atlas_core` donor modules from `C:/Users/Davi/Desktop/Projects/L2-Atlas/src/atlas_core/`.
Read-only audit — donor repo unmodified.

---

## Classification Table

| Module | File Size | Classification | Reasoning |
|--------|-----------|----------------|-----------|
| `mission_control/parser.py` | ~5 KB | **port** | Data-carrying; links to SCHEMA-01 |
| `execution/policy.py` | ~4 KB | **port** | Core safety boundary; no Hermes equivalent |
| `execution/powershell.py` | ~5 KB | **port** | Windows-primary executor; no Hermes equivalent |
| `logging/jsonl_logger.py` | ~2 KB | **port** | Data-carrying; redaction patterns critical |
| `runtime/orchestrator.py` | ~10 KB | **reference** | High coupling; will be rewritten for Hermes integration |
| `skills/registry.py` | ~1.5 KB | **port** | Standalone; no Hermes skills equivalent |

---

## Module-by-Module Analysis

### 1. `mission_control/parser.py` — PORT

**Purpose:** Parses Markdown Mission Control files into `MissionBoard` / `Mission` / `MissionStep` models.

**Imports:**
- stdlib: `hashlib`, `re`, `pathlib`
- local: `atlas_core.mission_control.task_model` (Mission, MissionBoard, MissionDiagnostic, MissionStep, KANBAN_SECTIONS)

**Hermes overlap:** None. Hermes `hermes_cli/_parser.py` is a CLI argument parser — different domain.

**Windows coupling:** None — pure text processing.

**Data-carrying:** YES — parses into structured Pydantic-like models. Phase 2 SCHEMA-01 target fields:
- `Mission.id` → `Task.id`
- `Mission.project` → `Task.project_id`
- `MissionBoard.missions` → Task collection in Run schema

**Phase 2 action:** Port `MissionBoard`, `Mission`, `MissionStep` models to Pydantic v2 (`model_config = ConfigDict(frozen=True)`). Redact no secret content. Replace `task_model.py` dataclass imports with Pydantic v2 models in SCHEMA-01.

---

### 2. `execution/policy.py` — PORT

**Purpose:** Workspace and command policy gates — `WorkspacePolicy` validates path containment; `CommandPolicyEngine` evaluates `CommandRequest` → `PolicyDecision`.

**Imports:**
- stdlib: `re`, `dataclasses`, `pathlib`
- local: `atlas_core.runtime.models.CommandRequest`

**Hermes overlap:** Hermes has `tools/approval.py` (62.5 KB) for tool approval UX. Conceptually related but different scope: `policy.py` enforces workspace path containment and command blocklist; approval.py manages interactive approval flows for dangerous commands. No functional duplication.

**Windows coupling:** Mild — `WorkspacePolicy.validate_request` uses `Path` objects; Windows path semantics apply. Functional on both platforms.

**Data-carrying:** YES — `PolicyDecision(allowed, requires_approval, reason)` → links to Phase 2 `ExecutionEvent` schema fields (`policy_result`, `requires_approval`).

**Phase 2 action:** Port `WorkspacePolicy` and `CommandPolicyEngine` to packages/atlas-core. Replace `CommandRequest` import with SCHEMA-01 Pydantic v2 model. Add `from __future__ import annotations`.

---

### 3. `execution/powershell.py` — PORT

**Purpose:** Windows-specific execution boundary — `PowerShellExecutor` wraps subprocess calls with policy check + JSONL evidence logging.

**Imports:**
- stdlib: `subprocess`, `time`, `pathlib`, `typing`, `collections.abc`
- local: `atlas_core.execution.policy.CommandPolicyEngine`, `atlas_core.logging.jsonl_logger.JsonlLogger`, `atlas_core.runtime.models.CommandRequest, CommandResult`

**Hermes overlap:** None. Hermes shell execution is cross-platform via `tools/approval.py` + subprocess. `PowerShellExecutor` is explicitly Windows + PowerShell — ATLAS-only concern.

**Windows coupling:** HIGH — constructor references PowerShell binary; `subprocess.run` invokes PowerShell. This module is intentionally Windows-only for L2-ATLAS-PROJECT.

**Data-carrying:** YES — `CommandResult` carries `stdout`, `stderr`, `exit_code`, `elapsed_ms` → Phase 2 `ExecutionEvent.result` schema fields.

**Phase 2 action:** Port to packages/atlas-core. Replace local imports with SCHEMA-01 Pydantic v2 models for `CommandRequest`/`CommandResult`. Add Windows CI guard to test matrix.

---

### 4. `logging/jsonl_logger.py` — PORT

**Purpose:** Append-only JSONL logger with conservative secret redaction. Two `SECRET_PATTERNS` regex patterns.

**Imports:**
- stdlib only: `json`, `re`, `datetime`, `pathlib`, `typing`, `collections.abc`

**Hermes overlap:** None. Hermes `hermes_state.py` is a full SQLite session DB. `jsonl_logger.py` is a lightweight append-only file logger — complementary, not overlapping.

**Windows coupling:** None — pure stdlib IO.

**Data-carrying:** YES — redaction patterns are audit infrastructure critical to T-1-10 (secret leakage):
```python
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(token|api[_-]?key|secret|password)=([^\s&]+)"),
    re.compile(r"(?i)\b(bearer)\s+([A-Za-z0-9._~+/=-]+)"),
)
```
These patterns MUST be preserved verbatim in the port. Phase 2 SCHEMA-01 `AuditEvent.data` field passes through `JsonlLogger._redact()` before persistence.

**Phase 2 action:** Port to packages/atlas-core unchanged. Expose `SECRET_PATTERNS` as a module-level constant. Add tests for both redaction patterns. Link to Phase 2 `AuditEvent` schema via `JsonlLogger.write(event="audit_event", data=audit_event.model_dump())`.

---

### 5. `runtime/orchestrator.py` — REFERENCE

**Purpose:** `AtlasOrchestrator` — assembles all atlas_core components into a runtime: config → policy → executor → logger → parser → skills.

**Imports:**
- stdlib: `shutil`, `sys`, `pathlib`, `typing`
- local (ALL of atlas_core): `config.AtlasConfig`, `execution.policy.*`, `execution.powershell.*`, `logging.jsonl_logger.JsonlLogger`, `mission_control.parser.*`, `runtime.models.*`, `skills.registry.SkillRegistry`

**Hermes overlap:** HIGH conceptually — Hermes `agent/agent_init.py` + `agent/agent_runtime_helpers.py` + `run_agent.py` serve the equivalent "runtime orchestrator" role, but via async Python with LLM loop management, tool dispatch, and session management at ~400 KB total.

**Windows coupling:** Indirect — delegates to `PowerShellExecutor` for execution.

**Reason for REFERENCE (not port):** The orchestrator is the integration seam — it wires components together. For L2-ATLAS-PROJECT, the integration seam changes entirely: Hermes plugin hooks replace the direct orchestration pattern. The new orchestrator will listen to `on_session_start`, `pre_tool_call`, `post_tool_call` from Hermes plugins and dispatch ATLAS logic reactively. Porting the imperative `plan_task` / `run_task` loop would produce dead code.

**Phase 2 action:** Use as architectural reference for understanding the ATLAS execution model (`plan → approve → execute → log`). Do NOT copy code. Design the Phase 4 ATLAS plugin with this flow in mind, adapted to the Hermes hook event model.

---

### 6. `skills/registry.py` — PORT

**Purpose:** In-memory `SkillRegistry` — discovers skill manifests from `*/manifest.json` files in a skills root directory; provides `list()`, `get()`, `describe()`, `summaries()`.

**Imports:**
- stdlib: `pathlib`
- local: `atlas_core.skills.manifest.SkillManifest`

**Hermes overlap:** Hermes has `skills_hub.py` (66.3 KB) — a full Hermes-native skills management system with marketplace, enable/disable, discovery, and config. ATLAS `SkillRegistry` serves a different purpose: discovering ATLAS-specific skills (manifest.json format) that are not Hermes skills. No functional overlap.

**Windows coupling:** None — `pathlib.Path.glob()` is cross-platform.

**Data-carrying:** Light — `SkillManifest` is the schema type. Phase 2 SCHEMA-01: `SkillManifest` → Pydantic v2 model with `name: str`, `version: str`, `description: str`.

**Phase 2 action:** Port `SkillRegistry` and `SkillManifest` to packages/atlas-core. Convert `SkillManifest` to Pydantic v2 model. Wire ATLAS skills discovery to use the Hermes profile skills directory or ATLAS-owned skills path.

---

## Phase 2 Schema Linkage (SCHEMA-01)

| Donor Model | Phase 2 Pydantic v2 Target | Key Fields |
|-------------|---------------------------|------------|
| `Mission` (parser.py) | `Task` | `id`, `project_id`, `status`, `steps` |
| `MissionStep` (parser.py) | `TaskStep` | `id`, `body`, `checked` |
| `PolicyDecision` (policy.py) | embedded in `ExecutionEvent` | `allowed`, `requires_approval`, `reason` |
| `CommandRequest` (models.py) | `CommandRequest` | `command`, `working_dir` |
| `CommandResult` (models.py) | `CommandResult` / `ExecutionEvent.result` | `stdout`, `stderr`, `exit_code`, `elapsed_ms` |
| `AuditEvent` (jsonl_logger.py writes) | `AuditEvent` | `timestamp`, `event`, `data` (redacted) |
| `SkillManifest` (skills/registry.py) | `SkillManifest` | `name`, `version`, `description` |

All models use `model_config = ConfigDict(frozen=True)` per D-012 (Pydantic v2, source of truth).

---

## Donor Repo Integrity Verification

Baseline `git status --short` before audit:
```
?? ATLAS_TERMINAL_AGENT_CODING_BRIEF.md
```

Post-audit `git status --short` (must match):
```
?? ATLAS_TERMINAL_AGENT_CODING_BRIEF.md
```

No tracked or staged changes introduced. L2-Atlas source tree unmodified.
