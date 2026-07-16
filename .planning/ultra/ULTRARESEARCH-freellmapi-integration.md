# FreeLLMAPI Integration — Research Report

> Generated 2026-07-10 · depth: standard · 6 research angles · codebase-only (no web sources)

---

## Executive Summary

1. **FreeLLMAPI is an external Node.js sidecar** aggregating 18 free-tier LLM providers behind a single OpenAI-compatible `/v1` endpoint on port 3001. ATLAS uses it as a low-cost inference lane for classification, summarization, drafts, and background agents. [D-015]
2. **Decision D-015** mandates: sidecar first, managed sidecar second, fork/vendor last. Fork triggers require ≥2 of: upstream unmaintained >90d, unpatched security advisory >30d, rejected feature needed, distribution must bundle. [D-015:150-157]
3. **The sidecar is running** at `http://127.0.0.1:3001` with a unified API key in its SQLite DB. Node.js v24.15.0 is available. State file at `~/.atlas/freellmapi.json` records the checkout at `C:\Users\Davi\Desktop\Projects\freellmapi\`. [F6 §11]
4. **Integration spans 30+ files** across 7 layers: control module, CLI, Rust gateway (dispatch-only), provider resolution, model registry, cockpit UI, and 2 TUI surfaces. [F1-F6]
5. **Key architectural rule (D-022):** The Rust gateway holds zero freellmapi logic. All three routes (`GET/POST /v1/freellmapi/{status,start,stop}`) dispatch to the Python CLI as subprocesses. [F2]
6. **OMNI wiring law:** The sidecar owns its `unified_api_key` in its SQLite DB (`server/data/freeapi.db`). ATLAS reads it via `freellmapi_control.get_api_key()` — never from OS env vars. [F4 §3]
7. **Privacy policy (D-015:119-134):** Free-tier routes may log prompts. Approved only for non-sensitive tasks. A one-time `privacy_warning` audit event is emitted at every first run boundary. [F1 §4, F4 §6]
8. **5 coverage gaps** identified: no happy-path process management tests, no Windows kill tests, no freellmapi+Focus combined override test, no settings UI sidecar-running test, no end-to-end integration test. [F5]
9. **4 surface parity gaps:** atlas-terminal missing privacy warnings, Go TUI not auto-fetching status on startup, Go TUI not storing freellmapi keys via auth store, DialogAtlasSettings freellmapi behavior unverified. [F3 §6]
10. **Biggest operational gap:** No install/update automation. The operator must manually `git clone + npm install + npm run build`. An `atlas freellmapi install` command would close this. [F1 §10, F6 §5]

---

## 1. What FreeLLMAPI Is

**Repository:** [tashfeenahmed/freellmapi](https://github.com/tashfeenahmed/freellmapi) (MIT license)

**Purpose:** Aggregate free-tier LLM providers behind one OpenAI-compatible endpoint. Provides ~1.7B tokens/month of working inference across 160+ models.

**Supported providers (18):** Google, Groq, Cerebras, NVIDIA, Mistral, OpenRouter, GitHub Models, Cohere, Cloudflare, HuggingFace, Z.ai (Zhipu), Ollama, Kilo, Pollinations, LLM7, OVH AI Endpoints, OpenCode Zen, AI Horde, plus custom OpenAI-compatible endpoints.

**Capabilities:**
- `/v1/chat/completions`, `/v1/models`, `/v1/responses`, `/v1/embeddings`
- Encrypted API key storage (AES-256-GCM in production mode)
- Per-provider daily request caps
- Fallback chain routing across providers
- Request analytics with configurable retention
- Dashboard at `http://127.0.0.1:3001`
- Docker support

**Port:** 3001 (default), configurable via `PORT` env var.

> Sources: F1 §1, D-015:9

---

## 2. Architecture and Decision Record

### D-015 Decision

**Status:** Accepted for integration spike (2026-06-07)

**Architecture:**
```
ATLAS / Hermes
  -> http://127.0.0.1:3001/v1
  -> FreeLLMAPI sidecar
  -> configured upstream provider or keyless/free route
```

