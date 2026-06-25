# Requirements: L2 ATLAS — v1.1 Multi-Surface Workbench

**Defined:** 2026-06-23
**Core value:** One serious, auditable ATLAS agent that works consistently from terminal and web
surfaces over the same projects, context, configuration, permissions, tools, and memory.

## v1.1 Requirements

### INTAKE — Terminal Harness Transformation

- [x] **INTAKE-01**: Produce a file/component/license inventory classifying donor material as
  adopt, rewrite, or reject.
- [x] **INTAKE-02**: Import no donor agent runtime, provider layer, config store, memory store,
  telemetry, updater, share service, hosted-service coupling, or product account flow.
- [x] **INTAKE-03**: Shipped code and artifacts use only ATLAS package names, symbols, commands,
  config keys, environment variables, state paths, URLs/referers, and UI strings.
- [x] **INTAKE-04**: Preserve required license/copyright notices and document donor provenance in
  attribution/design-history documentation.
- [x] **INTAKE-05**: Establish dependency, bundle/binary size, startup, idle-memory, and file-count
  budgets before adoption.

### PROMPT — Agent Identity and Prompt Compiler

- [x] **PROMPT-01**: Compile prompts from versioned layers with explicit precedence:
  platform safety → ATLAS core identity → model adapter → workspace instructions → session
  bootstrap → retrieved context → current request.
- [x] **PROMPT-02**: The immutable ATLAS core defines operator identity, audit/evidence contract,
  tool discipline, verification, uncertainty, scope control, permission behavior, and concise
  surface-appropriate communication without imported product identity.
- [x] **PROMPT-03**: Session bootstrap states surface, workspace/project, Current Focus,
  mission/run/session, available capabilities, permission mode, loaded instruction sources,
  context budget, and prompt/context versions. The agent may form a working plan but cannot
  rewrite its core identity or policy.
- [x] **PROMPT-04**: Stable system-prompt bytes are frozen per session for provider prompt caching;
  dynamic context and recall are injected separately and cannot silently mutate invariants.
- [x] **PROMPT-05**: Prompt versions, source hashes, tool-catalog version, and context source IDs
  are audit-recorded and replayable without persisting secrets or hidden chain-of-thought.

### TOOL — Tool-Call Contract

- [x] **TOOL-01**: Every available tool has one machine-readable capability record: schema,
  description, category, risk, permissions, workspace/network scope, side effects, timeout,
  cancellation, idempotency, result limit, redaction, audit events, and UI renderer.
- [x] **TOOL-02**: Tool catalog generation derives from runtime registries/manifests and rejects
  duplicate names, incompatible schemas, unclassified risk, or undocumented side effects.
- [x] **TOOL-03**: Unknown, malformed, unavailable, disallowed, wrong-workspace, and stale tool
  calls fail closed with normalized error events that both surfaces render consistently.
- [x] **TOOL-04**: Tool execution supports cancellation, bounded output, timeout, retry policy,
  secret redaction, path/network guards, and exactly-once semantics where side effects matter.
- [x] **TOOL-05**: Parent/child agent capability inheritance can only narrow permissions;
  subagent events preserve ancestry, workspace, run, tool call, and surface session identity.

### CTX — Brain, Wiki, RAG and Context

- [x] **CTX-01**: The Brain graph is the retrieval spine: project/focus/goal/task/entity
  neighborhoods and paths select candidate wiki pages, observations, runs, artifacts, sources,
  and skills.
- [x] **CTX-02**: Retrieval supports graph, FTS5, semantic, recency, failure-pattern, and skill
  signals with deterministic budgets, deduplication, freshness, provenance, and explicit
  confidence/abstention.
- [x] **CTX-03**: Automatic context injection runs only for context-dependent requests and records
  query, retrievers used, selected/rejected sources, scores, truncation, and token cost.
- [x] **CTX-04**: Retrieved/project/tool content is treated as evidence, not authority. Trust
  labels, delimiters, injection scanning, secret redaction, and instruction-hierarchy rules
  prevent untrusted text from overriding system/user policy.
- [x] **CTX-05**: The agent has explicit Brain/wiki query tools for search, page/source fetch,
  neighbors, relationship paths, provenance, and freshness; it searches before asking the user
  to repeat likely-known context.

### SURF — Shared Session and Workspace Protocol

