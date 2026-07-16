# F2: FreeLLMAPI Integration in ATLAS CLI and Rust Gateway

## 1. CLI Commands (atlas freellmapi)

The freellmapi subcommand group is registered as a Typer app at main.py:65-66:

    freellmapi_app = typer.Typer(name="freellmapi", help="FreeLLMAPI sidecar endpoint: start, status, stop.")
    app.add_typer(freellmapi_app, name="freellmapi")

### atlas freellmapi start

- **File**: main.py:1206-1219
- **What it does**: Calls freellmapi_control.start() to launch the external FreeLLMAPI sidecar (an OpenAI-compatible Node.js gateway) as a detached background process.
- **Options**: --json (emit machine-readable JSON output containing ok, message, and the full status() dict: running, base_url, dir, installed, api_key, remediation).
- **Behavior**: If already running, returns success immediately. If the checkout directory is missing, returns an error with remediation instructions (clone the sidecar). Spawns `node server/dist/index.js` detached.

### atlas freellmapi status

- **File**: main.py:1222-1233
- **What it does**: Calls freellmapi_control.status() to report sidecar liveness, base URL, install state, and API key presence.
- **Options**: --json (emit JSON with running, base_url, dir, installed, api_key, remediation).
- **Default output**: "running <base_url>" or "stopped <base_url>".

### atlas freellmapi stop

- **File**: main.py:1236-1249
- **What it does**: Calls freellmapi_control.stop() to kill the sidecar process via PID (Windows: taskkill /T /F; Unix: SIGTERM).
- **Options**: --json (emit JSON with ok and message).
- **Idempotent**: If no PID is recorded, returns a non-fatal message.

### Control module (freellmapi_control.py)

- **File**: freellmapi_control.py (164 lines)
- Key functions:
  - resolve_dir() (line 46): Locates the external checkout via ATLAS_FREELLMAPI_DIR env, then ~/.atlas/freellmapi.json state file, then sibling directory candidates.
  - health_ok(timeout) (line 61): HTTP probe against {BASE_URL}/models. Any HTTP response (even 401) counts as healthy.
  - start(poll_seconds) (line 101): Spawns `node server/dist/index.js` detached. Optionally polls until healthy.
  - stop() (line 151): Kills the recorded PID.
  - status() (line 89): Returns {running, base_url, dir, installed, api_key, remediation}.
  - get_api_key() (line 73): Reads the unified API key from the sidecar's SQLite DB.

---

## 2. atlas up / atlas down Integration

### atlas up (main.py:1019-1044)

- **Ordering**: gateway -> cockpit -> freellmapi (only if gateway AND cockpit are healthy).
- **Error handling**:
  - FreeLLMAPI is started ONLY when gateway_ok and cockpit_ok (line 1036). This is a conditional gate -- a failed gateway or cockpit blocks freellmapi start.
  - A freellmapi failure does NOT cause atlas up to exit with error. The return value from freellmapi_control.start() is discarded (_); only the message is echoed with "freellmapi: " prefix (line 1038).
  - atlas up fails (exit 1) only if gateway or cockpit fails (line 1040-1041). FreeLLMAPI is explicitly optional (D-015).

    # main.py:1034-1041
    if gateway_ok and cockpit_ok:
        _, freellmapi_message = freellmapi_control.start()
        typer.echo(f"freellmapi: {freellmapi_message}")

    if not (gateway_ok and cockpit_ok):
        raise typer.Exit(1)

### atlas down (main.py:1061-1097)

- **Ordering**: freellmapi -> cashflow -> discord -> cockpit -> gateway. FreeLLMAPI is stopped FIRST (line 1073-1074) -- it depends on nothing and is the outermost sidecar.
- **Error handling**:
  - Each component's stop() is called regardless of prior failures (failed is accumulated, not short-circuited).
  - Idempotent stop results (e.g. "no pid", "not running") are treated as success via _stop_result_is_idempotent_ok() (line 1084).
  - Supports --json for machine-readable output.
  - Exits with code 1 only if any non-idempotent stop fails.

    stop_plan = (
        ("freellmapi", freellmapi_control.stop),
        ("cashflow", cashflow_control.stop),
        ("discord", discord_control.stop),
        ("cockpit", cockpit_control.stop),
        ("gateway", gateway_control.stop),
    )

---

## 3. atlas doctor FreeLLMAPI Health Probe (doctor.py:99-114)

- FreeLLMAPI is checked as an **optional sidecar** in the sidecar loop (item 5 of the doctor report), alongside cashflow and discord.
- The check is **informational only** -- it never fails the overall doctor run (no all_ok = False on sidecar failures).
- Uses dynamic import: importlib.import_module("atlas_runtime.freellmapi_control") (line 108).
- Calls module.health_ok(timeout=0.5) -- a 0.5-second HTTP probe.
- Reports:
  - "ok" if the health check succeeds.
  - "offline - atlas freellmapi start" if the probe fails (with remediation hint).
  - "error - <exception>" if the import or call throws.

    # doctor.py:102-106
    for name, module_name, remediation in (
        ("freellmapi", "freellmapi_control", "atlas freellmapi start"),
        ("cashflow", "cashflow_control", "atlas cashflow start"),
        ("discord", "discord_control", "atlas discord start"),
    ):

