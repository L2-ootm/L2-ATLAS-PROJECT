# L2 ATLAS — Implementation Start Plan

> **For agentic workers:** This is a foundation/audit phase, not a product-feature phase. Tasks produce **decision records, audit documents, and schema artifacts** with explicit verification gates — they are not red/green TDD feature tasks. Do NOT write product features until Task 10's gate passes. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert locked research/decisions into a build-ready foundation: pin Hermes, audit its extension points and L2-Atlas donor modules, lock canonical repo layout + schema language, and draft the core domain + SQLite schemas — so the first MVP loop (mission → enhanced runtime → audit → artifact → wiki → cockpit) can be implemented on solid ground.

**Architecture:** ATLAS is an enhanced **Hermes** (Python) runtime with an audit-first event model, a SQLite/WAL/FTS5/sqlite-vec datastore, a first-class LLM Wiki, a WebUI cockpit (framework TBD), and a later Rust-native sidecar. This plan does not build those surfaces; it produces the contracts and audits they depend on.

**Tech Stack:** Python 3.11+ (Hermes foundation + atlas-core), Pydantic v2 (schema source of truth), SQLite (datastore), Markdown (LLM Wiki), Git (vendoring/pinning). WebUI and native stacks remain open pending spikes.

---

## Context Snapshot (verified 2026-06-04)

| Fact | Value | Source of truth |
|---|---|---|
| Repo HEAD | `782062d` (clean working tree) | `git status` / `git log` |
| Hermes upstream | `https://github.com/NousResearch/hermes-agent.git` | `git remote -v` in local install |
| Hermes license | **MIT** (safe to vendor/fork) | `LICENSE` in install |
| Hermes version | `0.14.0`, tag `v2026.5.16-1302-ge8b9369a9` | `pyproject.toml`, `git describe` |
| Hermes pinned SHA | `e8b9369a9d2df36139a5055cae3ed3c15691e03e` | `git rev-parse HEAD` |
| Hermes local install | `<USER_HOME>\AppData\Local\hermes\hermes-agent` | filesystem |
| Hermes shape | Python-primary, **monolithic** (`cli.py` 685KB, `run_agent.py` 202KB, `hermes_state.py` 142KB) | filesystem |
| L2-Atlas core | `<USER_HOME>\Desktop\Projects\L2-Atlas\src\atlas_core` (Python 3.11, deps: prompt_toolkit, rich) | `pyproject.toml`, dir listing |

### atlas_core donor modules (confirmed present)

```
atlas_core/
├── cli.py, config.py
├── mission_control/   parser.py, task_model.py, paths.py, writer.py
├── execution/         policy.py, powershell.py, result.py
├── logging/           jsonl_logger.py
├── runtime/           orchestrator.py, models.py, heartbeat.py, mission_control_loop.py
├── ai/  shell/  skills/  testing/  ui_cli/
```

---

## Contradictions / Risks Found (must be resolved by this plan)

These are real inconsistencies across the committed docs. Each maps to a task below.

- **C1 — Repo layout conflict (3 incompatible layouts).**
  - `RESEARCH_SYNTHESIS.md` proposes a **flat** layout (`atlas-core/`, `atlas-runtime/`, `atlas-knowledge/`, `atlas-pulse/`, `atlas-native/`, `atlas-web/`, `atlas-skills/`).
  - `FOUNDATION_STRATEGY.md` proposes `foundation/hermes-agent/`, `atlas/`, `apps/web/`, `packages/atlas-core/`, `services/wiki-runtime/`, `services/pulse-runtime/`.
  - `SYSTEM_OVERVIEW.md` proposes `apps/web`, `apps/api`, `services/agent-runtime`, `services/wiki-runtime`, `packages/atlas-core`.
  - **Resolution:** Task 5 ratifies one canonical layout (proposed decision **D-011**).

- **C2 — Schema language ambiguity.** `NEXT_ACTION_PLAN.md` step 4 targets `packages/atlas-core/src/schemas/` (a JS/TS-monorepo idiom), but the entire runtime (Hermes + L2-Atlas) is Python. Shipping TS schemas as the source of truth for a Python runtime creates a dual-maintenance trap.
  - **Resolution:** Task 5 proposes **Pydantic v2 as the single source of truth**, emitting JSON Schema for TS (web) and Rust (native) consumers (proposed decision **D-012**).

