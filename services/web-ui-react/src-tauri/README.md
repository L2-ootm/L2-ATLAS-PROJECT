# ATLAS Desktop Shell (Tauri 2)

Wraps the React cockpit in a native desktop window (system WebView2 — no bundled
Chromium) and lets the in-app UI control the gateway. The shell is intentionally
thin: its Rust commands shell out to the canonical `atlas` CLI primitive.

## Commands (Rust → exposed to the webview via `invoke`)
- `start_gateway`  → `atlas gateway start`
- `gateway_status` → `atlas gateway status`
- `stop_gateway`   → `atlas gateway stop`

The frontend calls these through `src/lib/host.ts` using the injected
`window.__TAURI__` global (`withGlobalTauri: true`), so the plain browser build
needs no `@tauri-apps/*` runtime dependency. Outside the shell, `isTauri()` is
false and the cockpit falls back to the copy-command flow.

## Prerequisites
- The `atlas` CLI on PATH (`scripts/install-atlas-cli.ps1`). The shell's
  `start_gateway` spawns it; without it the in-app button returns a clear error.
- Rust toolchain + WebView2 (Windows 11 ships it).

## Run / build (from `services/web-ui-react/`)
```bash
npm run tauri:dev     # dev: boots Vite (:5174) + the native window
npm run tauri:build   # produce the installer/bundle
```

## Notes
- `devUrl` is `http://localhost:5174` (Vite port) and `frontendDist` is `../dist`.
- Window: 1280×832, min 960×640.
- `target/` and `gen/schemas` are git-ignored; `Cargo.lock` is committed.
- Default Tauri icons are in `icons/` — replace with brand art via
  `npm run tauri icon <source.png>` later.