**Positive consequences:**
- Real low-cost/free inference lane
- Compatible with Hermes custom OpenAI provider config
- Provider keys isolated from ATLAS core DB
- Routed provider/model metadata captured in AuditEvent.data
- Avoids Node/Electron dependency in Python/Rust runtime

**Negative/risks:**
- Free-tier availability unstable
- Provider ToS varies; keyless routes may log prompts
- Another local process to supervise
- npm audit advisories at intake
- Not suitable for private L2/client material

### Fork/Vendor Triggers (D-021 §7)

Fork or vendor only if ≥2 of:
1. Upstream unmaintained >90 days while provider routes rot
2. Unpatched security advisory >30 days
3. ATLAS needs a routing feature upstream rejected
4. Distribution must bundle the gateway

> Sources: D-015, F1 §2-3

---

## 3. Control Module API

**File:** `services/agent-runtime/atlas_runtime/freellmapi_control.py` (164 lines)

### Constants

| Name | Value | Source |
|------|-------|--------|
| `STATE_FILE` | `~/.atlas/freellmapi.json` | freellmapi_control.py:20 |
| `DEFAULT_PORT` | 3001 | freellmapi_control.py:21 |
| `BASE_URL` | `http://127.0.0.1:3001/v1` (env: `ATLAS_LLM_GATEWAY_URL`) | freellmapi_control.py:23 |
| `CLONE_HINT` | `git clone ... && npm install && npm run build` | freellmapi_control.py:24 |

### Functions

| Function | Signature | Behavior |
|----------|-----------|----------|
| `resolve_dir()` | `() -> Path \| None` | Env > state file > sibling candidates |
| `health_ok()` | `(timeout=1.0) -> bool` | Any HTTP response = alive; only connection errors = down |
| `get_api_key()` | `() -> str \| None` | Reads `unified_api_key` from sidecar's SQLite DB |
| `status()` | `() -> dict` | `{running, base_url, dir, installed, api_key, remediation}` |
| `start()` | `(poll_seconds=0.0) -> (bool, str)` | Idempotent spawn; never sets NODE_ENV=production |
| `stop()` | `() -> (bool, str)` | Reads PID from state file, kills process tree |

### Directory Resolution Order

1. `ATLAS_FREELLMAPI_DIR` env var
2. `~/.atlas/freellmapi.json` state file (`dir` field)
3. `_EXTERNAL_REPOS/freellmapi` (gitignored)
4. `../freellmapi` (sibling directory)

> Sources: F1 §6, F1 §5

---

## 4. CLI Integration

### Commands

| Command | What it does | Options |
|---------|-------------|---------|
| `atlas freellmapi start` | Spawns sidecar, polls health | `--json` |
| `atlas freellmapi status` | Shows running/installed/key | `--json` |
| `atlas freellmapi stop` | Kills sidecar process | `--json` |

### `atlas up` Integration

- Starts freellmapi **only after** gateway+cockpit are healthy (cli/main.py:1034)
- **Never fails** `atlas up` when sidecar is absent or fails
- Return value ignored; only message printed

### `atlas down` Integration

- Stops freellmapi **first** in the teardown sequence (before cashflow, discord, cockpit, gateway)
- Each stop is individually attempted; failures don't prevent others

### `atlas doctor` Integration

- Informational health probe with 0.5s timeout (vs default 1.0s)
- Never fails the overall doctor run

> Sources: F2, F6 §5-6

---

## 5. Rust Gateway Integration

### Routes (dispatch-only, D-022)

| Route | Method | Dispatch target |
|-------|--------|----------------|
| `/v1/freellmapi/status` | GET | `atlas freellmapi status --json` |
| `/v1/freellmapi/start` | POST | `atlas freellmapi start --json` |
| `/v1/freellmapi/stop` | POST | `atlas freellmapi stop --json` |

**Zero business logic in Rust.** The gateway spawns the Python CLI as a subprocess and forwards JSON output. Test at `tests/api.rs:1374-1409` verifies route registration and 500 response when the atlas binary is absent.

> Sources: F2, native/atlas-core-rs/crates/atlas-gateway/src/lib.rs:2281-2303

---

## 6. Provider Resolution Chain

When `auth_mode == "freellmapi"`:

```
config_service.resolve_provider()
  → provider.api_key starts with "env:"? → resolve from OS env
  → still empty AND auth_mode == "freellmapi"?
    → freellmapi_control.get_api_key()
      → resolve_dir() finds checkout
      → open server/data/freeapi.db
      → SELECT value FROM settings WHERE key = 'unified_api_key'
      → return cleartext key (or None)
  → return {provider, model, auth_mode, base_url, api_key, reasoning_effort}
```

**OMNI wiring law:** The sidecar owns its key. ATLAS never stores it in env vars or its own config.

**mock_mode:** Always `False` for freellmapi — it's a real run, not mock. `provider_service.py:43` sets `real = True` for credential-less modes.

**Schema gate:** `control_plane.py:32` — `auth_mode` Literal includes `"freellmapi"` as one of 4 valid modes.

> Sources: F4 §1-4, F4 §7

---

## 7. Model Registry Integration

**File:** `services/agent-runtime/atlas_runtime/model_registry.py`

| Constant | Value | Purpose |
|----------|-------|---------|
| `DEFAULT_GATEWAY_URL` | `http://127.0.0.1:3001/v1` | FreeLLMAPI sidecar endpoint |

**Sync flow:**
1. `fetch_gateway_models()` calls `GET {base_url}/models` with optional bearer auth
2. `refresh()` does source-scoped upsert/deactivate across SQLite tables
3. Rust gateway reads the same table for its own `/v1/models` serving (D-022)

**Port 3001 is by design** — model_registry queries FreeLLMAPI's `/models` to discover available models. The naming `DEFAULT_GATEWAY_URL` is misleading (refers to sidecar, not ATLAS gateway on port 8484).

> Sources: F4 §5, F6 §9

---

## 8. Surface Integration

### Cockpit (React)

- **Settings page:** Mode selector includes freellmapi, auto-fills base_url + api_key from sidecar status
- **Status panel:** RUNNING/STOPPED indicator with START/STOP toggle button
- **Toggle behavior:** Calls freellmapiStart/Stop, polls up to 5 times at 1.2s intervals
- **Privacy warning:** `role="alert"` with ShieldAlert icon when auth_mode=freellmapi
- **Guard:** Base URL required for freellmapi save
- **API functions:** `freellmapiStatus()`, `freellmapiStart()`, `freellmapiStop()` with graceful 404/503 degradation

### Go TUI

- **Slash command:** `/freellmapi [status|start|stop]`
- **Settings:** freellmapi in provider modes cycler, privacy warning in settings form
- **Events:** `tool_name == "freellmapi"` displays privacy warning in transcript
- **Security:** `FreellmapiStatus` type omits `api_key` (unlike cockpit)
- **Base URL validation** on settings save

### atlas-terminal (donor TUI)

- **Adapter proxy:** `/atlas/freellmapi/{status,start,stop}` routes through to gateway
- **Slash commands:** `/freellmapi-status`, `/freellmapi-start`, `/freellmapi-stop`
- **Toast feedback** on each command

### Parity Gaps

1. **atlas-terminal missing privacy warning** — no freellmapi privacy banner in settings
2. **Go TUI not auto-fetching status on startup** — requires manual `/freellmapi status`
3. **Go TUI not storing freellmapi API keys** via auth store
4. **DialogAtlasSettings freellmapi behavior unverified**

> Sources: F3

---

## 9. Privacy Warning System

Two-layer enforcement:

1. **UI layer:** `provider_service.privacy_warning` field — displayed as ShieldAlert banner in cockpit and Go TUI settings
2. **Audit layer:** `native.py:249-257` — emits `tool_call` event with `tool_name="freellmapi"` and `privacy_warning` data at run boundary before execution

**Scope:** Every first run through a FreeLLMAPI route triggers the audit event. Fail-open via `_safe_emit` (native.py:423).

> Sources: F4 §6, F3 §5

---

## 10. Test Coverage

### Test Inventory (25+ functions across 6 files)