- **C3 — WebUI presupposition.** `NATIVE_APP_STRATEGY.md` table lists WebUI stack as "Next.js or similarly excellent web stack," but `DECISION_REGISTER.md` D-006 keeps the WebUI framework **open** (SvelteKit vs Next.js). Doc inconsistency.
  - **Resolution:** Task 8 spike is the authority; Task 10 patches `NATIVE_APP_STRATEGY.md` to say "TBD pending D-006 spike."

- **R1 — Hermes is monolithic.** `cli.py` is 685KB and `run_agent.py` 202KB. "Enhance Hermes directly" (D-001) against files this large carries high merge/upstream-drift cost. **Mitigation:** the divergence policy must default to **plugin/tool/hook surfaces first**, with in-core edits treated as last resort and each one recorded as a divergence decision. Captured as a new risk; reinforced in Task 3's audit objective.

- **R2 — Secrets in the local Hermes install.** `AppData\Local\hermes\hermes-agent` contains `auth.json`, `.env` (23KB), `state.db` (73MB), and session DBs. Vendoring that directory would import secrets and personal data, violating the non-negotiables. **Mitigation:** Task 2 clones **fresh from upstream at the pinned SHA**, never copies the install. Verified by a secret-scan gate.

---

## File / Artifact Map

This phase creates **documents and schema drafts only**. No service code.

| Path | Responsibility | Created by |
|---|---|---|
| `docs/decisions/2026-06-04_D011_repo_layout.md` | Canonical monorepo layout decision | Task 5 |
| `docs/decisions/2026-06-04_D012_schema_source_of_truth.md` | Pydantic-first schema decision | Task 5 |
| `docs/foundation/HERMES_FOUNDATION_PIN.md` | Hermes pin record (upstream, SHA, license, vendoring method) | Task 1 |
| `_EXTERNAL_REPOS/hermes-agent/` (outside project repo) | Clean upstream clone at pinned SHA for inspection | Task 2 |
| `docs/research/HERMES_FOUNDATION_AUDIT.md` | Extension-point audit vs report 01 | Task 3 |
| `docs/imports/L2_ATLAS_MODULE_EXTRACTION_PLAN.md` | Per-module port/rewrite/reference/discard map | Task 4 |
| `packages/atlas-core/atlas_core/schemas/` | Pydantic v2 domain schemas | Task 6 |
| `infra/migrations/0001_core.sql` | SQLite MVP schema | Task 7 |
| `docs/research/WEBUI_STACK_SPIKE.md` | SvelteKit vs Next.js decision input | Task 8 |
| `docs/research/CRM_PULSE_CHANNELS_DEEP_DIVE.md` | Missing-research brief + intake | Task 9 |
| `.planning/STATE.md`, `.planning/RISKS.md`, `docs/decisions/...` | Phase-close updates | Task 10 |

**Layout note:** This plan adopts (pending D-011 ratification in Task 5) the `apps/` + `services/` + `packages/` + `infra/` layout, because it reconciles two of three docs and cleanly separates the Python runtime (`packages/`, `services/`) from web/native surfaces (`apps/`). Tasks 6–7 write into that layout; if D-011 is rejected, move artifacts before Task 10.

---

## Task 1: Pin the Hermes foundation (record, do not vendor yet)

**Files:**
- Create: `docs/foundation/HERMES_FOUNDATION_PIN.md`

- [ ] **Step 1: Re-verify the pin facts against the live install**

Run:
```bash
cd "<USER_HOME>/AppData/Local/hermes/hermes-agent" && \
  git remote get-url origin && \
  git rev-parse HEAD && \
  git describe --tags && \
  head -1 LICENSE && \
  grep -m1 '^version' pyproject.toml
```
Expected:
```
https://github.com/NousResearch/hermes-agent.git
e8b9369a9d2df36139a5055cae3ed3c15691e03e
v2026.5.16-1302-ge8b9369a9
MIT License
version = "0.14.0"
```
If any value differs, use the live value and note the drift in the pin doc.

- [ ] **Step 2: Write `docs/foundation/HERMES_FOUNDATION_PIN.md`**

