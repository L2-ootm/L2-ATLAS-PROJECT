# TUI ATLAS Branding Spec

**Phase:** 10.0.7 sub-scope (TUI-only first, full foundation deferred)
**Date:** 2026-06-23
**Status:** Approved

---

## [S1] Problem

The TUI at `foundation/atlas-hermes/ui-tui/` is stock Hermes branding: "Hermes Agent" name, Nous Research taglines, caduceus icon, `HERMES_TUI_*` env vars, `~/.hermes/` config paths, `@hermes/ink` package. The React cockpit already carries ATLAS branding. The TUI must match before public release.

## [S2] Scope

**In scope:**
- `foundation/atlas-hermes/ui-tui/` — all source, config, types, tests
- `services/agent-runtime/atlas_runtime/cli/tui.py` — launcher wrapper
- `foundation/atlas-hermes/hermes_cli/main.py` — TUI-related env vars and paths only (the `_launch_tui` function and its callers)

**Out of scope:**
- Full foundation rename (hermes_cli package, other CLI commands, infra, Docker) — deferred to 10.0.7 full pass
- Python package name `hermes-agent` → stays for now
- `~/.hermes/config.yaml` foundation config — stays for now (TUI reads it, but renaming it is the full de-brand scope)

## [S3] Approach: Wave-Based Rename

### Wave 1: Package Identity

| File | Change |
|------|--------|
| `ui-tui/package.json` | `"name": "hermes-tui"` → `"atlas-tui"` |
| `ui-tui/packages/hermes-ink/package.json` | `"name": "@hermes/ink"` → `"@atlas/ink"` |
| `ui-tui/src/types/hermes-ink.d.ts` | `declare module '@hermes/ink'` → `@atlas/ink` |
| All `src/` files importing `@hermes/ink` | → `@atlas/ink` |

### Wave 2: Brand Strings (user-visible)

| File:Line | Current | New |
|-----------|---------|-----|
| `theme.ts:240` | `name: 'Hermes Agent'` | `name: 'ATLAS'` |
| `theme.ts:241` | `icon: '⚕'` | `icon: '◆'` |
| `theme.ts:244` | `goodbye: 'Goodbye! ⚕'` | `goodbye: 'Goodbye! ◆'` |
| `branding.tsx:47` | `'Nous Research · Messenger of the Digital Gods'` | `'ATLAS · AI Operating System'` |
| `branding.tsx:48` | `'Messenger of the Digital Gods'` | `'AI Operating System'` |
| `branding.tsx:49` | `'Nous Research'` | `'ATLAS'` |
| `branding.tsx:289,320` | `' · Nous Research'` | `' · ATLAS'` |
| `branding.tsx:405` | `'hermes update'` | `'atlas update'` |
| `banner.ts:46-53` | ASCII "HERMES" | ASCII "ATLAS" |
| `banner.ts:55-71` | Caduceus art | Replace with ATLAS-appropriate art (compass star or abstract mark) |
| `helpHint.tsx:12` | `'exit hermes'` | `'exit atlas'` |
| `core.ts:114` | `'exit hermes'` | `'exit atlas'` |
| `core.ts:120` | `'update Hermes Agent...'` | `'update ATLAS to the latest version...'` |
| `core.ts:477` | `` `Hermes #${i+1}` `` | `` `ATLAS #${i+1}` `` |
| `modelPicker.tsx:182` | `'hermes model'` | `'atlas model'` |
| `modelPicker.tsx:309` | `'~/.hermes/.env'` | `'~/.atlas/.env'` (also Wave 4) |
| `setup.ts:7` | `'Hermes needs a model provider...'` | `'ATLAS needs a model provider...'` |
| `setup.ts:13` | `'hermes setup'` | `'atlas setup'` |
| `useMainApp.ts:532` | `'Hermes'` | `'ATLAS'` |
| `terminalParity.ts:73` | `'machine running Hermes'` | `'machine running ATLAS'` |
| `appChrome.tsx:30` | `EMOJI_FRAMES` first entry `'⚕ '` | Replace with `'◆ '` |

### Wave 3: Environment Variables

