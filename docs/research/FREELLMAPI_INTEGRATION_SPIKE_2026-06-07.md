# FreeLLMAPI Integration Spike — ATLAS/Hermes

**Repo:** https://github.com/tashfeenahmed/freellmapi  
**Local intake clone:** `<USER_HOME>/AppData/Local/Temp/freellmapi`  
**Commit inspected:** `43415fd Merge pull request #252 from tashfeenahmed/feat/install-script-and-lan-docs`  
**Date:** 2026-06-07  
**License:** MIT

## Executive verdict

**High-value candidate. Do not vendor directly into ATLAS yet. Integrate as a sidecar OpenAI-compatible inference gateway first.**

FreeLLMAPI is almost exactly the missing low-cost inference substrate ATLAS needs for non-critical/background work: it exposes a single OpenAI-compatible endpoint over many free-tier providers, has fallover/rate tracking, supports `/v1/chat/completions`, `/v1/models`, `/v1/responses`, streaming, tool calls, embeddings, analytics, encrypted key storage, dashboard auth, Docker deployment, and a desktop Electron app.

The right ATLAS move is a **Phase 4.5 / Phase 5 integration spike**:

1. Run FreeLLMAPI locally as a sidecar on loopback only.
2. Configure Hermes/ATLAS custom provider to use `http://127.0.0.1:<port>/v1`.
3. Route only low-risk tiers through it first: classification, summarization, draft generation, embeddings experiments, low/medium subagents.
4. Keep high-stakes coding/reasoning on known paid/stable providers until reliability is proven.

## What it provides

FreeLLMAPI claims and implements:

- OpenAI-compatible chat endpoint: `POST /v1/chat/completions`.
- OpenAI-compatible model list: `GET /v1/models`.
- OpenAI Responses API shim: `POST /v1/responses`.
- Streaming and non-streaming responses.
- Tool calling support.
- Vision routing for image inputs on chat completions.
- Embeddings endpoint with family-safe routing.
- Fallback chain across providers when a provider returns 429/5xx/timeout.
- Per-key quota/rate tracking.
- Sticky sessions to avoid mid-conversation model switching.
- AES-256-GCM encrypted upstream key storage in SQLite.
- Unified local API key for client apps.
- React/Vite dashboard.
- Docker deployment.
- Desktop Electron tray app.

Supported/provider categories include Google, Groq, Cerebras, Mistral, OpenRouter, GitHub Models, Cohere, Cloudflare, HuggingFace Router, Z.ai/Zhipu, Ollama Cloud, Kilo, Pollinations, LLM7, OpenCode Zen, and custom OpenAI-compatible endpoints.

## Validation performed

### Install/build/test

Initial `npm install --ignore-scripts` installed JS deps but caused `better-sqlite3` native binding failures during tests. After rebuilding native binding:

```text
npm rebuild better-sqlite3
npm test
```

Result:

```text
42 test files passed
384 tests passed
```

Production build:

```text
npm run build
```

Result:

```text
server tsc passed
client tsc + vite build passed
```

Vite warning: main client JS chunk is ~1.1 MB / 340 KB gzip; acceptable for admin dashboard, not a blocker.

### Runtime smoke

Started built server with generated encryption key on port `3017`.

Unauthenticated probes returned expected auth failures:

```text
GET /api/health  -> 401 Authentication required
GET /v1/models   -> 401 Invalid API key
```

Then ran a fully closed-environment smoke test using `scripts/freellmapi_closed_env_smoke.py`:

1. Started a local mock OpenAI-compatible provider on `127.0.0.1:43117`.
2. Started FreeLLMAPI on `127.0.0.1:3017`.
3. Captured first-run unified API key from server stdout.
4. Created dashboard account through `/api/auth/setup`.
5. Registered the mock provider through `/api/keys/custom`.
6. Called `/v1/models` with the unified key.
7. Called `/v1/chat/completions` with `model=auto`.

Observed PASS:

```text
PASS: FreeLLMAPI routed model=auto through the local mock custom provider.
Mock provider requests seen: 1
```

Response included:

```json
"_routed_via": {
  "platform": "custom",
  "model": "mock-free-model"
}
```

This proves the sidecar pattern works without real provider keys or external LLM calls.

### Real-provider smoke

Also ran `scripts/freellmapi_real_kilo_smoke.py`, which uses Kilo Gateway's keyless free route. This does make a real external API call, but uses no Davi-owned provider key.

Flow:

1. Started FreeLLMAPI on `127.0.0.1:3018`.
2. Captured generated unified API key.
3. Created dashboard account through `/api/auth/setup`.
4. Added keyless Kilo provider through `/api/keys/`.
5. Called `/v1/chat/completions` with model `stepfun/step-3.7-flash:free`.

Observed result:

```text
chat status: 200
content: ATLAS_REAL_SMOKE_OK
```

Response metadata:

```json
"_routed_via": {
  "platform": "kilo",
  "model": "stepfun/step-3.7-flash:free"
}
```

Usage reported:

```json
{
  "prompt_tokens": 25,
  "completion_tokens": 79,
  "total_tokens": 104
}
```

Caveat: Kilo keyless/free traffic is external and may be logged/trained on. Use only for non-sensitive tests/tasks.

### Security/audit notes

`npm audit` after install reports:

```text
moderate: 4
high: 1
critical: 1
total: 6
```

Notable items and production risk assessment (updated Phase 4.5, 2026-06-08):