Content must include exactly:
```markdown
# Hermes Foundation Pin

- Upstream: https://github.com/NousResearch/hermes-agent.git
- License: MIT (vendoring/forking permitted; retain LICENSE + attribution)
- Version: 0.14.0 (tag v2026.5.16-1302-ge8b9369a9)
- Pinned commit: e8b9369a9d2df36139a5055cae3ed3c15691e03e
- Language: Python-primary; TS/JS confined to TUI/web surfaces
- Shape risk: monolithic core (cli.py ~685KB, run_agent.py ~202KB, hermes_state.py ~142KB)

## Vendoring decision (proposed: external-clone-then-decide)
1. Clone FRESH from upstream at the pinned SHA into `_EXTERNAL_REPOS/hermes-agent`
   (OUTSIDE this project's git tree). DO NOT copy the AppData install — it holds
   secrets (auth.json, .env) and runtime state (state.db).
2. Inspect upstream layout (Task 3) before choosing in-repo vendoring method.
3. Defer the submodule-vs-vendor-vs-fork decision to a follow-up record once the
   extension-point audit shows how much in-core change ATLAS truly needs.

## Divergence policy (binds all future Hermes changes)
Default order of preference: plugin > tool > hook > skill > ATLAS-only override > in-core edit.
Every in-core edit requires a divergence decision record in docs/decisions/.
```

- [ ] **Step 3: Commit**
```bash
git add docs/foundation/HERMES_FOUNDATION_PIN.md
git commit -m "docs: pin Hermes foundation (NousResearch/hermes-agent @ e8b9369, MIT)"
```

**Acceptance:** Pin doc exists with verified SHA/license/version; no clone performed yet; vendoring method explicitly deferred.

---

## Task 2: Clean external clone at pinned SHA (inspection copy)

**Files:**
- Create (outside project tree): `<USER_HOME>/Desktop/Projects/_EXTERNAL_REPOS/hermes-agent/`

- [ ] **Step 1: Create the external repos directory**
```bash
mkdir -p "<USER_HOME>/Desktop/Projects/_EXTERNAL_REPOS"
```

- [ ] **Step 2: Clone fresh from upstream (NOT from AppData) and pin**
```bash
cd "<USER_HOME>/Desktop/Projects/_EXTERNAL_REPOS" && \
  git clone https://github.com/NousResearch/hermes-agent.git && \
  cd hermes-agent && \
  git checkout e8b9369a9d2df36139a5055cae3ed3c15691e03e
```
Expected: detached HEAD at `e8b9369a9`.
If network/auth blocks the clone, STOP and report — do not substitute the AppData copy.

- [ ] **Step 3: Secret-scan gate (must pass before any future vendoring)**
```bash
cd "<USER_HOME>/Desktop/Projects/_EXTERNAL_REPOS/hermes-agent" && \
  ls -a | grep -E '^\.env$|^auth\.json$|state\.db' || echo "CLEAN: no secrets/state in fresh clone"
```
Expected: `CLEAN: no secrets/state in fresh clone` (upstream ships `.env.example`, not `.env`).

- [ ] **Step 4: Confirm the clone is outside the ATLAS git tree**
```bash
cd "<USER_HOME>/Desktop/Projects/L2-ATLAS-PROJECT" && git status --short
```
Expected: empty (no new tracked files from the external clone).

**Acceptance:** Pinned clean clone exists at `_EXTERNAL_REPOS/hermes-agent`; secret-scan reports CLEAN; ATLAS repo unaffected. No `git add` of the clone.

---

## Task 3: Hermes extension-point audit

**Files:**
- Create: `docs/research/HERMES_FOUNDATION_AUDIT.md`
- Read: `_EXTERNAL_REPOS/hermes-agent/` + `docs/research/raw-reports/2026-06-04_01_hermes-foundation-architecture.md`

- [ ] **Step 1: Locate each extension surface in the upstream clone**

Run (record file:line for each hit):
```bash
cd "<USER_HOME>/Desktop/Projects/_EXTERNAL_REPOS/hermes-agent" && \
  ls plugins/ tools/ skills/ providers/ cron/ gateway/ agent/ hermes_cli/ acp_adapter/ && \
  grep -rln "def register" plugins/ tools/ | head -20
```

- [ ] **Step 2: Fill the audit matrix in `HERMES_FOUNDATION_AUDIT.md`**

For each surface, document: location, public API/registration mechanism, how ATLAS extends it (plugin/tool/hook/in-core), and event-capture feasibility. Required rows:

```markdown
| Surface | Upstream location | Extension mechanism | ATLAS approach | Audit-event hookable? |
|---|---|---|---|---|
| Hook system | | | | |
| Tool registry | tools/, toolsets.py | | | |
| Provider routing | providers/ | | | |
| Session/state store | hermes_state.py | | | |
| Delegation/subagents | | | | |
| Cron | cron/ | | | |
| Profiles | | | | |
| Gateway/channels | gateway/, tui_gateway/ | | | |
| MCP | mcp_serve.py, optional-mcps/ | | | |
| Plugin surface | plugins/ | | | |
| CLI/TUI boundary | cli.py, hermes_cli/, ui-tui/ | | | |
```

