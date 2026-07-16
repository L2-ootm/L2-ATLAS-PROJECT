# F4 — FreeLLMAPI Provider Resolution & Model Registry Integration

## Table of Contents

1. [Full Provider Resolution Chain (auth_mode=freellmapi)](#1-full-provider-resolution-chain-auth_modefreellmapi)
2. [Sidecar API Key Reading (SQLite DB)](#2-sidecar-api-key-reading-sqlite-db)
3. [OMNI Wiring Law](#3-omni-wiring-law)
4. [mock_mode Projection for freellmapi](#4-mock_mode-projection-for-freellmapi)
5. [Model Registry Sync from the Sidecar](#5-model-registry-sync-from-the-sidecar)
6. [Privacy Warning Audit Event at Run Boundaries](#6-privacy-warning-audit-event-at-run-boundaries)
7. [Schema Definition](#7-schema-definition)

---

## 1. Full Provider Resolution Chain (auth_mode=freellmapi)

The provider resolution chain is a six-step process that starts at the schema layer and threads through config, sidecar API key lookup, and status composition.

### Step 1 — Schema Gate

The `auth_mode` field on `ProviderConfig` is a `Literal` restricting values to four modes. The schema rejects any value not in the set at validation time.

- **File**: `packages/atlas-core/atlas_core/schemas/control_plane.py`
- **Line 32**: `auth_mode: Literal["api_key", "oauth_import", "claude_code", "freellmapi"] = "api_key"`

### Step 2 — `config_service.resolve_provider()`

This is the central resolution function. When `provider.auth_mode == "freellmapi"`, it follows a specific branch:

1. Loads `AtlasConfig` (default or caller-supplied).
2. Extracts the model: uses `focus_framework` if provided, else `provider.model`.
3. Checks if `api_key` starts with `"env:"` — if so, dereferences the env var.
4. **If `api_key` is still empty AND `auth_mode == "freellmapi"`**: lazily imports `freellmapi_control` and calls `get_api_key()` to pull the key from the sidecar's SQLite DB.
5. Returns a dict with `provider`, `model`, `auth_mode`, `base_url`, `api_key`, `reasoning_effort`.

Key code path:

```python
# config_service.py:317-323
if not api_key and provider.auth_mode == "freellmapi":
    from atlas_runtime import freellmapi_control  # noqa: PLC0415
    api_key = freellmapi_control.get_api_key() or ""
```

- **File**: `services/agent-runtime/atlas_runtime/config_service.py`
- **Lines 305-331**: `resolve_provider()` function
- **Lines 317-323**: freellmapi branch with lazy import

The OMNI wiring law reference is embedded in the comment at line 319: `OMNI_SURFACE_WIRING_STRATEGY S1-2`.

### Step 3 — Sidecar API Key Lookup

`freellmapi_control.get_api_key()` reads the unified API key directly from the sidecar's SQLite database. (See Section 2 below.)

- **File**: `services/agent-runtime/atlas_runtime/freellmapi_control.py`
- **Lines 73-86**: `get_api_key()` function

### Step 4 — `provider_service.active_status()`

Composes the operator-facing status view. For freellmapi:

- Calls `config_service.resolve_provider(config)` to get the resolved dict.
- Sets `real = True` when `auth_mode in ("claude_code", "freellmapi")` — freellmapi is always treated as a real run regardless of whether a key resolved (line 43).
- Attaches `privacy_warning` string when `auth_mode == "freellmapi"` (lines 63-66).
- `mock_mode` is `not real`, so freellmapi gets `mock_mode = False`.

Key code:

```python
# provider_service.py:43
real = api_key_present or codex_ready or auth_mode in ("claude_code", "freellmapi")
```

```python
# provider_service.py:63-66
"privacy_warning": (
    "free endpoints may log prompts — never send secrets"
    if auth_mode == "freellmapi" else None
),
```

- **File**: `services/agent-runtime/atlas_runtime/provider_service.py`
- **Lines 31-67**: `active_status()` function
- **Line 43**: freellmapi always real
- **Lines 63-66**: privacy_warning injection

### Step 5 — `_freellmapi_mode()` (modes_status board)

Reports per-mode availability for the multi-mode "which ways can I wire?" board:

- Available when `base_url` is set AND `auth_mode == "freellmapi"`.
- Returns remediation instructions when unavailable.

```python
# provider_service.py:156-164
def _freellmapi_mode(config):
    base_url = config.provider.base_url
    available = bool(base_url) and config.provider.auth_mode == "freellmapi"
    return {
        "available": available,
        "detail": f"base_url: {base_url}" if base_url else "no base_url configured",
        "remediation": None if available
        else "set provider.auth_mode=freellmapi and provider.base_url=<endpoint>",
    }
```

- **File**: `services/agent-runtime/atlas_runtime/provider_service.py`
- **Lines 156-164**: `_freellmapi_mode()`

### Step 6 — Native Agent Resolution

`NativeAtlasAgent._resolve_provider()` calls `config_service.resolve_provider()` with the active Focus framework, then threads `auth_mode` through so `execute()` can treat freellmapi as a real run.

```python
# native.py:160
auth_mode = resolved.get("auth_mode") or "api_key"
```

```python
# native.py:244
free_keyless = auth_mode == "freellmapi" and bool(base_url)
```

- **File**: `services/agent-runtime/atlas_runtime/agents/native.py`
- **Lines 135-178**: `_resolve_provider()`
- **Line 160**: auth_mode extraction
- **Lines 244-257**: freellmapi keyless real-run path + privacy warning emit

---

## 2. Sidecar API Key Reading (SQLite DB)

### Location resolution

The sidecar directory is resolved in priority order:

1. `ATLAS_FREELLMAPI_DIR` environment variable (`freellmapi_control.py:48`)
2. `~/.atlas/freellmapi.json` state file's `dir` field (`freellmapi_control.py:52`)
3. Candidate sibling paths (`_EXTERNAL_REPOS/freellmapi` or parent `freellmapi/`) (`freellmapi_control.py:55-57`)

### DB path

Once the root is resolved, the SQLite DB is at `<root>/server/data/freeapi.db`.

### Query

```python
# freellmapi_control.py:73-86
def get_api_key() -> str | None:
    root = resolve_dir()
    if not root:
        return None
    db_path = root / "server" / "data" / "freeapi.db"
    if not db_path.exists():
        return None
    try:
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = 'unified_api_key'").fetchone()
            return row[0] if row else None
    except Exception:
        return None
```

- **File**: `services/agent-runtime/atlas_runtime/freellmapi_control.py`
- **Lines 73-86**: `get_api_key()`
- **Lines 46-58**: `resolve_dir()` (sidecar location resolution)
- **Line 20**: `STATE_FILE = pathlib.Path.home() / ".atlas" / "freellmapi.json"`
- **Line 23**: `BASE_URL` default: `http://127.0.0.1:3001/v1`

The key is read from the `settings` table, column `value`, where `key = 'unified_api_key'`. The function is fail-safe: any exception returns `None`, which `resolve_provider()` treats as an empty string (line 323).

### Health check

`health_ok()` at `freellmapi_control.py:61-70` confirms the sidecar is listening by hitting `{BASE_URL}/models`. Any HTTP response (even 401) counts as alive.

---

## 3. OMNI Wiring Law

The OMNI wiring law governs how credential-less provider modes (freellmapi, claude_code, oauth_import) can execute real runs without an OS env var side channel.

### Principle (from `resolve_provider` comment)

```python
# config_service.py:318-320
# The sidecar owns its unified key; runs must not depend on an OS env
# var side channel (OMNI_SURFACE_WIRING_STRATEGY S1-2). Best-effort:
# a stopped/absent sidecar keeps the keyless-base_url contract intact.
```

**Core rule**: When `auth_mode == "freellmapi"`, the API key is sourced from the sidecar's own SQLite DB — never from an OS environment variable. The sidecar is the single owner of the unified key. If the sidecar is stopped or absent, `get_api_key()` returns `None` and the run degrades gracefully (empty key, but `base_url` may still be set for keyless endpoints).

### Enforcement points

| Location | File | Line(s) | What it enforces |
|----------|------|---------|------------------|
| `resolve_provider()` | `config_service.py` | 317-323 | Sidecar DB key, not env var |
| `active_status()` | `provider_service.py` | 38-43 | freellmapi always real, no key dependency |
| `_freellmapi_mode()` | `provider_service.py` | 156-164 | availability gated on base_url, not api_key |
| `NativeAtlasAgent.execute()` | `agents/native.py` | 244-257 | keyless base_url = real run; privacy warning |

### The "keyless base_url contract"

freellmapi endpoints may not require an API key at all. The contract is:

- `base_url` set + `auth_mode == "freellmapi"` = real run (even with `api_key == ""`).
- The sidecar may *also* provide a key from its DB for authenticated upstream calls.
- An absent/stopped sidecar degrades to "keyless" — the `base_url` still routes traffic if the endpoint allows unauthenticated access.

---

## 4. mock_mode Projection for freellmapi

### Decision chain

`mock_mode` determines whether a run calls a real LLM provider or falls back to the deterministic mock agent. The decision is consistent across all three projection surfaces.

**Rule**: `mock_mode = not real`, where `real` is true when:
- `api_key_present` (a key resolved), OR
- `codex_ready` (oauth_import with valid store), OR
- `auth_mode in ("claude_code", "freellmapi")` — these modes are inherently real.

```python
# provider_service.py:37-43
real = api_key_present or codex_ready or auth_mode in ("claude_code", "freellmapi")
```

For freellmapi, `real` is always `True` regardless of whether a key resolved. Therefore `mock_mode` is always `False`.

### Three projection surfaces

All three surfaces delegate to `provider_service.active_status()`:

1. **`masked_dict()`** in `config_service.py:334-344`:
   ```python
   data["mock_mode"] = bool(provider_service.active_status(config)["mock_mode"])
   ```

2. **`get_config_snapshot()`** in `control_plane_service.py:142-153`:
   ```python
   data.update({
       "mock_mode": bool(provider_service.active_status(config)["mock_mode"]),
   })
   ```

3. **`active_status()` itself** in `provider_service.py:58`:
   ```python
   "mock_mode": not real,
   ```

- **File**: `services/agent-runtime/atlas_runtime/config_service.py`, lines 334-344
- **File**: `services/agent-runtime/atlas_runtime/control_plane_service.py`, lines 142-153
- **File**: `services/agent-runtime/atlas_runtime/provider_service.py`, line 58

### Why freellmapi is never mock

The comment at `control_plane_service.py:143-144` explains:
```
# mock_mode must agree with what a run would actually do; api_key presence
# alone is blind to oauth_import/claude_code/freellmapi (all real without a
# resolved key here). Delegate to the provider-mesh projection.
```

freellmapi runs hit real free endpoints. A stopped sidecar does not trigger mock mode — it means the `base_url` may be unreachable, but the run is still a "real" attempt. The foundation harness returns an honest failure (`failed/error`) rather than a MOCK MODE response.

---

## 5. Model Registry Sync from the Sidecar

### Architecture

`model_registry.py` keeps a local SQLite table (`model_registry`) in sync with the model list exposed by the sidecar's OpenAI-compatible `/v1/models` endpoint. The Rust gateway reads the same SQLite table directly for `/models` serving — no logic duplication (D-017/D-022).

### Default gateway URL

```python
# model_registry.py:33
DEFAULT_GATEWAY_URL = "http://127.0.0.1:3001/v1"
```

```python
# model_registry.py:142-144
def gateway_base_url() -> str:
    return os.environ.get("ATLAS_LLM_GATEWAY_URL", DEFAULT_GATEWAY_URL).rstrip("/")
```

- **File**: `services/agent-runtime/atlas_runtime/model_registry.py`
- **Line 33**: `DEFAULT_GATEWAY_URL`
- **Lines 142-144**: `gateway_base_url()` — env override via `ATLAS_LLM_GATEWAY_URL`

### `fetch_gateway_models()`

Hits `GET {base_url}/models` with an optional Bearer token (env `ATLAS_LLM_GATEWAY_KEY`).

```python
# model_registry.py:147-175
def fetch_gateway_models(base_url=None, api_key=None, timeout=10.0):
    url = (base_url or gateway_base_url()).rstrip("/") + "/models"
    key = api_key if api_key is not None else os.environ.get("ATLAS_LLM_GATEWAY_KEY", "")
    req = urllib.request.Request(url)
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    data = body.get("data") if isinstance(body, dict) else None
    ...
    return [m for m in data if isinstance(m, dict) and m.get("id")]
```

- **File**: `services/agent-runtime/atlas_runtime/model_registry.py`
- **Lines 147-175**: `fetch_gateway_models()`

### `refresh()` — Sync Logic

The sync follows a source-scoped upsert/deactivate pattern:

1. **Added**: models in the gateway response but not in the DB for this source → `INSERT OR IGNORE` with `first_seen = now`, `active = 1`.
2. **Retained**: models already known → `UPDATE last_seen = now, active = 1` (reactivates previously deactivated models).
3. **Deactivated**: active models for this source missing from the response → `UPDATE active = 0`.

Additionally, the v2 schema (`model_registry_v2`) is maintained with composite key `(model_id, provider_id, source)` and provider-level rows in `provider_registry`.

```python
# model_registry.py:178-352
def refresh(conn, lock, *, source=None, fetcher=fetch_gateway_models, auth_status_resolver=None):
    ...
    # Lines 229-265: legacy table upsert/deactivate
    # Lines 267-346: v2 table upsert/deactivate + provider_registry
```

- **File**: `services/agent-runtime/atlas_runtime/model_registry.py`
- **Lines 178-352**: `refresh()`

### Schema tables

Three tables are created idempotently:

| Table | Purpose | Key |
|-------|---------|-----|
| `model_registry` | Legacy flat model list | `model_id` PK |
| `provider_registry` | Provider metadata | `provider_id` PK |
| `model_registry_v2` | Composite model/provider/source | `(model_id, provider_id, source)` PK |

- **Lines 35-75**: Schema DDL (`_SCHEMA`, `_PROVIDER_SCHEMA`, `_MODEL_V2_SCHEMA`)
- **Lines 92-96**: `ensure_schema()` — idempotent creation

### Seed models (offline fallback)

```python
# model_registry.py:104-109
SEED_SOURCE = "seed"
DEFAULT_SEED_MODELS = (
    ("claude-fable-5", "anthropic"),
    ("claude-sonnet-4-6", "anthropic"),
    ("gemini-2.5-pro", "google"),
)
```

Seed rows use `source="seed"` so `refresh()`'s source-scoped deactivation never touches them. They act as an offline fallback when no LLM gateway is configured.

- **File**: `services/agent-runtime/atlas_runtime/model_registry.py`
- **Lines 99-139**: Seed constants and `seed_default_models()`

### Rust gateway reads the same table

Per the module docstring (`model_registry.py:11-12`):
> The Rust gateway reads the same SQLite table directly for /models serving — no logic duplication.

This is the D-022 language rule boundary: Python feeds the registry; Rust consumes it.

---

## 6. Privacy Warning Audit Event at Run Boundaries

### Two-layer warning system

The privacy warning for freellmapi is surfaced at two distinct points:

#### Layer 1 — Status composition (non-audit, operator-facing)

`active_status()` attaches a `privacy_warning` string to every status response when `auth_mode == "freellmapi"`:

```python
# provider_service.py:62-66
"privacy_warning": (
    "free endpoints may log prompts — never send secrets"
    if auth_mode == "freellmapi" else None
),
```

This is a persistent status field visible in every UI (CLI, cockpit, TUI). It does not produce an audit event.

- **File**: `services/agent-runtime/atlas_runtime/provider_service.py`
- **Lines 62-66**: `privacy_warning` field

#### Layer 2 — Run-boundary audit event (D-002 audit-first)

At the start of `NativeAtlasAgent.execute()`, when `free_keyless` is true (freellmapi + base_url set), an audited `tool_call` event is emitted:

```python
# native.py:244-257
free_keyless = auth_mode == "freellmapi" and bool(base_url)
if free_keyless:
    # Privacy posture (S2.3): free models may log prompts. Surface a
    # one-time, audited warning at the run boundary (D-002 audit-first)
    # so the operator sees the cost of the mode they wired.
    self._safe_emit(
        conn, lock, run_id, event_type="tool_call", tool_name="freellmapi",
        data={
            "runtime": "native",
            "privacy_warning": (
                "free models may log prompts — do not send secrets"
            ),
        },
    )
```

- **File**: `services/agent-runtime/atlas_runtime/agents/native.py`
- **Lines 244-257**: Privacy warning audit emit

### Why two layers

- **Status composition** (`provider_service.py`): Shows the warning on every status poll/dashboard — the operator always sees the cost of the mode.
- **Audit event** (`native.py`): Records a timestamped, run-scoped audit trail entry. This is the D-002 "audit-first" principle: the warning is permanently recorded in the audit database before the run proceeds.

### `_safe_emit` fail-open

The emit itself is wrapped in `_safe_emit()` (`native.py:423-433`), which catches exceptions and logs a warning rather than crashing the run. Audit failure never blocks execution.

- **File**: `services/agent-runtime/atlas_runtime/agents/native.py`
- **Lines 423-433**: `_safe_emit()`

---

## 7. Schema Definition

### `ProviderConfig` — The freellmapi-relevant fields

```python
# control_plane.py:24-48
class ProviderConfig(_FrozenControlPlaneModel):
    name: str = "openrouter"
    model: str = "anthropic/claude-sonnet-4"
    auth_mode: Literal["api_key", "oauth_import", "claude_code", "freellmapi"] = "api_key"
    api_key: str = ""
    base_url: str | None = None
    reasoning_effort: Literal["", "minimal", "low", "medium", "high"] = ""
```

- **File**: `packages/atlas-core/atlas_core/schemas/control_plane.py`
- **Lines 24-48**: `ProviderConfig` class
- **Line 32**: `auth_mode` Literal definition
- **Line 34**: `base_url` — required for freellmapi (the endpoint address)

### `api_key` validator

The `api_key` field is validated to ensure it is either empty or an `env:VAR_NAME` reference. This validator does NOT apply to freellmapi key resolution (which reads from the sidecar DB), but it constrains what can be written to the config file.

```python
# control_plane.py:39-48
@field_validator("api_key", mode="before")
@classmethod
def validate_api_key_reference(cls, value):
    ...
    if value and not _ENV_REFERENCE.fullmatch(value):
        raise ValueError("provider.api_key must be empty or an env:VAR_NAME reference")
    return value
```

- **File**: `packages/atlas-core/atlas_core/schemas/control_plane.py`
- **Lines 39-48**: `api_key` validator

### `ControlPlaneSnapshot` — mock_mode field

```python
# control_plane.py:319-323
class ControlPlaneSnapshot(AtlasConfig):
    settings: tuple[SettingStatus, ...] = ()
    auth: tuple[AuthStatus, ...] = ()
    effective: ProviderModelStatus | None = None
    mock_mode: bool = True
```

- **File**: `packages/atlas-core/atlas_core/schemas/control_plane.py`
- **Lines 319-323**: `ControlPlaneSnapshot` — `mock_mode` defaults to `True` (safe default: real runs require explicit credential resolution)

### `AtlasConfig` — Provider config container

```python
# control_plane.py:251-261
class AtlasConfig(_FrozenControlPlaneModel):
    schema_version: Literal[1] = 1
    revision: int = Field(default=0, ge=0)
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    ...
```

- **File**: `packages/atlas-core/atlas_core/schemas/control_plane.py`
- **Lines 251-261**: `AtlasConfig` — frozen, validated root config

---

## Summary: End-to-End Flow

```
config.yaml (auth_mode=freellmapi, base_url=<endpoint>)
    │
    ▼
AtlasConfig.provider.auth_mode == "freellmapi"
    │
    ▼
resolve_provider()
    ├─ api_key from env:VAR? ── No (freellmapi typically empty)
    ├─ freellmapi_control.get_api_key()
    │   ├─ resolve_dir() → sidecar checkout location
    │   └─ SELECT value FROM settings WHERE key='unified_api_key'
    │       └─ from <root>/server/data/freeapi.db
    └─ returns {provider, model, auth_mode, base_url, api_key, reasoning_effort}
        │
        ▼
active_status() ── real=True (auth_mode in freellmapi set)
    ├─ mock_mode = False
    └─ privacy_warning = "free endpoints may log prompts — never send secrets"
        │
        ▼
NativeAtlasAgent.execute()
    ├─ _resolve_provider() → auth_mode="freellmapi", base_url set
    ├─ free_keyless = True (auth_mode=="freellmapi" AND base_url set)
    ├─ EMIT privacy_warning audit event (D-002)
    └─ Route to real foundation harness (NOT mock)
        │
        ▼
model_registry.refresh() (periodic)
    ├─ GET {base_url}/models → list of model dicts
    ├─ Upsert into model_registry + model_registry_v2
    ├─ Deactivate missing models (source-scoped)
    └─ Rust gateway reads same SQLite table for /models serving
```