| Current | New | Files |
|---------|-----|-------|
| `HERMES_TUI_RESUME` | `ATLAS_TUI_RESUME` | `config/env.ts` |
| `HERMES_TUI_QUERY` | `ATLAS_TUI_QUERY` | `config/env.ts` |
| `HERMES_TUI_IMAGE` | `ATLAS_TUI_IMAGE` | `config/env.ts` |
| `HERMES_TUI_MOUSE_TRACKING` | `ATLAS_TUI_MOUSE_TRACKING` | `config/env.ts` |
| `HERMES_TUI_DISABLE_MOUSE` | `ATLAS_TUI_DISABLE_MOUSE` | `config/env.ts` |
| `HERMES_TUI_NO_CONFIRM` | `ATLAS_TUI_NO_CONFIRM` | `config/env.ts` |
| `HERMES_TUI_INLINE` | `ATLAS_TUI_INLINE` | `config/env.ts` |
| `HERMES_TUI_FPS` | `ATLAS_TUI_FPS` | `config/env.ts` |
| `HERMES_TUI_STARTUP_TIMEOUT_MS` | `ATLAS_TUI_STARTUP_TIMEOUT_MS` | `gatewayClient.ts` |
| `HERMES_TUI_RPC_TIMEOUT_MS` | `ATLAS_TUI_RPC_TIMEOUT_MS` | `gatewayClient.ts` |
| `HERMES_TUI_GATEWAY_URL` | `ATLAS_TUI_GATEWAY_URL` | `gatewayClient.ts` |
| `HERMES_TUI_SIDECAR_URL` | `ATLAS_TUI_SIDECAR_URL` | `gatewayClient.ts` |
| `HERMES_PYTHON` | `ATLAS_PYTHON` | `gatewayClient.ts`, `hermes_cli/main.py` |
| `HERMES_BIN` | `ATLAS_BIN` | `lib/externalCli.ts` |
| `HERMES_TUI_TERMUX_MODE` | `ATLAS_TUI_TERMUX_MODE` | `lib/termux.ts` |
| `HERMES_TUI_TRUECOLOR` | `ATLAS_TUI_TRUECOLOR` | `lib/forceTruecolor.ts` |
| `HERMES_HEAPDUMP_DIR` | `ATLAS_HEAPDUMP_DIR` | `lib/memory.ts` |
| `HERMES_HEAPDUMP_ON_START` | `ATLAS_HEAPDUMP_ON_START` | `entry.tsx` |
| `HERMES_DEV_PERF` | `ATLAS_DEV_PERF` | `lib/perfPane.tsx` |
| `HERMES_DEV_PERF_LOG` | `ATLAS_DEV_PERF_LOG` | `lib/perfPane.tsx` |
| `HERMES_HOME` (TUI context) | `ATLAS_HOME` | `lib/history.ts`, `hermes_cli/main.py` |

**Approach:** `replaceAll` on each file. One atomic commit per wave.

### Wave 4: Config Paths

| Current | New | Files |
|---------|-----|-------|
| `~/.hermes` | `~/.atlas` | `lib/history.ts:6`, `lib/memory.ts:148`, `lib/perfPane.tsx:24` |
| `~/.hermes/.hermes_history` | `~/.atlas/.atlas_history` | `lib/history.ts:7` |
| `~/.hermes/.env` | `~/.atlas/.env` | `components/modelPicker.tsx:309` |
| `~/.hermes/heapdumps` | `~/.atlas/heapdumps` | `lib/memory.ts:148` |
| `~/.hermes/perf.log` | `~/.atlas/perf.log` | `lib/perfPane.tsx:24` |

### Wave 5: Python Launcher

| File | Change |
|------|--------|
| `cli/tui.py` | No env var changes needed (it doesn't reference HERMES_TUI directly — it calls `_launch_tui()`) |
| `hermes_cli/main.py:11178` | `HERMES_TUI` → `ATLAS_TUI` (the trigger check) |
| `hermes_cli/main.py:1298` | `HERMES_HOME` → `ATLAS_HOME` (the home path resolution) |
| `hermes_cli/main.py:1490-1611` | All `HERMES_TUI_*` env var sets in `_launch_tui()` → `ATLAS_TUI_*` |
| `hermes_cli/main.py:1514` | `hermes-tui-active-session-` → `atlas-tui-active-session-` |

### Wave 6: Tests + Build Verification

- Update test fixtures in `ui-tui/src/__tests__/` that reference hermes strings
- Run `npm run check` (tsc)
- Run `npm run build` (vite build)
- Manual: `atlas tui` boots with ATLAS branding, no console errors

## [S4] What Stays (intentionally untouched)

- `~/.hermes/config.yaml` — foundation config file (full rename is 10.0.7 scope)
- `hermes_cli` Python package name — full rename is 10.0.7 scope
- `hermes_agent` dist name — full rename is 10.0.7 scope
- Docker/infra strings — full rename is 10.0.7 scope
- `LICENSE`, `ATTRIBUTION.md`, `DIVERGENCE_LOG.md` — always untouched

## [S5] Risk

| Risk | Mitigation |
|------|------------|
| TUI reads `~/.hermes/config.yaml` but we rename env vars to `ATLAS_*` | The config file path is NOT renamed in this phase (S4). TUI still reads `~/.hermes/config.yaml` via the foundation config loader. Only the env vars and user-visible strings change. |
| Env var rename breaks the Python → TUI bridge | `hermes_cli/main.py` TUI section is updated in Wave 5 to set `ATLAS_TUI_*` instead of `HERMES_TUI_*`. Both sides change in the same phase. |
| ASCII logo doesn't fit ATLAS (5 chars vs 6) | ATLAS is shorter — the block art will be narrower, which is fine. Design it to match the cockpit's celestial theme. |
| `@hermes/ink` rename breaks the build | The package is a local `file:` reference in package.json. Renaming the directory + package.json name + all imports in one atomic change keeps it consistent. |

## [S6] Acceptance

- `npm run check` (tsc) — green
- `npm run build` (vite build) — green
- `grep -ri hermes foundation/atlas-hermes/ui-tui/src/` — returns only test fixtures and code comments (no user-visible strings, no env vars, no config paths)
- `atlas tui` boots, displays "ATLAS" branding, no console errors
- All env vars in `src/config/env.ts` start with `ATLAS_TUI_`
- All config paths reference `~/.atlas/`, not `~/.hermes/`