- [ ] **Step 3: Answer the central question — where does the audit event bus attach?**

Explicitly identify the single best interception point(s) for the audit-first model (D-002): LLM call, tool call, subagent run, approval, artifact, wiki/memory write. State whether this is achievable via hook/plugin (preferred, per R1) or requires in-core edits (and if so, how localized).

- [ ] **Step 4: Record the R1 verdict**

State plainly: can ATLAS's MVP audit loop be built **without** editing `cli.py`/`run_agent.py`? Yes/No + evidence. This decides whether D-001's "enhance directly" is plugin-first or fork-first.

- [ ] **Step 5: Commit**
```bash
git add docs/research/HERMES_FOUNDATION_AUDIT.md
git commit -m "docs: Hermes extension-point + audit-hook audit"
```

**Acceptance:** Every matrix row filled with concrete file:line; audit-bus attachment point identified; R1 verdict stated with evidence.

---

## Task 4: L2-Atlas atlas_core extraction audit

**Files:**
- Create: `docs/imports/L2_ATLAS_MODULE_EXTRACTION_PLAN.md`
- Read: `<USER_HOME>/Desktop/Projects/L2-Atlas/src/atlas_core/` (read-only; never modify L2-Atlas)

- [ ] **Step 1: Read each donor module's interface**

Read (interfaces only, not full files): `mission_control/parser.py`, `mission_control/task_model.py`, `execution/policy.py`, `execution/powershell.py`, `logging/jsonl_logger.py`, `runtime/models.py`, `runtime/heartbeat.py`, `runtime/orchestrator.py`, `skills/registry.py`.

- [ ] **Step 2: Fill the classification table**

Classify each module: `port` (move/adapt), `rewrite` (concept good, code not), `reference` (learn only), `discard`.

```markdown
| Module | Role | Classification | ATLAS destination | Notes / blockers |
|---|---|---|---|---|
| mission_control/parser.py | Markdown mission parsing | | packages/atlas-core | sync rules w/ DB mission model |
| mission_control/task_model.py | Task/state contracts | port? | packages/atlas-core/schemas | reconcile with Pydantic schemas (Task 6) |
| execution/policy.py | WorkspacePolicy/CommandPolicyEngine | | services/agent-runtime/policy | cross-platform abstraction needed |
| execution/powershell.py | PowerShellExecutor | rewrite? | — | Windows-only; must generalize (see consolidation map) |
| logging/jsonl_logger.py | JSONL audit logging | | maps to AuditEvent/RunEvent | feeds Task 6/7 schemas |
| runtime/models.py | TaskInput/ExecutionPlan/Result | | packages/atlas-core/schemas | donor for Run/ToolCall shapes |
| runtime/heartbeat.py | Pulse/heartbeat loop | | services/pulse-runtime (later) | |
| runtime/orchestrator.py | Local runtime core | reference | — | concept donor; Hermes is the real runtime |
| skills/registry.py | Skill manifest/loader | | merge w/ Hermes skills | avoid second skill system (D-008) |
```

- [ ] **Step 3: Cross-link to schema tasks**

For every `port`/`rewrite` module that carries a data contract (task_model, models, jsonl_logger), name the exact Task 6 schema it feeds. This prevents a second, incompatible model from forming.

- [ ] **Step 4: Commit**
```bash
git add docs/imports/L2_ATLAS_MODULE_EXTRACTION_PLAN.md
git commit -m "docs: L2-Atlas atlas_core extraction classification"
```

**Acceptance:** Every module classified with a destination; PowerShell executor flagged as rewrite (cross-platform); data-carrying modules linked to Task 6 schemas. L2-Atlas repo unmodified (`cd L2-Atlas && git status` clean).

---

## Task 5: Lock canonical layout (D-011) and schema source of truth (D-012)

**Files:**
- Create: `docs/decisions/2026-06-04_D011_repo_layout.md`
- Create: `docs/decisions/2026-06-04_D012_schema_source_of_truth.md`

- [ ] **Step 1: Write D-011 — canonical monorepo layout**

