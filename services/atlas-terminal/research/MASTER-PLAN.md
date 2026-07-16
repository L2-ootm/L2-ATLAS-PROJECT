# MASTER-PLAN — Atlas Terminal Full Functional Migration

> Synthesized 2026-07-10 from 4 research batches (8 subagents)
> Current state: atlas-terminal boots but has event shape mismatch, missing features, incomplete wiring
> Target state: MiMoCode-quality TUI, fully wired to ATLAS gateway, production ready, legacy Go TUI removed

---

## 1. Executive Summary

The atlas-terminal (vendored from opencode/MiMoCode) has superior visual quality, plugin architecture, i18n, and theme support compared to the legacy Go TUI. However, it has a critical event shape mismatch bug that crashes on every SSE event, missing features (settings, permissions, history), incomplete wiring (5 bootstrap stubs), and only 7 tests vs 84 in the legacy.

**Critical path:** Fix event shape → wire stubs → add error handling → expand tests → clean donors → remove legacy TUI.

**Total estimated effort:** 11-14 hours (event fix + wiring + hardening + tests + cleanup + removal)

---

## 2. Current State Comparison

| Dimension | Legacy Go TUI | New atlas-terminal |
|-----------|--------------|-------------------|
| Commands | 13 slash commands | 6 ATLAS + 20 donor |
| Gateway endpoints | 21 wired | 15 wired + 10 stubs |
| Tests | 84 | 7 |
| Visual quality | Basic (BubbleTea) | Very high (60fps, themes, sound) |
| Plugin system | None | TuiPluginRuntime |
| i18n | None | 8 locales |
| Binary size | 8.1 MB | N/A (Bun runtime) |
| Architecture | Single binary | Adapter + SDK + vendor tree |
| Status | Non-functional | Bootable, event crash |

---

## 3. Critical Bug: Event Shape Mismatch

**Root cause:** Adapter sends `DonorEvent { type, properties }` but SDK expects `GlobalEvent { directory, workspace, payload: { type, properties } }`.

**Impact:** Every SSE event crashes the first subscriber at `event.ts:11`. The TUI cannot process any events from the gateway.

**Fix:** Wrap events in GlobalEvent envelope in `atlasFetch.ts:handleEventStream`. Effort: 30 min.

**Property mismatches beyond wrapper:**
- session.updated, message.updated, message.part.updated: missing sessionID
- session.error: error names not in SDK union
- permission.asked: object vs string, missing patterns/always
- permission.replied: field name mismatch

---

## 4. Feature Gaps

### Must-Have for Replacement
1. /settings adapter (provider config UI)
2. Permission overlay with 4-option scope (once/session/always/deny)
3. /history, /help, /quit
4. Surface session create/close + heartbeat loop
5. Bootstrap offline resilience

### Nice-to-Have
- /mode (build/plan/compose switch)
- /freellmapi (sidecar control)
- Sound effects refinement

---

## 5. Wiring Gaps

### Phase 1: Event Fix (30 min)
- atlasFetch.ts: wrap SSE events in GlobalEvent envelope
- Add retry: 3000 header
- Update test assertions

### Phase 2: Wire Stubs (1-2 hrs)
- /vcs: git branch read
- /session/status: real idle/busy
- /project: gateway project query
- /question + /question/never-ask: gateway settings
- Remove /experimental/resource

### Phase 3: Error Handling (2-3 hrs)
- ensureSurface retry (2 attempts, 1s backoff)
- Gateway request timeout (15s)
- Stream heartbeat timeout (60s)
- Normalize 502 responses

### Phase 4: Test Coverage (3-4 hrs)
- Target: 50+ tests
- Focus: adapter unit tests, command routing, permission flow, session lifecycle, SSE parsing

### Phase 5: Donor Cleanup (30-45 min)
- ~30 renames in 6 non-vendor files
- ~40 vendor attribution comments untouched

---

## 6. Legacy Go TUI Removal

### Safe Removal Sequence
1. Retarget CLI entrypoint (main.py) to launch atlas-terminal
2. Delete go_tui.py and imports
3. Update installer scripts (remove Go build blocks)
4. Update/delete 5 test files
5. Delete services/atlas-tui/ directory
6. Clean comments in atlasFetch.ts
7. Update planning docs
8. Run full test suite

### What Breaks If Deleted Today
- atlas and atlas tui commands non-functional
- 5+ test files fail
- Installer scripts fail

---

## 7. Reusable Patterns from Foundation/MiMoCode

### From Foundation (ui-tui/)
- Ink 6.8 + nanostores state management
- GatewayClient + createGatewayEventHandler pattern
- TurnController singleton for streaming
- Reusable utilities: circularBuffer, clipboard, memory monitoring, virtual scrolling, syntax highlighting

### From MiMoCode Vendor
- vendor/shared/global.ts: path resolution backbone (actively used)
- vendor/plugin/tui.ts: plugin contract types (526 lines)
- vendor/opencode/bus/: event definitions
- Dead weight to trim: vendor/opencode/util/ (29 unexported), vendor/opencode/tool/ (stubs), vendor/opencode/server/

---

## 8. Execution Roadmap

### Wave 1: Fix the Crash (30 min)
- Fix event shape mismatch in handleEventStream
- Verify: TUI boots without crash, events render in transcript

### Wave 2: Wire Core Features (3-4 hrs)
- Wire /settings, /history, /help, /quit adapters
- Wire permission overlay with 4-option scope
- Add surface heartbeat loop
- Add bootstrap offline resilience

### Wave 3: Harden (2-3 hrs)
- ensureSurface retry
- Gateway timeouts
- Stream heartbeat
- 502 normalization

### Wave 4: Test (3-4 hrs)
- Expand from 7 to 50+ tests
- Cover adapter, SSE, permissions, sessions, commands

### Wave 5: Clean + Remove Legacy (1-2 hrs)
- Clean 97 donor references
- Remove services/atlas-tui/
- Retarget CLI to atlas-terminal
- Update installer scripts
- Update planning docs

### Wave 6: UAT + Ship
- Operator UAT in Windows Terminal
- Verify all P0-P2 commands work
- Archive legacy Go TUI
- Mark atlas-terminal as default

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Event fix breaks other SSE consumers | Low | Medium | Test with gateway running, check cockpit SSE |
| Bootstrap stubs need gateway endpoints that don't exist | Medium | Low | Graceful fallback to empty shapes |
| Timeout values too aggressive | Low | Low | Make configurable via env vars |
| Donor cleanup breaks vendor internals | Low | High | Only rename comments, not code |
| Legacy removal breaks installer | Medium | Medium | Test installer scripts after changes |

---

*Master plan synthesized from 8 parallel subagents across 4 research batches.*