| Layer | File | Tests | Key coverage |
|-------|------|-------|-------------|
| Sidecar control | test_freellmapi_control.py | 10 | Status shape, API key reads, start/stop remediation, env dir resolution |
| Provider routing | test_provider_routing.py | 7 | Sidecar key deref, keyless contract, auth_mode validation, privacy warning |
| Provider CLI | test_provider_cli.py | 3 | Live status without key, modes coverage |
| Gateway adapter | atlasFetch.test.ts | 3 | Status/start/stop route forwarding |
| Settings UI | settings.test.tsx | 1 | Privacy warning + base_url requirement |

### Coverage Gaps

1. **No happy-path process management** — `fc.start()` and `fc.stop()` success paths untested
2. **No Windows process kill tests** — `taskkill /T /F` behavior unverified
3. **No freellmapi+Focus combined override test** — model override via Focus with freellmapi mode
4. **Settings UI never tests sidecar-running path** — start/stop mocked but never invoked
5. **No integration test** — no end-to-end chain: sidecar start → config → agent execute → response

### Benchmark Scripts

| Script | Purpose |
|--------|---------|
| freellmapi_model_benchmark.py | 23 models, 2 tests each, correctness + speed scoring |
| freellmapi_top_model_benchmark.py | 9 top models including `auto`, structured output + code |
| freellmapi_opencode_kilo_benchmark.py | 10 models, platform-family routing verification |

### Smoke Scripts

| Script | Type |
|--------|------|
| freellmapi_closed_env_smoke.py | Deterministic, local mock provider, no network |
| freellmapi_real_kilo_smoke.py | Real outbound call via Kilo keyless route |

> Sources: F5

---

## 11. Environment Variables

| Variable | File | Purpose | Default |
|----------|------|---------|---------|
| `ATLAS_LLM_GATEWAY_URL` | freellmapi_control.py:23, model_registry.py:144 | OpenAI-compatible gateway base URL | `http://127.0.0.1:3001/v1` |
| `ATLAS_LLM_GATEWAY_KEY` | .env.example:73, model_registry.py:166 | Bearer token for the sidecar | `""` (empty) |
| `ATLAS_FREELLMAPI_DIR` | freellmapi_control.py:48, .env.example:76 | Path to freellmapi checkout | auto-resolved |

**FreeLLMAPI's own env vars** (from its `.env.example`):
- `ENCRYPTION_KEY` — AES key for production mode (auto-generated in non-production)
- `PORT` — server port (default 3001)
- `HOST` — network interface (default `::`)
- `PROXY_RATE_LIMIT_RPM` — rate limit per IP (default 120)
- `FREEAPI_CONFIG_JSON` — declarative startup config
- `FREEAPI_DB_PATH` — SQLite location override

> Sources: F1 §5, F6 §7

---

## 12. Operational Gotchas

| Gotcha | Severity | Mitigation |
|--------|----------|------------|
| NODE_ENV=production crashes sidecar | **High** | Never set NODE_ENV in start() (freellmapi_control.py:121-123) |
| Cleartext API key in status --json | Medium | Documented operator concern; local-only scope |
| Health check accepts 401 as alive | Low | Intentional — sidecar may be auth-gated but functional |
| atlas up non-blocking on freellmapi | Low | By design — sidecar is optional |
| Free-tier lacks tool-calling | Medium | Use tool-capable models for real runs |
| npm audit advisories (6) | Medium | Contained — no direct ATLAS risk; remediate before distribution |
| Port 3001 naming confusion | Low | `model_registry.DEFAULT_GATEWAY_URL` refers to sidecar, not ATLAS gateway |
| PID fire-and-forget on start | Low | No crash recovery; operator must re-run `atlas freellmapi start` |
| Windows kill uses /T /F (tree) | Info | Unix uses SIGTERM only (no child kill) |

> Sources: F6 §1-9

---

## 13. Packaging and Deployment

**Current:** External, gitignored checkout. Manual `git clone + npm install + npm run build`.

**Resolution order:** env var > state file > `_EXTERNAL_REPOS/freellmapi` > `../freellmapi` (sibling).

**Runtime:** Node.js on PATH. Entry point: `<checkout>/server/dist/index.js`. Must be pre-built.

**Fork/vendor policy:** D-015:150-157 — require ≥2 trigger conditions.

**No pyproject.toml or package registration** — purely an external process managed via subprocess spawn.