Resolve C1. Record the ratified layout:
```markdown
# D-011 — Canonical repo layout
Status: proposed → ratify before Task 6.
Decision: polyglot monorepo
  foundation/        # Hermes vendoring pointer (method TBD per Task 3)
  packages/atlas-core/   # Python: Pydantic schemas, shared contracts, policy types
  services/agent-runtime/  # enhanced Hermes/ATLAS runtime + event bus + audit
  services/wiki-runtime/   # LLM Wiki ingest/query/lint
  services/pulse-runtime/  # later
  apps/api/          # mission/run/source/wiki API
  apps/web/          # cockpit WebUI (framework TBD, D-006)
  infra/migrations/  # SQLite schema
  native/            # Rust sidecar (later)
  wiki/  docs/        # exist
Rationale: separates Python runtime (packages/services) from web/native surfaces (apps/native);
reconciles SYSTEM_OVERVIEW + FOUNDATION_STRATEGY; supersedes the flat layout in RESEARCH_SYNTHESIS.
```

- [ ] **Step 2: Write D-012 — schema source of truth**

Resolve C2:
```markdown
# D-012 — Schema source of truth: Pydantic v2
Status: proposed → ratify before Task 6.
Decision: Pydantic v2 models in packages/atlas-core/atlas_core/schemas/ are the single
source of truth. Emit JSON Schema (model_json_schema()) for TS (web) and Rust (native) consumers.
Rationale: runtime is Python (Hermes + L2-Atlas); TS-first schemas (NEXT_ACTION_PLAN's
packages/.../src/schemas) would create dual maintenance. JSON Schema is the cross-language bridge.
SQLite DDL (Task 7) is generated to match these models, not authored independently.
```

- [ ] **Step 3: Commit**
```bash
git add docs/decisions/2026-06-04_D011_repo_layout.md docs/decisions/2026-06-04_D012_schema_source_of_truth.md
git commit -m "docs: D-011 canonical layout + D-012 Pydantic schema source of truth"
```

**Acceptance:** Both decisions written and self-consistent; Task 6/7 paths now unambiguous.

---

## Task 6: Core domain schemas (Pydantic v2 drafts)

**Files:**
- Create: `packages/atlas-core/atlas_core/schemas/__init__.py`
- Create: `packages/atlas-core/atlas_core/schemas/core.py`
- Create: `packages/atlas-core/pyproject.toml`

> These are **draft contracts**, not wired runtime code. They exist to lock field names/types so the SQLite schema (Task 7) and future services agree. Keep them minimal — enums + IDs + relationships + audit fields. Resist adding fields not in the MVP loop (YAGNI).

- [ ] **Step 1: Write `packages/atlas-core/pyproject.toml`**
```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "atlas-core"
version = "0.0.1"
description = "ATLAS shared domain schemas and contracts."
requires-python = ">=3.11"
dependencies = ["pydantic>=2.6"]

[tool.setuptools.packages.find]
where = ["."]
```

- [ ] **Step 2: Write `packages/atlas-core/atlas_core/schemas/core.py`**

Minimal, audit-first contracts for the MVP loop. Field names here are authoritative for Task 7's DDL.
```python
"""ATLAS core domain schemas (draft v0). Source of truth per D-012."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _id() -> str:
    return uuid4().hex


class MissionStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class RunStatus(str, Enum):
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class EventKind(str, Enum):
    llm_call = "llm_call"
    tool_call = "tool_call"
    subagent_run = "subagent_run"
    approval = "approval"
    external_action = "external_action"
    artifact = "artifact"
    wiki_update = "wiki_update"
    memory_change = "memory_change"
    failure = "failure"
    retry = "retry"


class Mission(BaseModel):
    id: str = Field(default_factory=_id)
    title: str
    intent: str
    status: MissionStatus = MissionStatus.pending
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source_ref: str | None = None          # markdown mission or channel origin
    metadata: dict[str, Any] = Field(default_factory=dict)


class Run(BaseModel):
    id: str = Field(default_factory=_id)
    mission_id: str
    status: RunStatus = RunStatus.running
    agent_profile: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    summary: str | None = None


class AuditEvent(BaseModel):
    id: str = Field(default_factory=_id)
    run_id: str
    kind: EventKind
    ts: datetime = Field(default_factory=datetime.utcnow)
    actor: str                              # model id, tool name, subagent id, user
    reason: str | None = None               # reason/input/action/output/verification
    payload: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    id: str = Field(default_factory=_id)
    run_id: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    duration_ms: int | None = None
    ts: datetime = Field(default_factory=datetime.utcnow)


class Artifact(BaseModel):
    id: str = Field(default_factory=_id)
    run_id: str
    kind: str                               # file, report, patch, message
    path: str | None = None
    sha256: str | None = None
    bytes: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Source(BaseModel):
    id: str = Field(default_factory=_id)
    uri: str                                # immutable raw source pointer
    sha256: str | None = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


class WikiPage(BaseModel):
    id: str = Field(default_factory=_id)
    slug: str
    page_type: str                          # entity|concept|decision|workflow|source-summary|comparison|query|risk
    title: str
    source_id: str | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Deferred to MVP+1 (declared so later tasks reference consistent names):
# AgentProfile, Skill, Workflow, Contact, Organization, Opportunity
```