- [ ] **SURF-01**: A surface session records surface kind/instance, workspace kind, project/root,
  mission/run/session, agent/model, permission mode, prompt/context versions, and lifecycle.
- [ ] **SURF-02**: Sessions run in either the ATLAS global workspace or a registered Project
  root resolved through the existing project model.
- [ ] **SURF-03**: Canonical path validation blocks traversal, symlink escape, stale roots, and
  undeclared cross-project writes.
- [ ] **SURF-04**: TUI and WebUI consume one normalized event stream for text, activity, tools,
  results, tasks/subagents, retries, retrieval, approvals, errors, and completion.
- [ ] **SURF-05**: Disconnect/reconnect/resume/process restart preserves session/workspace identity
  and cannot leave an unowned running execution.
- [ ] **SURF-06**: Cancellation propagates to model stream, active tools, subprocesses, and
  child agents and emits a terminal audited outcome.

### AGNT — Existing ATLAS Agent

- [ ] **AGNT-01**: TUI and WebUI use the existing ATLAS agent/runtime; no donor-specific
  `AgentRuntime`, provider layer, tool executor, or memory backend is introduced.

### CFG — Global Configuration Control Plane

- [ ] **CFG-01**: `~/.atlas/config.yaml` is the authoritative non-secret configuration file with
  a versioned frozen schema and migration path.
- [ ] **CFG-02**: Config updates are atomic, cross-process locked, optimistic-concurrency checked,
  validated, permission-hardened, and audited.
- [ ] **CFG-03**: CLI, gateway, TUI, WebUI, and future surfaces use one masked GET/PATCH contract.
- [ ] **CFG-04**: Config changes publish change events and become visible across surfaces without
  restart when hot-reloadable; restart-required fields say so explicitly.
- [ ] **CFG-05**: Every setting reports configured/effective value, source, validation status,
  restart requirement, and remediation without exposing secret values.
- [ ] **CFG-06**: Conflicting concurrent writes return a version conflict instead of silently
  overwriting another surface.

### AUTH / MODEL

- [ ] **AUTH-01**: Secrets stay in ATLAS-owned auth storage or `env:` references and never cross
  masked config/session/event APIs.
- [ ] **AUTH-02**: External auth stores are detected read-only unless an explicit later decision
  authorizes mutation.
- [ ] **MOD-01**: All surfaces show the same effective provider/model, source, auth state, health,
  and fallback status.
- [ ] **MOD-02**: Provider/model changes use the shared config/runtime contract and preserve
  current-session prompt/version semantics.

### PERM — Surface-Scoped Permission Broker

- [ ] **PERM-01**: Approval records include requesting surface/session, run/tool call, risk,
  normalized args, workspace, expiry, decision, reason, and provenance.
- [ ] **PERM-02**: Only the initiating live surface session can resolve its actionable request.
- [ ] **PERM-03**: TUI-owned requests use the ATLAS TUI native blocking prompt.
- [ ] **PERM-04**: WebUI-owned requests appear in the matching conditional header/sidebar queue.
- [ ] **PERM-05**: Headless/API `ask` decisions deny by default unless an explicit approval
  channel is registered.
- [ ] **PERM-06**: Atomic claim/decision logic guarantees at-most-once deferred execution under
  concurrent replies, reconnects, and process restart.
- [ ] **PERM-07**: Allow-once/session/always decisions cannot widen scope across surface sessions,
  workspaces, projects, tools, argument patterns, or global policy.

### TUI — ATLAS Terminal Workbench

- [ ] **TUI-01**: `atlas` and `atlas tui` open the ATLAS terminal workbench.
- [ ] **TUI-02**: Startup selects global workspace or a registered Project and shows canonical cwd.
- [ ] **TUI-03**: Compact ATLAS text identity, model/auth, permission mode, context budget, Focus,
  and session state render without imported product branding.
- [ ] **TUI-04**: Transcript and multiline composer stream normalized agent events.
- [ ] **TUI-05**: Tool calls/results, diffs, tasks/subagents, retries, retrieval provenance, and
  verification evidence have readable terminal renderers.
- [ ] **TUI-06**: Native permission prompts support approve once, scoped allow, reject, and cancel.
- [ ] **TUI-07**: Commands expose project/workspace, mission/focus, wiki/Brain, config/model,
  permission mode, help, session/resume, and diagnostics.