| Advisory | Severity | Scope | Production risk to ATLAS |
|----------|----------|-------|--------------------------|
| `vitest` | Critical | Dev dependency only | None — not present in built sidecar binary |
| `esbuild` | Moderate | Dev server only | None — not active when using compiled build |
| `drizzle-orm` | High | Production code (FreeLLMAPI SQLite ORM) | Contained — ATLAS communicates with FreeLLMAPI via HTTP only; ATLAS never provides user-controlled input that becomes a SQL identifier in FreeLLMAPI's ORM. Affects only FreeLLMAPI's own internal SQLite DB. |
| Other moderate (4) | Moderate | Various | Review before distribution |

Net assessment: No advisory creates a direct ATLAS security risk when FreeLLMAPI runs as a loopback-only sidecar. Mitigation: loopback-only bind, no external port exposure, monitor FreeLLMAPI upstream for patch releases. Before any ATLAS distribution that bundles or forks FreeLLMAPI: run full dependency remediation and confirm all advisories are patched.

## Desktop app

Desktop app exists under `desktop/`.

Key facts from its README/package:

- Electron menu-bar/tray app.
- Runs router locally on `127.0.0.1:31415` by default.
- Full dashboard in native window.
- Windows build target exists: `npm run desktop:dist:win`.
- Windows build is documented as config-complete but not heavily tested upstream.
- Requires native build toolchain for `better-sqlite3`.

ATLAS implication: useful as an operator-local model gateway, but not the first integration path. Start with Docker/server sidecar. Desktop can become a later operator convenience package.

## ATLAS integration options

### Option A — Sidecar provider gateway — recommended first

Run FreeLLMAPI separately and configure ATLAS/Hermes to call it as a custom OpenAI-compatible provider.

Shape:

```text
ATLAS/Hermes → http://127.0.0.1:3001/v1 → FreeLLMAPI router → free-tier providers
```

Benefits:

- Minimal ATLAS code impact.
- No TypeScript/Node/Electron dependencies inside Python runtime.
- Keeps upstream project replaceable.
- Works with existing Hermes custom endpoint mechanism: `model.base_url` + `model.api_key`.
- Keeps API keys outside ATLAS database for now.

Risks:

- Another process to supervise.
- Must handle local service health/readiness.
- Free-tier reliability fluctuates.
- ToS constraints vary by provider.

### Option B — ATLAS-managed sidecar supervisor

Add an ATLAS service wrapper that can start/stop/check FreeLLMAPI.

Potential CLI:

```text
atlas provider-gateway status
atlas provider-gateway start
atlas provider-gateway stop
atlas provider-gateway open-dashboard
atlas provider-gateway models
```

This should come after Option A proves value.

### Option C — Hermes plugin

Hermes plugin could expose setup/status tools for FreeLLMAPI.

Useful but not necessary for first pass. Avoid plugin complexity until sidecar behavior is proven.

### Option D — Vendor or fork into ATLAS

Not recommended now.

Reasons:

- Different stack: TypeScript/Node/React/Electron vs ATLAS Python/Rust strategy.
- Fast-moving provider catalog; upstream maintenance is valuable.
- Vendoring increases security and dependency ownership burden.

Fork only if we need custom routing semantics or ATLAS-specific audit hooks that upstream will not accept.

## Operational constraints

- Bind to loopback only: `127.0.0.1`. Do not expose to internet.
- Treat as personal/single-user infrastructure.
- Keep one provider account per provider; do not resell/share endpoint.
- Do not use for production promises or paid client delivery without paid provider fallback.
- Keep upstream provider keys in FreeLLMAPI, not scattered across ATLAS configs.
- Use ATLAS audit layer to record when a FreeLLMAPI route was used and which model/provider served it if headers expose that data.

## Proposed ATLAS Phase 4.5 spike

**Goal:** Prove FreeLLMAPI can serve as a local low-cost inference gateway for ATLAS/Hermes without destabilizing the core runtime.

Success criteria:

1. FreeLLMAPI runs locally via Docker or Node with loopback binding.
2. At least one free/keyless provider route works end-to-end, if available under current provider terms.
3. Hermes custom endpoint can call FreeLLMAPI with `model=auto`.
4. ATLAS can classify a task as `free-tier-ok` vs `paid-required`.
5. AuditEvent captures routed provider/model from response headers where available (`X-Routed-Via`, `X-Fallback-Attempts`).
6. Failure mode is clean: if FreeLLMAPI is down or exhausted, ATLAS falls back to configured primary provider or refuses with clear reason.
7. No provider keys are committed to repo; `.env` examples only.

Recommended first implementation tasks:

1. Add decision record: `D-015-free-tier-provider-gateway.md`.
2. Add docs: `docs/operations/FREELLMAPI_SIDECAR.md`.
3. Add local `.env.example` snippet for FreeLLMAPI endpoint only, no keys.
4. Add ATLAS config fields:
   - `free_gateway.enabled`
   - `free_gateway.base_url`
   - `free_gateway.api_key_env`
   - `free_gateway.allowed_task_classes`
5. Add a small health probe utility.
6. Add one non-critical routing test using mocked OpenAI-compatible responses.

## Recommendation

Proceed, but as an integration spike — not a direct merge into the ATLAS core.

Priority: **High** for ATLAS cost control and autonomy.  
Risk: **Medium** due to provider ToS variability, free-tier instability, and dependency/security hygiene.  
Architecture: **Sidecar first, managed sidecar second, fork/vendor last.**