- [ ] **Step 3: Verify the schemas import and emit JSON Schema (D-012 check)**
```bash
cd "<USER_HOME>/Desktop/Projects/L2-ATLAS-PROJECT/packages/atlas-core" && \
  python -c "from atlas_core.schemas.core import Mission, Run, AuditEvent; import json; print(json.dumps(Mission.model_json_schema())[:200])"
```
Expected: a JSON Schema fragment for `Mission` (proves Pydantic source-of-truth → JSON Schema bridge works). If pydantic is not installed, note it and install into a scratch venv — do NOT add to the Hermes install venv.

- [ ] **Step 4: Commit**
```bash
git add packages/atlas-core/
git commit -m "feat(atlas-core): draft v0 domain schemas (Mission/Run/AuditEvent/ToolCall/Artifact/Source/WikiPage)"
```

**Acceptance:** Schemas import cleanly; `model_json_schema()` emits for the core types; field names match the names used in Task 7. No service wiring added.

---

## Task 7: SQLite MVP schema

**Files:**
- Create: `infra/migrations/0001_core.sql`

> DDL must mirror Task 6 field names exactly (D-012: DDL generated to match models). Audit-first: events/tool_calls/artifacts all FK to `runs`; runs FK to `missions`. WAL + FTS5 + sqlite-vec per D-003.

- [ ] **Step 1: Write `infra/migrations/0001_core.sql`**
```sql
-- 0001_core.sql — ATLAS MVP datastore (SQLite/WAL/FTS5/sqlite-vec). Mirrors atlas_core.schemas.core.
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE missions (
  id          TEXT PRIMARY KEY,
  title       TEXT NOT NULL,
  intent      TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','running','succeeded','failed','cancelled')),
  created_at  TEXT NOT NULL,
  source_ref  TEXT,
  metadata    TEXT NOT NULL DEFAULT '{}'   -- JSON
);

CREATE TABLE runs (
  id            TEXT PRIMARY KEY,
  mission_id    TEXT NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
  status        TEXT NOT NULL DEFAULT 'running'
                  CHECK (status IN ('running','succeeded','failed')),
  agent_profile TEXT,
  started_at    TEXT NOT NULL,
  finished_at   TEXT,
  summary       TEXT
);

CREATE TABLE audit_events (
  id      TEXT PRIMARY KEY,
  run_id  TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  kind    TEXT NOT NULL
            CHECK (kind IN ('llm_call','tool_call','subagent_run','approval',
                            'external_action','artifact','wiki_update',
                            'memory_change','failure','retry')),
  ts      TEXT NOT NULL,
  actor   TEXT NOT NULL,
  reason  TEXT,
  payload TEXT NOT NULL DEFAULT '{}'        -- JSON
);

CREATE TABLE tool_calls (
  id          TEXT PRIMARY KEY,
  run_id      TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  tool        TEXT NOT NULL,
  args        TEXT NOT NULL DEFAULT '{}',   -- JSON
  exit_code   INTEGER,
  stdout      TEXT,
  stderr      TEXT,
  duration_ms INTEGER,
  ts          TEXT NOT NULL
);

CREATE TABLE artifacts (
  id         TEXT PRIMARY KEY,
  run_id     TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL,
  path       TEXT,
  sha256     TEXT,
  bytes      INTEGER,
  created_at TEXT NOT NULL
);

CREATE TABLE sources (
  id          TEXT PRIMARY KEY,
  uri         TEXT NOT NULL,
  sha256      TEXT,
  ingested_at TEXT NOT NULL
);

CREATE TABLE wiki_pages (
  id         TEXT PRIMARY KEY,
  slug       TEXT NOT NULL UNIQUE,
  page_type  TEXT NOT NULL,
  title      TEXT NOT NULL,
  source_id  TEXT REFERENCES sources(id) ON DELETE SET NULL,
  updated_at TEXT NOT NULL
);

-- Indexes for the audit-first read paths
CREATE INDEX idx_runs_mission     ON runs(mission_id);
CREATE INDEX idx_events_run        ON audit_events(run_id, ts);
CREATE INDEX idx_toolcalls_run     ON tool_calls(run_id, ts);
CREATE INDEX idx_artifacts_run     ON artifacts(run_id);

-- Full-text search over wiki pages (FTS5). Content lives in the app; this is the search index.
CREATE VIRTUAL TABLE wiki_fts USING fts5(slug, title, body, content='');

-- Vector search placeholder (sqlite-vec). Loaded as an extension at runtime; guarded so the
-- migration still applies if the extension is absent during early dev.
-- CREATE VIRTUAL TABLE wiki_vec USING vec0(embedding float[768]);
```