- [ ] **TUI-08**: Ctrl-C and cancel unwind model/tools/subagents without corrupting session state.
- [ ] **TUI-09**: Resume/replay preserves workspace plus prompt/context/tool-catalog versions.
- [ ] **TUI-10**: Layout passes narrow/wide, no-color, ASCII-safe, Unicode, Windows Terminal,
  PowerShell, cmd, VS Code, and WSL tests.
- [ ] **TUI-11**: Runtime source/bundles/snapshots contain no imported product identity outside
  approved documentation/notices.

### WEB — Web Agent and Queue UX

- [ ] **WEB-01**: WebUI starts global/project agent sessions through the shared session protocol.
- [ ] **WEB-02**: WebUI renders event parity with TUI, including retrieval and subagents.
- [ ] **WEB-03**: A minimal conditional header appears only for active/relevant agent state.
- [ ] **WEB-04**: A right permission/queue sidebar appears only for matching WebUI-owned pending
  work or when explicitly pinned.
- [ ] **WEB-05**: Config, project, model, permission, cancel, reconnect, and resume controls use the
  shared contracts.
- [ ] **WEB-06**: Queue UX is responsive, keyboard-operable, focus-safe, and screen-reader announced.

### AUDIT / SECURITY

- [ ] **AUD-01**: Every surface session, model call, retrieval, tool call, permission transition,
  config change, subagent, cancellation, and completion has structured audit identity.
- [ ] **AUD-02**: Audit can show cross-surface terminal outcomes but never grants another surface
  decision authority.
- [x] **SEC-01**: Automated scans prove no donor telemetry/update/share/network behavior or
  unapproved imported identity ships.
- [ ] **SEC-02**: Prompt injection, poisoned wiki/graph entries, malicious tool output, path escape,
  secret leakage, approval spoofing, and replay attacks fail closed.

### EVAL / TEST

- [ ] **EVAL-01**: Phase 10.2 ships a versioned reference dataset covering prompt hierarchy,
  identity, tool choice/arguments, retrieval, abstention, permissions, subagents, compaction,
  resume, uncertainty, and verification.
- [ ] **EVAL-02**: Product evals combine deterministic checks, calibrated LLM judging where needed,
  and operator review; failures block prompt/tool/context promotion.
- [ ] **TEST-01**: Prompt golden tests cover provider families, surfaces, workspaces, permission
  modes, context presence/absence, and cache-prefix stability.
- [ ] **TEST-02**: Every registered tool passes capability-schema, policy, audit, timeout,
  cancellation, malformed input, output-bound, and surface-rendering conformance tests.
- [ ] **TEST-03**: RAG tests measure context precision/recall, faithfulness, provenance,
  freshness, token budget, abstention, and poisoned-source resistance.
- [ ] **TEST-04**: Cross-surface tests run identical reference missions through TUI and WebUI and
  compare normalized events and terminal outcomes.
- [ ] **TEST-05**: At least 20 representative end-to-end runs meet reliability, no-secret,
  no-unapproved-write, exactly-once approval, startup, memory, latency, and recovery budgets.

### UX / DOCS

- [ ] **UX-01**: Errors state what failed, which contract/source decided it, and the next safe
  remediation action.
- [ ] **DOC-01**: Runbooks cover TUI, Web agent sessions, projects, config/auth/models, Brain/wiki
  retrieval, permissions, recovery, attribution, and rollback.
- [ ] **DOC-02**: Manual UAT records operator acceptance and a legacy-TUI retirement/rollback
  decision.

## Deferred

- Tauri/native shell and PTY embedding resume after Phase 10.8.
- OS keychain, multi-user/SaaS auth, mobile, voice, and global overlay remain later work.
- No new LangChain/LangGraph/LlamaIndex/CrewAI-style framework is introduced unless measured
  evidence proves the existing ATLAS contracts insufficient.

## Traceability

| Phase | Requirement groups |
|---|---|
| 10.1 | INTAKE, SEC-01 |
| 10.2 | PROMPT, TOOL, CTX, EVAL |
| 10.3 | SURF, AGNT-01, AUD-01 |
| 10.4 | CFG, AUTH, MOD, UX-01 |
| 10.5 | PERM, SEC-02, AUD-02 |
| 10.6 | TUI |
| 10.7 | WEB |
| 10.8 | TEST, DOC |

---
*Last updated: 2026-06-23 — v1.1 resumed and re-scoped by D-023.*
