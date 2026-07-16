# New atlas-terminal Inventory

## Features
- 6 ATLAS commands (init, review, dream, distill, goal, deep-research) + 20+ donor commands
- 15 fully wired gateway endpoints + 10 bootstrap stubs
- Very high visual quality (animated logo, starry background, themes, sound effects, 60fps)
- Plugin system (TuiPluginRuntime with slots)
- i18n (8 locales)
- Theme switching (dark/light/lock)
- Background images, logo design variants

## Strengths Over Legacy TUI
- Much richer visual quality (animations, themes, sound)
- Plugin architecture for extensibility
- i18n support
- TypeScript/React ecosystem (larger contributor pool)
- Donor-derived from production-quality opencode/MiMoCode

## Weaknesses
- Event shape mismatch bug (DonorEvent vs GlobalEvent)
- Only 7 tests (vs 84 in legacy)
- 97 donor references to clean
- Adapter incomplete (skills, LSP, MCP, VCS are stubs)
- More complex architecture (adapter layer, SDK, vendor tree)
- Bootstrap crashes when gateway is offline