- [ ] **Step 2: Apply the migration against a scratch DB to prove it is valid**
```bash
cd "<USER_HOME>/Desktop/Projects/L2-ATLAS-PROJECT" && \
  python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.executescript(open('infra/migrations/0001_core.sql').read()); print('OK tables:', [r[0] for r in c.execute(\"select name from sqlite_master where type='table' order by name\")])"
```
Expected: `OK tables: ['artifacts', 'audit_events', 'missions', 'runs', 'sources', 'tool_calls', 'wiki_pages']` (FTS5 must be available in the local sqlite build; if `wiki_fts` errors, note the sqlite/FTS5 gap and keep it as a separate guarded statement).

- [ ] **Step 3: Commit**
```bash
git add infra/migrations/0001_core.sql
git commit -m "feat(infra): SQLite MVP schema 0001_core (audit-first, WAL/FTS5/sqlite-vec)"
```

**Acceptance:** Migration applies on a scratch DB; table set matches the schema; column names match Task 6 models exactly; FTS5/vec status recorded.

---

## Task 8: WebUI stack spike document (resolves D-006)

**Files:**
- Create: `docs/research/WEBUI_STACK_SPIKE.md`

> This is the decision-input doc, not a built app. It must end in a recommendation that the user ratifies. Also patches the C3 inconsistency.

- [ ] **Step 1: Write the comparison**

Score SvelteKit/Svelte 5 vs Next.js/React (and note TanStack+Vite as an alternative) against the cockpit's real needs:
```markdown
| Criterion (weight) | SvelteKit/Svelte 5 | Next.js/React | Notes |
|---|---|---|---|
| Runtime perf / bundle (high) | | | cockpit = realtime dashboards |
| Realtime/streaming dashboards (high) | | | run logs, audit stream, pulse |
| L2 existing code reuse (high) | | | research says L2 has Next.js muscle |
| Dev velocity (med) | | | |
| UI polish ceiling (med) | | | "not generic admin CRUD" |
| Web/native sharing w/ Tauri shell (med) | | | D-005 thin-shell role |
| Ecosystem/hiring (low) | | | |
```

- [ ] **Step 2: State a recommendation + the smallest spike that would settle it**

Recommend one stack OR define a 1-day build spike (render a live audit-event stream from the Task 7 schema in both) that decides it objectively.

- [ ] **Step 3: Patch the C3 doc inconsistency**

Edit `docs/architecture/NATIVE_APP_STRATEGY.md` line ~14: change the WebUI "Preferred stack" cell from "Next.js or similarly excellent web stack" to "TBD pending D-006 spike (SvelteKit vs Next.js)".

- [ ] **Step 4: Commit**
```bash
git add docs/research/WEBUI_STACK_SPIKE.md docs/architecture/NATIVE_APP_STRATEGY.md
git commit -m "docs: WebUI stack spike (D-006) + reconcile NATIVE_APP_STRATEGY C3"
```

**Acceptance:** Spike doc ends in a concrete recommendation or a defined decisive build-spike; NATIVE_APP_STRATEGY no longer presupposes Next.js.

---

## Task 9: CRM/Pulse/Channels missing-research brief (closes D-010 intake)

**Files:**
- Create: `docs/research/CRM_PULSE_CHANNELS_DEEP_DIVE.md`

> No standalone report exists (gap noted in RESEARCH_SYNTHESIS and D-010). This task does not build CRM (forbidden); it prepares the research so the gap is tracked, not silently dropped.

- [ ] **Step 1: Write the research brief**

