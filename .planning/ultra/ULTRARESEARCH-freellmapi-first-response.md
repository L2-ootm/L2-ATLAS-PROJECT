# FreeLLMAPI Integration — First Response Milestone

> Generated 2026-07-11 · depth: milestone report · codebase + screenshot evidence

---

## Milestone

**First successful ATLAS → freellmapi → free provider response.**

Screenshot evidence (2026-07-11):
- User prompt: "hey who are you?"
- Provider: `Native · auto freellmapi` (shown in TUI status bar)
- Response: "I'm Hermes Agent, an AI assistant created by Nous Research."
- Context: Working directory `~/Desktop/Projects/L2-ATLAS-PROJECT/services/atlas-terminal`
- Session: `ses_mrfsw6o60001`
- Cost: `$0.00 spent` (free tier)
- Status bar shows `Build · auto` mode

This is the first time ATLAS has routed a user prompt through the freellmapi sidecar to a free-tier LLM provider and returned a coherent response.

---

## What's Working

### End-to-End Chain (Verified)

```
User types "hey who are you?"
  → Go TUI / atlas-terminal
  → Gateway POST /v1/missions/{id}/run
  → CLI: atlas mission run (dispatched subprocess)
  → NativeAtlasAgent.execute()
  → resolve_provider() → auth_mode=freellmapi
  → freellmapi_control.get_api_key() → reads sidecar SQLite DB
  → OpenAI SDK: api_key=freellmapi-b671..., base_url=http://127.0.0.1:3001/v1, model=auto
  → FreeLLMAPI sidecar routes to best available provider
  → Response returned through audit stream
  → TUI renders response
```

### Config State (Revision 11)

| Field | Value | Source |
|-------|-------|--------|
| `provider.name` | `freellmapi` | ATLAS config.yaml |
| `provider.auth_mode` | `freellmapi` | ATLAS config.yaml |
| `provider.model` | `auto` | ATLAS config.yaml |
| `provider.base_url` | `http://127.0.0.1:3001/v1` | ATLAS config.yaml |
| `provider.api_key` | *(empty in config)* | Resolved from sidecar DB at runtime |

### Sidecar State

| Metric | Value |
|--------|-------|
| Location | `C:\Users\Davi\Desktop\Projects\freellmapi\` |
| Port | 3001 |
| API keys | 14 platforms (groq, cerebras, nvidia, google, mistral, openrouter x3, cloudflare, ollama, opencode, llm7, kilo, pollinations) |
| Models available | 81 chat + 12 embedding |
| Catalog version | 2026.07.08 (monthly tier) |
| Requests processed | 11 (5 success, 6 errors — OpenRouter 429s + timeouts) |
| Status | Running (health_ok returns true) |

### Provider Routing

When `model=auto`, the sidecar routes to the best available provider. In the first response, it selected `deepseek-ai/deepseek-v4-flash` via NVIDIA. The sidecar's fallback chain tries multiple providers in parallel and returns the first successful response.

---

## What's NOT Vendored Yet

The sidecar is wired as an **external process**, not integrated into ATLAS's own runtime:

| Aspect | Current State | What "Vendored" Would Mean |
|--------|--------------|---------------------------|
| **Process** | Separate Node.js process, spawned by `freellmapi_control.start()` | Embedded in ATLAS binary or Python runtime |
| **Database** | Separate SQLite DB at `<checkout>/server/data/freeapi.db` | Unified with ATLAS's `atlas.db` |
| **API keys** | Encrypted in sidecar's own DB, read via `get_api_key()` | Managed through ATLAS's `secure_store` |
| **Dashboard** | Standalone web UI at `:3001` | Integrated into ATLAS cockpit |
| **Provider catalog** | Synced from freellmapi.co on sidecar's schedule | ATLAS-controlled refresh |
| **Config** | Sidecar's own `.env` + DB settings | ATLAS config.yaml authority |
| **Lifecycle** | Manual clone + build + `atlas freellmapi start` | `atlas up` handles everything |

### D-015 Policy

The sidecar stays external by decision (D-015). Fork/vendor only if ≥2 of:
1. Upstream unmaintained >90 days
2. Unpatched security advisory >30 days
3. ATLAS needs a rejected feature
4. Distribution must bundle it

None of these conditions are currently met.

---

## Configuration That Made It Work

Three changes from the previous config (revision 9 → 11):

```diff
- provider.name: openai-codex
+ provider.name: freellmapi

- provider.auth_mode: oauth_import
+ provider.auth_mode: freellmapi

