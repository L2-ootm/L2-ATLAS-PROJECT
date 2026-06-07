# Plan 01-02 Summary — Extension-Surface Audit + Event-Bus Verdict

**Phase:** 01 — Hermes Foundation Clone & Extension Audit
**Plan:** 01-02 (Wave 2)
**Status:** Complete
**Commit:** 71e0743
**REQ-ID:** FOUND-02

## Deliverables

| File | Action |
|------|--------|
| `docs/research/HERMES_FOUNDATION_AUDIT.md` | Created — 10 extension-surface rows, VALID_HOOKS confirmed, event-bus verdict |

## Key Findings

- **Event-bus verdict: YES** — ATLAS audit plugin attaches via `~/.hermes/plugins/atlas_audit/` using `register(ctx)` + `ctx.register_hook("post_tool_call", ...)`. No in-core edits to `cli.py` or `run_agent.py` required.
- Template: langfuse observability plugin pattern
- All 10 required extension surfaces documented: hook system, tool registry, session store, delegation, cron, profiles, gateway, MCP, plugin surface, CLI/TUI boundary

## Open Question Resolutions

- **A1 (turn_id):** Correlation key is `task_id` (not `turn_id`) — Phase 2 schema correction required
- **A2 (system prompt):** ATLAS-only override via AGENTS.md context-file path
- **A3 (artifact capture):** `post_tool_call` name-filter sufficient, no in-core edit
- **A4 (state write path):** Parallel DB joined on `session_id` kwarg

## Verification

- `docs/research/HERMES_FOUNDATION_AUDIT.md` exists ✅
- Contains VERDICT line ✅
- Contains all 10 required surface rows ✅
- Cites `hermes_cli/plugins.py` and langfuse plugin as source evidence ✅
- A1–A4 resolutions present ✅
