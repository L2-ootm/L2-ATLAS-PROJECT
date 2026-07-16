# Gap Analysis — Legacy vs New TUI

## Feature Gaps (Legacy has, New lacks)
- /settings (provider config UI with PATCH /v1/config)
- /freellmapi (sidecar status/start/stop)
- /mode (build/plan/compose switch)
- /history (recent missions)
- /help, /quit, /new, /sidebar
- Permission overlay with 4-option scope (once/session/always/deny)
- 6 additional wired gateway endpoints
- 77 more tests (84 vs 7)

## New TUI Advantages
- Plugin system (TuiPluginRuntime)
- i18n (8 locales)
- Themes, animations, sound effects, 60fps
- /init (guided setup), /goal (stop-condition)

## Minimum Feature Set for Replacement
1. /settings adapter (provider config)
2. Permission overlay with nonce-scoped approve/reject
3. /history, /help, /quit
4. Surface session create/close + heartbeat loop
5. Bootstrap offline resilience

## Wiring Gaps
- Event shape mismatch (DonorEvent vs GlobalEvent) — 15 min fix
- 5 needed stubs to wire (/vcs, /session/status, /project, /question, /question/never-ask) — 2.5 hrs
- 4 error handling gaps (ensureSurface, gateway timeout, stream heartbeat, 502 normalization) — 1.5 hrs
- Total: ~4.5 hrs for Phase 1-3

## Test Gap
- Need ~50+ tests to match legacy density
- Priority: adapter unit tests, command routing, permission flow, session lifecycle, SSE parsing