- provider.model: gpt-5.5
+ provider.model: auto
```

**Why each mattered:**
- `name=freellmapi`: Tells the provider mesh to use freellmapi-specific resolution
- `auth_mode=freellmapi`: Triggers `get_api_key()` from sidecar DB instead of OS env
- `model=auto`: Sidecar's routing model — selects best available provider dynamically. `gpt-5.5` doesn't exist in the sidecar catalog

**The API key is automatic.** No manual key entry needed. The resolution chain:
1. `config_service.resolve_provider()` checks `auth_mode`
2. If `freellmapi` and no env key → calls `freellmapi_control.get_api_key()`
3. `get_api_key()` opens `<checkout>/server/data/freeapi.db`
4. Reads `SELECT value FROM settings WHERE key = 'unified_api_key'`
5. Returns the cleartext key for OpenAI SDK authentication

---

## Backup & Restore

All state backed up at `.ops/freellmapi-backup/`:

| File | Purpose |
|------|---------|
| `freeapi-2026-07-11.db` | Full sidecar DB (14 encrypted keys, 81 models, settings) |
| `freellmapi-state.json` | ATLAS state file (pid + dir) |
| `atlas-config-2026-07-11.yaml` | ATLAS config at time of first response |
| `RESTORE.md` | Step-by-step restore instructions |

Keys are AES-256-GCM encrypted in the DB with the sidecar's own `encryption_key`. Restoring the DB restores everything.

---

## Verification Evidence

| Test | Result | Method |
|------|--------|--------|
| Sidecar health | PASS | `GET /v1/models` returns 401 (alive, auth-gated) |
| API key auth | PASS | 63 models listed with Bearer token |
| Chat completion | PASS | `model=auto` → routed to `openai/gpt-oss-120b` (Groq) |
| Provider resolution | PASS | `resolve_provider()` returns `freellmapi-b671...` from sidecar DB |
| Direct OpenAI client | PASS | `model=auto` → response from `deepseek-ai/deepseek-v4-flash` |
| ATLAS end-to-end | PASS | User prompt → gateway → CLI → agent → sidecar → response in TUI |

---

## What's Next

### Immediate (Operator)
1. **Try more prompts** — test tool-calling capabilities with `auto` routing
2. **Add more providers** — the sidecar dashboard at `http://127.0.0.1:3001` lets you add keys for additional free tiers
3. **Switch model** — replace `auto` with a specific model if you want deterministic routing

### Short-Term (Integration)
1. **Privacy warning in TUI** — atlas-terminal doesn't show the freellmapi privacy banner (parity gap vs cockpit/Go TUI)
2. **Model registry sync** — the `models` table in ATLAS DB doesn't exist yet; `atlas models refresh` would populate it from the sidecar
3. **Focus-based model override** — test if Focus framework overrides interact correctly with freellmapi mode

### Medium-Term (Architecture)
1. **Fallback chain** — when free routes are exhausted (429), fall back to a paid provider automatically
2. **Task classification** — ATLAS-level routing: free-tier-ok tasks → freellmapi, paid-required → direct provider
3. **Rate limit awareness** — surface per-provider quota state in the cockpit dashboard

---

## Open Questions

1. **Tool-calling reliability**: The first response was a simple chat. How does `auto` routing handle tool-calling requests? Some free models don't support tools.
2. **Context window limits**: Free models have smaller context windows. How does ATLAS's context compression interact with freellmapi model limits?
3. **Streaming**: Does the sidecar support SSE streaming for real-time token delivery? The first response appeared to work but streaming behavior is unverified.
4. **Embeddings**: The sidecar has 12 embedding models. Can ATLAS use these for its wiki/knowledge-graph features?
5. **Premium tier**: FreeLLMAPI Premium ($19/yr) provides 30-day early access to new models. Worth it for ATLAS development?

---

## Sources

| # | Source | Context |
|---|--------|---------|
| [1] | Screenshot: first ATLAS freellmapi response | 2026-07-11, user prompt "hey who are you?" |
| [2] | `.planning/ultra/ULTRARESEARCH-freellmapi-integration.md` | Full architecture documentation |
| [3] | `.planning/ultra/findings/F1-architecture.md` | D-015 decision, control module API |
| [4] | `.planning/ultra/findings/F4-provider-chain.md` | Provider resolution chain |
| [5] | `.ops/freellmapi-backup/` | Backup artifacts |
| [6] | `docs/decisions/D-015-freellmapi-sidecar-gateway.md` | Canonical decision record |