Capture the open questions and the MVP boundary:
```markdown
# CRM / Pulse / Channels — Deep Dive (intake)
Status: research pending (D-010 open).

## Why this exists
No dedicated CRM/Pulse/Channels report was produced; conclusions are scattered across
the Hermes and market reports. CRM is explicitly NOT a first surface (D-007).

## Questions to answer before any CRM build
- Minimal AI-native CRM primitives (Contact/Organization/Opportunity) — fields + relationships.
- Pulse: what monitors matter first (repo state, inboxes, deadlines, wiki health)?
- Channels: which adapter ships first, and why NOT WhatsApp production (constraint)?
- How do CRM entities reuse the audit-first event model (Task 6/7) rather than a parallel store?

## MVP boundary (locked)
CRM primitives come AFTER the mission→run→audit→wiki→cockpit loop works (D-007).
```

- [ ] **Step 2: Link it from the research backlog**

Add a one-line pointer in `docs/research/DEEP_RESEARCH_BACKLOG.md` referencing this brief and D-010.

- [ ] **Step 3: Commit**
```bash
git add docs/research/CRM_PULSE_CHANNELS_DEEP_DIVE.md docs/research/DEEP_RESEARCH_BACKLOG.md
git commit -m "docs: CRM/Pulse/Channels research intake brief (D-010)"
```

**Acceptance:** Brief exists with explicit open questions + locked MVP boundary; backlog links it.

---

## Task 10: Phase-close — update state, risks, decisions; verify gate

**Files:**
- Modify: `.planning/STATE.md`, `.planning/RISKS.md`, `docs/decisions/2026-06-04_DECISION_REGISTER.md`

- [ ] **Step 1: Append R1/R2 to `.planning/RISKS.md`**

Add: "6. Hermes is monolithic (cli.py ~685KB) — direct in-core enhancement risks upstream drift; mitigation: plugin/hook-first divergence policy." and "7. Local Hermes install holds secrets (auth.json/.env/state.db) — never vendor the install; clone fresh from upstream."

- [ ] **Step 2: Update the decision register**

Mark D-011 and D-012 as added; note D-006 spike doc created (Task 8); note D-010 intake brief created (Task 9).

- [ ] **Step 3: Update `.planning/STATE.md`**

New dated section: artifacts produced (pin doc, audits, schemas, migration, spike, CRM brief), decisions added (D-011/D-012), risks added (R1/R2), and the next step (first MVP-loop implementation, gated on D-011/D-012 ratification + Task 3 R1 verdict).

- [ ] **Step 4: Verify the pre-code gate (from NEXT_ACTION_PLAN)**
```bash
cd "<USER_HOME>/Desktop/Projects/L2-ATLAS-PROJECT" && git status --short && git log --oneline -10
```
Confirm: research synthesis exists ✓, decisions registered ✓, Hermes SHA pinned ✓ (Task 1), L2-Atlas extraction plan exists ✓ (Task 4), no secrets copied ✓ (Task 2 scan), no raw personal data copied ✓.

- [ ] **Step 5: Commit**
```bash
git add .planning/ docs/decisions/2026-06-04_DECISION_REGISTER.md
git commit -m "docs: close implementation-start phase (state, risks R1/R2, decisions D-011/D-012)"
```

**Acceptance:** All gates green; STATE.md reflects reality; the next phase (MVP-loop code) has unambiguous schemas, layout, and foundation pin to build on.

---

## Self-Review (against mission objectives)

| Mission objective | Covered by |
|---|---|
| Clone/pin Hermes foundation | Tasks 1, 2 (pinned SHA, MIT, fresh clone, secret-scan) |
| Audit Hermes extension points | Task 3 (matrix + audit-bus attachment + R1 verdict) |
| Audit L2-Atlas/src/atlas_core | Task 4 (per-module port/rewrite/reference/discard) |
| Define core schemas | Task 6 (Pydantic v0 drafts) |
| Define SQLite MVP schema | Task 7 (0001_core.sql, applies on scratch DB) |
| Decide WebUI stack spike | Task 8 (D-006 spike doc + C3 patch) |
| Prepare CRM/Pulse/Channels research | Task 9 (D-010 intake brief) |
| Write plan to specified path | This file |
| Update STATE.md | Task 10 |

**Constraints honored:** no secrets copied (Task 2 clones upstream, scans), no raw personal data, old repos not moved/modified (Tasks 3/4 read-only), Hermes clone documented before vendoring (Task 1 defers method), no Electron, no CRM build, no WhatsApp, no native overlay, audit-first preserved (Task 6/7 schemas are audit-centered).

**Execution note:** Tasks 1→2→3 and 1→4 can parallelize after Task 1 (Task 4 is independent of Hermes). Tasks 6→7 are sequential (DDL mirrors schemas) and depend on Task 5. Tasks 8, 9 are independent. Task 10 is last.
