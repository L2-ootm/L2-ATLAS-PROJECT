# Phase 1: Hermes Foundation Clone & Extension Audit

**Phase number:** 1
**Name:** Hermes Foundation Clone & Extension Audit
**Status:** In progress

---

## Goal

Produce a clean, secret-free Hermes clone at the pinned SHA and an authoritative audit of all extension surfaces so every future ATLAS addition is properly grounded.

---

## Requirements Covered

| REQ-ID | Description |
|--------|-------------|
| FOUND-01 | Clone Hermes at pinned SHA with secret-scan gate confirming clean copy |
| FOUND-02 | Extension-point audit documenting hook/tool/plugin surfaces and event bus attach verdict |
| FOUND-03 | Every Hermes divergence classified (upstreamable/plugin-tool/ATLAS-only/experimental) in docs/decisions/ |
| FOUND-04 | Per-module classification (port/rewrite/reference/discard) for all L2-Atlas atlas_core donor modules |

---

## Success Criteria

1. `_EXTERNAL_REPOS/hermes-agent` exists at SHA `e8b9369a9…`, secret-scan gate reports CLEAN.
2. `docs/research/HERMES_FOUNDATION_AUDIT.md` exists with every extension-surface row filled (hook, tool registry, session store, delegation, cron, profiles, gateway, MCP, plugin surface, CLI/TUI boundary).
3. The audit states a clear YES/NO verdict on whether the audit-event bus can attach via plugin/hook without editing cli.py or run_agent.py.
4. `docs/imports/L2_ATLAS_MODULE_EXTRACTION_PLAN.md` exists with every atlas_core module classified (port/rewrite/reference/discard) and data-carrying modules linked to Phase 2 schemas.
5. L2-Atlas repo working tree is unmodified after the audit (git status clean).

---

## Key Decisions Applicable

- **D-001** (locked): Hermes foundation used directly, not as black-box subprocess.
- **D-002** (locked): Every runtime action emits structured audit events — audit-event bus must attach without in-core edits if possible.
- **D-008** (locked): Skills must be classified before shipping as ATLAS-grade — the Hermes skills surface identified here feeds Phase 9.
- **D-011** (locked): Canonical repo layout: foundation/ + packages/atlas-core + services/* + apps/* + infra/ + native/
- Divergence policy: Preference order for Hermes changes: plugin > tool > hook > skill > ATLAS-only override > in-core edit. Every in-core edit requires a docs/decisions/ record.
- Hermes SHA: `e8b9369a9d2df36139a5055cae3ed3c15691e03e` (MIT, v0.14.0 / tag v2026.5.16-1302-ge8b9369a9)

---

## What NOT to Build

- Do not write any ATLAS service code, schemas, or migrations — that is Phase 2.
- Do not vendor `C:/Users/Davi/AppData/Local/hermes/hermes-agent` — contains secrets/state files.
- Do not modify any files in the L2-Atlas source repos — audit only, read-only.
- Do not begin the event bus implementation — that is Phase 4.
- Do not classify skills beyond identifying the surface — full skill classification is Phase 9.
- Do not ship any runnable ATLAS code in this phase.