> Sources: F1 §10

---

## 14. How to Set It Up Now

Your sidecar IS running. To integrate with ATLAS:

```bash
# 1. Switch to freellmapi mode
atlas config patch provider.name=freellmapi provider.auth_mode=freellmapi

# 2. Set base URL
atlas config patch provider.base_url=http://127.0.0.1:3001/v1

# 3. Add provider keys via dashboard at http://127.0.0.1:3001

# 4. Verify
atlas provider status        # should show freellmapi mode
atlas freellmapi status      # should show running + installed

# 5. Test a run
atlas mission create --title "test" --intent "hello world"
```

> Sources: F6 §11, freellmapi_control.py

---

## 15. Ideal Form (Recommendations)

| Aspect | Current | Recommendation |
|--------|---------|---------------|
| Install | Manual git clone | `atlas freellmapi install` command |
| Update | Manual git pull | `atlas freellmapi update` |
| Monitoring | One-shot health_ok | Continuous heartbeat + auto-restart |
| Config | No .env in checkout | ATLAS writes/patches sidecar .env |
| Distribution | External clone | Docker image or npm package |
| Key security | Cleartext in status | Redact in non-verbose mode |
| Fallback | None | Paid provider fallback when free exhausted |
| Task routing | All tasks to free | ATLAS-level classification (free-tier-ok vs paid-required) |
| Parity | atlas-terminal missing warnings | Add privacy warning to all surfaces |

---

## Open Questions

1. **Should `atlas freellmapi install` be implemented?** The biggest UX gap is manual setup. A one-command install that does `git clone + npm install + npm run build` would close this.
2. **Free-route tool-calling:** HTTP 429 exhaustion observed. Is this a temporary rate limit or a permanent capability gap?
3. **Privacy policy ratification:** Should the cleartext API key in `status --json` be masked? Current stance is "local-only convenience" but this diverges from the masked-secret contract.
4. **Distribution bundling:** If ATLAS ever ships as a bundled installer, FreeLLMAPI would trigger fork/vendor condition #4. Is Docker the right packaging path?
5. **Premium tier impact:** FreeLLMAPI Premium ($19/yr) provides 30-day early access to new models. Should ATLAS documentation recommend it?

---

## Sources

All sources are codebase file:line references (no external URLs — this is a codebase-only investigation).

| # | Source | Lines |
|---|--------|-------|
| [1] | docs/decisions/D-015-freellmapi-sidecar-gateway.md | 1-157 |
| [2] | services/agent-runtime/atlas_runtime/freellmapi_control.py | 1-164 |
| [3] | services/agent-runtime/atlas_runtime/config_service.py | 305-331 |
| [4] | services/agent-runtime/atlas_runtime/provider_service.py | 31-67, 156-163 |
| [5] | services/agent-runtime/atlas_runtime/model_registry.py | 33, 142-175 |
| [6] | services/agent-runtime/atlas_runtime/agents/native.py | 240-257 |
| [7] | services/agent-runtime/atlas_runtime/cli/main.py | 1019-1089, 1202-1249 |
| [8] | services/agent-runtime/atlas_runtime/cli/doctor.py | 99-114 |
| [9] | native/atlas-core-rs/crates/atlas-gateway/src/lib.rs | 2281-2303, 2668-2670 |
| [10] | services/web-ui-react/src/routes/Settings.tsx | 120-221, 305-392 |
| [11] | services/web-ui-react/src/lib/api.ts | 605-631, 937 |
| [12] | services/atlas-tui/internal/tui/commands.go | 210-219 |
| [13] | services/atlas-tui/internal/tui/model.go | 90-95, 320-336, 500-518 |
| [14] | services/atlas-tui/internal/client/client.go | 371-389 |
| [15] | services/atlas-terminal/src/adapter/atlasFetch.ts | 138-147, 344-346 |
| [16] | services/atlas-terminal/src/tui/app.tsx | 651-684 |
| [17] | packages/atlas-core/atlas_core/schemas/control_plane.py | 31-32 |
| [18] | .env.example | 69-76 |
| [19] | HANDOFF.md | 621-651 |
| [20] | .planning/STATE.md | 270-293, 662, 707-716 |
