# Legacy Go TUI Inventory

## Features
- 13 slash commands (settings, mode, dream, distill, deep-research, review, freellmapi, permissions, history, sidebar, new, help, quit)
- 21 gateway endpoints (surface sessions, config, models, auth, provider, freellmapi, missions, runs SSE)
- Rich UI: starfield, meteor, logo gradient, transcript, permissions sidebar, context sidebar, settings overlay, approval overlays, autocomplete
- 4 builtin workflows (dream, distill, deep-research, review)
- Full provider/model/auth mode selection with probe
- Permission polling with 4-option approve/deny
- 84 tests, 8.1 MB binary, 4,800 lines Go, 3 deps

## Strengths Over New TUI
- More slash commands (13 vs 6 ATLAS commands)
- More gateway endpoints wired (21 vs 15)
- More tests (84 vs 7)
- Simpler architecture (single binary, no adapter layer)
- Proven working end-to-end

## Weaknesses
- Go/BubbleTea rendering limits (no rich markdown, no themes, no sound)
- No plugin system
- No i18n
- Binary size growing (8.1 MB)
- Maintenance burden (separate Go codebase)