---

## 4. Rust Gateway Dispatch Routes

All three routes are **dispatch-only** (D-022): the Rust gateway holds zero sidecar logic. Each handler shells out to the `atlas` CLI and parses the JSON response.

### GET /v1/freellmapi/status

- **File**: lib.rs:2281-2287
- Dispatches: `atlas freellmapi status --json`
- Returns: parsed JSON from CLI stdout.

### POST /v1/freellmapi/start

- **File**: lib.rs:2289-2295
- Dispatches: `atlas freellmapi start --json`
- Returns: parsed JSON from CLI stdout.

### POST /v1/freellmapi/stop

- **File**: lib.rs:2297-2303
- Dispatches: `atlas freellmapi stop --json`
- Returns: parsed JSON from CLI stdout.

### Route registration (lib.rs:2668-2670)

    .route("/v1/freellmapi/status", get(freellmapi_status))
    .route("/v1/freellmapi/start", post(freellmapi_start))
    .route("/v1/freellmapi/stop", post(freellmapi_stop))

All three use the standard dispatch pattern:
- dispatch_atlas() with a 30-second timeout (DISPATCH_TIMEOUT, lib.rs:490).
- JSON parse of stdout; on failure returns ApiError::Internal("freellmapi <action> parse failed: ...").
- On non-zero CLI exit or spawn failure, returns 500 via the dispatch layer.

---

## 5. Gateway Test Coverage (api.rs:1374-1409)

### freellmapi_routes_registered_and_dispatch_only

- **What it tests**: All three routes are registered and are purely dispatch-based (D-022).
- **Method**: Points atlas_cmd at a nonexistent binary (__nonexistent_atlas_binary__). Expects **500** (not 404) for all three routes, proving:
  1. Routes are registered (404 would mean unrouted).
  2. The gateway holds no sidecar logic -- a missing CLI binary produces an internal error, not a functional response.
- **Routes tested**:
  - GET /v1/freellmapi/status
  - POST /v1/freellmapi/start
  - POST /v1/freellmapi/stop

    // api.rs:1387-1408
    for (method, uri) in [
        ("GET", "/v1/freellmapi/status"),
        ("POST", "/v1/freellmapi/start"),
        ("POST", "/v1/freellmapi/stop"),
    ] {
        // ... assert_eq!(resp.status(), StatusCode::INTERNAL_SERVER_ERROR, ...)
    }

**Note**: There are no stub-based happy-path tests for freellmapi routes (unlike discord/cashflow which have happy-path tests with CLI stubs). The test coverage is limited to dispatch registration verification.

---

## 6. Dispatch Pattern (D-022 Compliance)

The D-022 pattern applied to FreeLLMAPI is identical to discord, cashflow, messaging, and tools:

| Layer | Responsibility | FreeLLMAPI Implementation |
|-------|---------------|---------------------------|
| **Rust gateway** | HTTP routing, JSON validation, timeout, dispatch | Routes requests to `atlas freellmapi <action> --json`; parses stdout JSON; no business logic. |
| **Python CLI** | Business logic, process management, state files | freellmapi_control.py manages the Node.js sidecar lifecycle. |
| **External sidecar** | The actual OpenAI-compatible API | FreeLLMAPI checkout -- never vendored (D-015). |

Key D-022 properties:
- The Rust gateway contains **zero** FreeLLMAPI-specific business logic.
- All state (PID files, directory resolution, health probing) lives in Python (freellmapi_control.py).
- The gateway is a pure HTTP-to-CLI bridge for these routes.
- The test at api.rs:1377 explicitly verifies this by showing that a missing CLI binary produces 500, not a fabricated response.

---

## Summary of File:Line References

| What | File | Lines |
|------|------|-------|
| CLI subcommand group registration | main.py | 65-66 |
| freellmapi start command | main.py | 1206-1219 |
| freellmapi status command | main.py | 1222-1233 |
| freellmapi stop command | main.py | 1236-1249 |
| atlas up freellmapi integration | main.py | 1019-1044 (esp. 1034-1041) |
| atlas down freellmapi stop ordering | main.py | 1061-1097 (esp. 1073-1074) |
| Doctor freellmapi health probe | doctor.py | 99-114 |
| freellmapi_control.py full module | freellmapi_control.py | 1-164 |
| Gateway handler: freellmapi_status | lib.rs | 2281-2287 |
| Gateway handler: freellmapi_start | lib.rs | 2289-2295 |
| Gateway handler: freellmapi_stop | lib.rs | 2297-2303 |
| Gateway route registration | lib.rs | 2668-2670 |
| Test: dispatch-only verification | api.rs | 1374-1409 |