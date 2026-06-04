# Synthesized Decisions (ingest-docs merge — 2026-06-04)

Sources (ADR precedence): D-011, D-012, DECISION_REGISTER, FOUNDATION_STRATEGY, NATIVE_APP_STRATEGY, HERMES_FOUNDATION_PIN, AGENTS.md (SPEC)

---

## LOCKED decisions (block any contradiction)

D-001  Hermes foundation used directly, not as black-box subprocess.
D-002  Every runtime action emits structured audit events (LLM call, tool call, subagent, approval, external action, artifact, wiki update, memory change, failure, retry).
D-003  SQLite/WAL/FTS5/sqlite-vec is MVP datastore. Postgres/pgvector is future SaaS option only.
D-004  LLM Wiki is first-class runtime (raw sources immutable, wiki pages agent-maintained, RAG supplements but does not replace).
D-005  Desktop/native layer is Rust-first. Electron is a negative baseline, not the default.
D-006  WebUI framework OPEN — SvelteKit/Svelte 5 vs Next.js/React; requires spike before build.
D-007  CRM is NOT first implementation surface. Comes after mission/run/audit/wiki/cockpit loop.
D-008  Existing Hermes/OpenClaw/L2 skills must be classified and polished before becoming ATLAS-grade (classes: core, operator, l2-internal, personal/private, experimental, deprecated).
D-009  Native voice/STT/TTS/overlay is a differentiator but NOT a first MVP blocker.
D-010  CRM/Pulse/Channels dedicated research still missing (open — intake brief created).
D-011  Canonical repo layout: foundation/ + packages/atlas-core + services/* + apps/* + infra/ + native/  (ratified 2026-06-04)
D-012  Pydantic v2 is single schema source of truth; JSON Schema for TS/Rust; SQLite DDL mirrors models. (ratified 2026-06-04)

## Divergence policy (from FOUNDATION_STRATEGY + HERMES_FOUNDATION_PIN)

Preference order for all Hermes changes: plugin > tool > hook > skill > ATLAS-only override > in-core edit.
Every in-core edit requires a docs/decisions/ record with classification: upstreamable | plugin/tool | ATLAS-only | experimental.

## Architecture rules (from AGENTS.md SPEC)

- Separate: (1) raw sources; (2) compiled wiki/memory; (3) runtime execution; (4) cockpit UI.
- Actions must be auditable: reason, input, tool/action, output, verification.
- Update .planning/STATE.md after every meaningful step.
