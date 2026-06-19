# Running ATLAS v1.0 from a clean checkout

This is the canonical "how do I start it" runbook for the v1.0 operator loop:
**SQLite DB → Rust gateway (`atlas-gateway`) → SvelteKit cockpit (`web-ui`)**.

All components are loopback-only. Nothing binds a routable interface and nothing
calls the network except the cockpit talking to `127.0.0.1:8484`.

---

## 0. Prerequisites

| Tool | Version used in v1.0 | Notes |
|---|---|---|
| Python | 3.11 | runs the `atlas` CLI + service layer |
| Rust / Cargo | 1.96 | builds `atlas-gateway` |
| Node | 24 | runs the SvelteKit cockpit |

Python packages are used as editable installs (no per-package venv is committed):

```bash
pip install -e packages/atlas-core
pip install -e services/agent-runtime
pip install -e services/wiki-runtime
```

---

## 1. Bootstrap the database (REQUIRED on a fresh machine)

The `atlas` CLI and the gateway both expect the schema to already exist at
`~/.atlas/atlas.db` (Windows: `%USERPROFILE%\.atlas\atlas.db`). **Neither component
auto-applies migrations.** On a brand-new checkout you must apply them once, or
the first `atlas mission create` fails with `no such table: missions`.

Apply every pending migration with the runner (idempotent, non-destructive — safe
to re-run; adopts a drifted/hand-patched DB and stamps it):

```bash
atlas db init      # apply pending migrations to ~/.atlas/atlas.db
atlas db status    # [x] applied / [ ] pending, per migration
```

To verify the schema + full loop end-to-end against a throwaway DB (does not touch
`~/.atlas`):

```bash
python scripts/fresh_db_smoke.py   # prints "SMOKE PASSED"
```

> One-shot install: `scripts/install-atlas-cli.ps1` runs the editable installs,
> `atlas db init`, and a `atlas --help` check — after it, `atlas` is on PATH and
> the DB is bootstrapped.

---

## 2. Start the gateway

Simplest — the lifecycle primitive (idempotent; locates the binary, spawns it
detached, waits for `/health`, and injects a working `ATLAS_CLI` so the gateway
can dispatch writes):

```bash
atlas gateway start    # also: atlas gateway status | atlas gateway stop
```

Release binary directly (already built at `native/atlas-core-rs/target/release/atlas-gateway.exe`):

```bash
./native/atlas-core-rs/target/release/atlas-gateway.exe
```

Or from source:

```bash
cd native/atlas-core-rs && cargo run -p atlas-gateway
```

Expected: `atlas-gateway vX.Y.Z listening on http://127.0.0.1:8484`.

Health check:

```bash
curl http://127.0.0.1:8484/health
```

### Gateway environment variables

| Var | Default | Effect |
|---|---|---|
| `ATLAS_GATEWAY_PORT` | `8484` | bind port. **Leave at 8484** — the cockpit hardcodes this URL (`web-ui/src/lib/api.ts`). |
| `ATLAS_DB` | `~/.atlas/atlas.db` | DB the gateway **reads**. |
| `ATLAS_CLI` | `atlas` | command the gateway shells out to for **writes** (mission create/run/cancel). |
| `ATLAS_CORS_ORIGINS` | (none) | extra allowed origins. |

> Consistency caveat: the gateway honours `ATLAS_DB`, but the Python `atlas` CLI
> always writes to `~/.atlas/atlas.db` (path is hardcoded). If you point `ATLAS_DB`
> elsewhere, gateway reads and CLI writes diverge. For v1.0, leave `ATLAS_DB` unset
> so both use the same default DB.

---

## 3. Start the cockpit

```bash
cd services/web-ui
npm install      # first time only
npm run dev      # http://localhost:5173
```

Production build (adapter-static; output in `services/web-ui/build/`):

```bash
npm run build && npm run preview
```

The cockpit targets `http://127.0.0.1:8484` for all data. If the gateway is down
the sidebar shows an offline state rather than crashing.

### Desktop shell (Tauri 2) — optional native window

The React cockpit can run as a native desktop app (system WebView2) that can start
the gateway from inside the app (the System-page "Start Gateway" button). Requires
the `atlas` CLI on PATH (`scripts/install-atlas-cli.ps1`).

```bash
cd services/web-ui-react
npm run tauri:dev     # native window + Vite dev (:5174)
npm run tauri:build   # installer / bundle
```

See `services/web-ui-react/src-tauri/README.md`. Outside the shell the same UI
falls back to the copy-command flow (`atlas gateway start`).

---

## 4. Smoke the loop manually

See `.planning/phases/09.5-public-hardening/MANUAL_TEST_GUIDE.md` for the full
operator acceptance checklist (create mission → run → live events → wiki → export).

---

## Limitations (v1.0)

- No DB bootstrap command — apply migrations manually (§1).
- Gateway port is effectively fixed at 8484 because the cockpit URL is compiled in.
- `atlas` CLI DB path is not configurable via env.
- Native shell (Tauri) is **Phase 10 / v1.1**, not v1.0 — run the cockpit in a browser.
