# Synthesized Requirements (ingest-docs merge — 2026-06-04)

Sources: PRODUCT_THESIS.md (PRD), SYSTEM_OVERVIEW.md, ATLAS_SKILL_POLISHING_PLAN.md,
L2_CAPABILITIES_INCLUSION_PLAN.md, L2_ATLAS_LEGACY_CONSOLIDATION_MAP.md,
CLAUDE_IMPLEMENTATION_START_PLAN.md, NEXT_ACTION_PLAN.md, RESEARCH_SYNTHESIS.md

---

## Category: FOUNDATION — Hermes integration

FOUND-01  Hermes foundation cloned fresh at pinned SHA (e8b9369); clean from secrets and state.
FOUND-02  Hermes extension-point audit produced (hook/tool/plugin surfaces, audit hookability).
FOUND-03  Divergence policy enforced: plugin/hook-first; in-core edits documented.
FOUND-04  L2-Atlas atlas_core modules classified: port / rewrite / reference / discard.

## Category: SCHEMA — Domain contracts

SCHEMA-01  Pydantic v2 domain schemas exist for: Mission, Run, AuditEvent, ToolCall, Artifact, Source, WikiPage.
SCHEMA-02  SQLite migration 0001_core.sql applies cleanly (WAL, FTS5, foreign keys).
SCHEMA-03  JSON Schema emittable from all core Pydantic models (D-012 bridge).

## Category: RUNTIME — Enhanced agent runtime

RUNTIME-01  User can create a Mission with title, intent, and optional source reference.
RUNTIME-02  User can execute a Mission through the enhanced ATLAS/Hermes runtime.
RUNTIME-03  Every LLM call, tool call, subagent run, approval, and artifact emits a structured AuditEvent.
RUNTIME-04  Run produces a durable run record with status, start/finish timestamps, and summary.
RUNTIME-05  User can cancel a running Mission and see partial audit trail.
RUNTIME-06  Subagents are governed: role, model tier, toolset, cost budget, and audit trail all recorded.
RUNTIME-07  Policy engine enforces command/workspace safety (cross-platform; not Windows-only).

## Category: WIKI — LLM knowledge runtime

WIKI-01  User can ingest a raw source into the wiki (immutable, SHA-256 stamped).
WIKI-02  Agent can create or update a wiki page and the change is logged + indexed.
WIKI-03  User can query wiki pages via full-text search (FTS5).
WIKI-04  Wiki log.md and index.md stay consistent after every agent-driven update.
WIKI-05  Vector search index (sqlite-vec) operational for semantic wiki recall.

## Category: AUDIT — Observability

AUDIT-01  User can view the full audit trail for any Run (LLM calls, tool calls, artifacts, errors).
AUDIT-02  Audit events are exportable (JSONL) for forensic review.
AUDIT-03  Stale/contradicted wiki claims are flagged by the lint pass.

## Category: COCKPIT — Operator UI

COCKPIT-01  User can view active and historical missions and their status from the cockpit.
COCKPIT-02  User can view the audit trail for a run from the cockpit.
COCKPIT-03  User can view wiki pages and search the knowledge base from the cockpit.
COCKPIT-04  User can create and launch a mission from the cockpit.
COCKPIT-05  Cockpit renders a real-time run/event stream (low-latency dashboard).

## Category: SKILLS — Skill/workflow registry

SKILLS-01  Skill inventory exists: name, path, description, class, public-safe, polish-required.
SKILLS-02  Core ATLAS skill pack classified and manifested with required metadata.
SKILLS-03  Developer Operator Pack classified and manifested.
SKILLS-04  L2 Systems Pack classified (l2-internal, not public default).

## Category: RESEARCH — Open research

RESEARCH-01  WebUI stack spike document created (SvelteKit vs Next.js) — resolves D-006.
RESEARCH-02  CRM/Pulse/Channels deep-dive research completed.

## Category: PULSE — Monitoring (Milestone 2+)

PULSE-01  User sees a daily/periodic briefing of repo state, inboxes, deadlines, wiki health.
PULSE-02  Heartbeat monitors run on cron and emit AuditEvents.

## Category: CRM — Relationship runtime (Milestone 2+)

CRM-01  Contact/Organization/Opportunity models defined and stored in SQLite.
CRM-02  CRM entities linked to Mission/Run audit trail.

## Category: NATIVE — Desktop sidecar (Milestone 3+)

NATIVE-01  Rust native sidecar with global command palette and local IPC to runtime.
NATIVE-02  STT/TTS voice integration via Hermes providers (after runtime loop).
NATIVE-03  Floating overlay / run-status HUD with approval prompts.

## OUT OF SCOPE (MVP)

- WhatsApp/production messaging integration (constraint: too risky pre-runtime)
- Multi-tenant SaaS / billing / Postgres
- Self-modifying agent behavior
- MCP marketplace UI
- Mobile app
