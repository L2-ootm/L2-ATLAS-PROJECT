# Deep Integration Analysis — OmniRoute, Page-Agent, Stealth-Browser-MCP

> Generated 2026-07-11 23:30 UTC+2 · Depth: rigorous · 3 repos analyzed against L2 ATLAS architecture

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Repo 1: diegosouzapw/OmniRoute](#2-repo-1-omniroute)
3. [Repo 2: alibaba/page-agent](#3-repo-2-page-agent)
4. [Repo 3: vibheksoni/stealth-browser-mcp](#4-repo-3-stealth-browser-mcp)
5. [Cross-Repo Integration Matrix](#5-cross-repo-integration-matrix)
6. [ATLAS Integration Risk Register](#6-atlas-integration-risk-register)
7. [Recommended Integration Path](#7-recommended-integration-path)
8. [Dependency & Supply Chain Analysis](#8-dependency--supply-chain-analysis)

---

## 1. Executive Summary

| Repo | ATLAS Fit | Verdict | Priority |
|------|-----------|---------|----------|
| **OmniRoute** | Gateway/LLM-routing replacement or augmentation | **HIGH** — could replace FreeLLMAPI sidecar + add 237 provider routing | P1 evaluate |
| **page-agent** | In-page GUI automation tool for agent runtime | **MEDIUM** — fits as a new tool adapter, not core infra | P2 evaluate |
| **stealth-browser-mcp** | Anti-bot browser automation MCP sidecar | **MEDIUM** — complementary to page-agent, MCP-native, but heavy | P3 evaluate |

**Key finding:** OmniRoute is the only repo with genuine structural overlap with ATLAS core infrastructure. page-agent and stealth-browser-mcp are candidate tool adapters (agent capabilities), not architectural replacements.

---

## 2. Repo 1: diegosouzapw/OmniRoute

**Stars:** 15.7k · **License:** MIT · **Forks:** 2.4k · **Commits:** 4,550 · **Version:** 3.8.46

### 2.1 Architecture

**Tech Stack:**
- **Runtime:** Node.js 22+ (also supports 24-26), TypeScript 6.x
- **Framework:** Next.js 16 (React 19) for dashboard + API routes
- **Database:** SQLite via sql.js + optional better-sqlite3; sqlite-vec for vector search; Redis (ioredis) optional for rate limiting
- **Build:** pnpm workspaces; tsx for dev; Turbopack (optional dev bundler)
- **Testing:** Node test runner (unit), Vitest (MCP), Playwright (E2E), Stryker (mutation), c8 (coverage)
- **Desktop:** Electron wrapper
- **Deployment:** Docker, Docker Compose, Fly.io, Podman, npm package, PWA

**Data Flow:**
```
IDE/CLI (Claude Code, Cursor, etc.)
  → HTTP proxy (localhost:20128/v1)
  → OmniRoute Smart Router
    → Compression pipeline (RTK + Caveman, 10 composable engines)
    → 17 routing strategies (priority, cost-optimized, auto, fusion, etc.)
    → Circuit breakers + model lockout + connection cooldown
    → Provider connections (237 providers, 90+ free)
      → TLS fingerprint stealth (JA3/JA4 via wreq-js)
      → SOCKS5/HTTP proxy support
    → Response with cost/usage telemetry headers
```

**Source Structure:**
- `src/app/` — Next.js app routes (dashboard + API)
- `src/server/` — Custom Express server, CORS, authz, WebSocket
- `src/lib/` — Core: DB, auth, config, provider credentials, compression, guardrails
- `src/sse/` — SSE streaming handlers
- `open-sse/` — Standalone SSE/proxy module (separate workspace)
- `src/mitm/` — MITM/TPROXY transparent decrypt
- `@omniroute/` — CLI package
- `electron/` — Desktop wrapper
- `config/` — Quality gates, ESLint, provider config

### 2.2 API Surface

**Endpoints (OpenAI-compatible proxy):**
- `POST /v1/chat/completions` — Main proxy endpoint
- `POST /v1/responses` — OpenAI Responses API compat
- `POST /v1/embeddings` — Embedding proxy
- `GET /v1/models` — Available models
- `POST /api/mcp` — Built-in MCP server (95 tools, 3 transports, 30 scopes)
- Dashboard routes (Next.js): settings, combos, usage, health, providers, keys, etc.

**MCP Tools (95):** Health, combos, models, routing, budget, metrics, pricing, memory, skills, admin

**CLI:** `omniroute` binary — setup-*, launch, connect, contexts, tokens, login, serve

**A2A Protocol:** 6 skills via JSON-RPC 2.0

**Key Environment Variables (critical subset):**
- `JWT_SECRET`, `API_KEY_SECRET` — Required security secrets
- `INITIAL_PASSWORD` — Bootstrap admin password
- `PORT` (default 20128) — Main listen port
- `STORAGE_ENCRYPTION_KEY` — DB encryption at rest
- `REQUIRE_API_KEY` — API key enforcement
- `ENABLE_TLS_FINGERPRINT` — JA3/JA4 stealth
- `ENABLE_SOCKS5_PROXY` — Proxy support
- `TOOL_POLICY_MODE` — Tool allowlist/denylist
- `INPUT_SANITIZER_ENABLED` — Prompt injection guard
- `PII_REDACTION_ENABLED` — PII protection
- `OMNIROUTE_ALLOW_PRIVATE_PROVIDER_URLS` — Local provider access
- 100+ additional env vars documented in `.env.example`

### 2.3 Quality Assessment

**Tests:**
- 21,000+ tests claimed
- Unit tests: Node test runner with shard support
- Integration tests: combo matrix, chaos resilience, heap growth
- E2E: Playwright
- Mutation testing: Stryker
- Coverage: c8 with 60% statement/line/function/branch thresholds
- Security: npm audit, CodeQL ratchet, Trivy, Snyk (socket.yml)
- Linting: ESLint (SonarJS plugin), Prettier, Vale (prose), markdownlint
- 60+ `check:*` scripts for code quality gates (cycles, dead code, complexity, type coverage, license compliance, secrets, etc.)

**Security Features:**
- Prompt injection guard (request-side)
- PII detection/redaction (request + response)
- SSRF guard (outbound URL validation)
- API key encryption at rest (AES)
- JWT session tokens
- Rate limiting (in-memory or Redis)
- CORS policy
- Body size guard with heap-pressure admission
- VS Code context sanitizer
- `.gitleaks.toml`, `.trivyignore` configs

**Maintenance:**
- Very active: 4,550 commits, 45 open PRs, 166 issues
- CHANGELOG maintained
- AGENTS.md, CLAUDE.md, GEMINI.md (AI coding agent docs)
- Contributing guidelines
- Security policy
- 42 language translations

### 2.4 ATLAS Fit

**Maps to:** Gateway layer (`native/atlas-core-rs/`) + FreeLLMAPI sidecar

**Gap filled:**
1. **Provider routing** — OmniRoute's 237 providers + 17 routing strategies + auto-fallback could replace FreeLLMAPI's 18 free providers entirely, or augment ATLAS's provider mesh
2. **Token compression** — RTK + Caveman compression (15-95% savings) is a capability ATLAS completely lacks
3. **MCP server** — 95-tool MCP server could serve as ATLAS's tool surface
4. **Guardrails** — PII, injection, vision guardrails overlap with ATLAS's audit-first design
5. **Cost telemetry** — X-OmniRoute-* headers per request

**Integration options:**
- **Option A (sidecar replacement):** Replace FreeLLMAPI sidecar with OmniRoute as the unified LLM gateway. ATLAS gateway :8484 routes to OmniRoute :20128 instead of :3001. Pros: massive provider coverage, compression, fallback. Cons: Node.js dependency, heavy footprint, Next.js dashboard conflicts with ATLAS cockpit.
- **Option B (library extraction):** Extract only the compression pipeline (RTK + Caveman engines) and provider routing logic. Import as npm package or rewrite compression as Python/Rust. Pros: targeted capability gain. Cons: significant extraction work.
- **Option C (proxy chain):** ATLAS gateway → OmniRoute :20128 → providers. OmniRoute becomes the provider abstraction layer. Pros: minimal ATLAS code changes. Cons: adds a hop, two Node.js processes.

**Recommendation:** Option C initially (proxy chain), evaluate Option B for compression extraction.

### 2.5 Risk

| Risk | Severity | Notes |
|------|----------|-------|
| **Supply chain: 170+ npm deps** | HIGH | Massive attack surface. Key deps: express, next, ws, zod, sql.js, jose, bcryptjs, undici. Optional native: better-sqlite3, wreq-js, keytar. Must pin and audit. |
| **Supply chain: git dep** | LOW | No git deps in OmniRoute |
| **Node.js 22+ requirement** | MEDIUM | ATLAS is Python-first (D-013/D-022). Adding a Node.js 22+ runtime requirement is non-trivial on Windows. |
| **Next.js framework weight** | HIGH | Full Next.js 16 app is ~300MB+ with deps. Overkill for a sidecar. |
| **License: MIT** | CLEAR | No issues |
| **Maintenance bus factor** | MEDIUM | Primarily single author (diegosouzapw), but very active |
| **Conflict with ATLAS gateway** | HIGH | Both are HTTP servers; port conflicts, routing confusion, auth model mismatch |

---

## 3. Repo 2: alibaba/page-agent

**Stars:** 26k · **License:** MIT · **Forks:** 2.4k · **Commits:** 1,104 · **Version:** 1.12.1

### 3.1 Architecture

**Tech Stack:**
- **Runtime:** Node.js 22+ / TypeScript 6.x
- **Framework:** Vite 8 + custom build scripts
- **Packages (monorepo):** 8 workspace packages
- **Testing:** Vitest 4.x, happy-dom
- **Linting:** ESLint 10 + Prettier
- **Build:** Custom `scripts/build.js` + Vite

**Monorepo Structure:**
```
packages/
  core/          — Core agent logic, DOM processing, prompt construction
  page-agent/    — Main npm package (PageAgent class)
  page-controller/ — Browser automation controller
  llms/          — LLM provider adapters (BYO model support)
  ui/            — Chat widget UI (React-based)
  mcp/           — MCP Server (Beta)
  extension/     — Chrome Extension for multi-page tasks
  website/       — Documentation site
```

**Data Flow:**
```
Web Page
  → Inject <script> tag (page-agent.js)
  → PageAgent class initializes
  → User speaks natural language
  → Core processes DOM (text-based, no screenshots)
  → LLM adapter routes to configured model
  → Agent actions executed in-page
  → Chrome Extension (optional) handles multi-tab
  → MCP Server (optional) exposes control externally
```

**Key Innovation:** Text-based DOM manipulation — no screenshots, no multimodal LLMs needed. Works with most mainstream models including local deployments.

### 3.2 API Surface

**NPM Package API:**
```typescript
import { PageAgent } from 'page-agent'
const agent = new PageAgent({
  model: 'qwen3.5-plus',
  baseURL: 'https://...',
  apiKey: 'YOUR_KEY',
  language: 'en-US',
})
await agent.execute('Click the login button')
```

**MCP Server (Beta):**
- Exposes page-agent as MCP tools for external control
- Package: `packages/mcp`

**Chrome Extension:**
- Multi-page task handling
- Bridge between extension context and page agent

**CDN (one-line integration):**
```html
<script src="https://cdn.jsdelivr.net/npm/page-agent@1.12.1/dist/iife/page-agent.demo.js"></script>
```

**Key Capabilities:**
- Smart form filling (20-click workflows → one sentence)
- Accessibility (voice commands, screen readers)
- SaaS AI copilot embedding
- Multi-page agent via extension
- BYO LLM (any OpenAI-compatible endpoint)

**Environment Variables:**
- Standard LLM provider keys (BYO)
- Demo mode uses testing LLM API (terms apply)

### 3.3 Quality Assessment

**Tests:**
- CI: GitHub Actions (`main-ci.yml`)
- Per-workspace test suites via `npm test --workspaces`
- `typecheck` across all packages
- Lint: ESLint + Prettier with import sorting
- Bundle size checked via bundlephobia

**Security:**
- Chrome Web Store rating visible
- MIT license with clear attribution to browser-use
- Standard npm security practices
- `.github/` directory (security policy referenced)

**Maintenance:**
- Alibaba-backed (alibaba organization on GitHub)
- Active: 36 releases, v1.12.1 latest (Jul 10, 2026)
- AGENTS.md, CLAUDE.md present
- CONTRIBUTING.md with contributor guidelines
- Clear maintainer's note on principles

### 3.4 ATLAS Fit

**Maps to:** Tool adapter layer (`services/agent-runtime/atlas_runtime/tools/adapters/`)

**Gap filled:**
1. **In-page GUI automation** — ATLAS has no browser interaction capability. page-agent provides text-based DOM manipulation without headless browser overhead
2. **Web copilot** — Could power an ATLAS web surface where users interact with pages via natural language
3. **Form automation** — Useful for mission workflows that involve web form submission
4. **Accessibility** — Natural language web control for the cockpit

**Integration options:**
- **Option A (npm package):** Import `page-agent` as a Node.js dependency, expose via Python subprocess bridge (like FreeLLMAPI). New tool adapter `browser_page_agent`.
- **Option B (MCP server):** Run page-agent's MCP server as a sidecar, expose its tools via ATLAS's MCP tool manifest.
- **Option C (CDN injection):** Inject the script into ATLAS cockpit pages for in-browser agent capabilities. Only works in web surfaces.

**Recommendation:** Option B (MCP server sidecar) aligns with ATLAS's existing sidecar pattern (D-015).

### 3.5 Risk

| Risk | Severity | Notes |
|------|----------|-------|
| **Supply chain: npm deps** | LOW | Lightweight: Vite, TypeScript, ESLint, Vitest. No heavy runtime deps. |
| **Supply chain: git dep** | NONE | No git dependencies |
| **Client-side only** | HIGH | page-agent runs IN the web page. ATLAS's agent runtime is server-side Python. Bridging requires a transport layer. |
| **Alibaba governance** | LOW | Corporate-backed, MIT licensed, clear contribution policy |
| **MCP Beta status** | MEDIUM | MCP package is labeled Beta — API may change |
| **Demo API terms** | LOW | Demo CDN uses a testing API with terms. Production use requires own LLM keys. |
| **License: MIT** | CLEAR | No issues. Attribution to browser-use included. |

---

## 4. Repo 3: vibheksoni/stealth-browser-mcp

**Stars:** 1.5k · **License:** MIT · **Forks:** 227 · **Commits:** 44 · **Version:** 0.2.5

### 4.1 Architecture

**Tech Stack:**
- **Runtime:** Python 3.10+
- **MCP Framework:** FastMCP 2.11.2
- **Browser Engine:** nodriver 0.47.0 (undetected Chrome driver) + Chrome DevTools Protocol
- **Data Models:** Pydantic 2.11.7
- **Other:** uvicorn (HTTP transport), psutil, Pillow, requests, py2js (Python-JS bridge)

**Data Flow:**
```
MCP Client (Claude Code, Cursor, etc.)
  → stdio or HTTP transport
  → FastMCP Server (server.py)
  → 97 tools across 11 sections
  → nodriver (undetectable Chrome)
  → Chrome DevTools Protocol (CDP)
  → Target website (bypasses Cloudflare, Queue-It, etc.)
  → Results: screenshots, DOM data, network captures, cloned elements
```

**Source Structure:**
```
src/
  server.py                        — FastMCP server entry point
  browser_manager.py               — Browser lifecycle (spawn, reap, idle timeout)
  dom_handler.py                   — DOM query and interaction
  element_cloner.py                — Element extraction (basic)
  cdp_element_cloner.py            — CDP-based pixel-accurate cloning
  cdp_function_executor.py         — CDP command execution + JS function calls
  comprehensive_element_cloner.py  — Full element clone with all CSS/DOM/events
  progressive_element_cloner.py    — On-demand expansion of cloned elements
  file_based_element_cloner.py     — File-backed extraction persistence
  network_interceptor.py           — Network request/response capture
  dynamic_hook_system.py           — AI-generated Python hooks for traffic interception
  dynamic_hook_ai_interface.py     — LLM interface for hook generation
  hook_learning_system.py          — Hook pattern learning
  http_security.py                 — HTTP transport auth (bearer token)
  file_upload_security.py          — Allowlisted directory enforcement
  platform_utils.py                — Cross-platform browser detection
  process_cleanup.py               — Orphan process cleanup
  debug_logger.py                  — Debug logging to stderr
  persistent_storage.py            — Element storage
  proxy_forwarder.py               — Proxy support
  proxy_utils.py                   — Proxy utilities
  response_handler.py              — Response formatting
  response_stage_hooks.py          — Response interception hooks
  models.py                        — Pydantic models
  js/                              — JavaScript helpers
```

**Modular Architecture:**
- **Full mode:** 97 tools (11 sections)
- **Minimal mode:** 20 core tools (`--minimal`)
- **Custom mode:** Disable specific sections (`--disable-*`)

### 4.2 API Surface

**97 MCP Tools across 11 Sections:**

| Section | Tools | Description |
|---------|-------|-------------|
| browser-management | 8 | spawn, navigate, close, list, state, back, forward, reload |
| element-interaction | 12 | query, click, type, paste, file_upload, scroll, wait, execute_script, select, state, content, screenshot |
| element-extraction | 9 | CDP clone, styles, structure, events, animations, assets, related files |
| file-extraction | 9 | Save extraction results to files |
| network-debugging | 10 | List/search requests, headers, payloads, responses, hooks |
| cdp-functions | 14 | Direct CDP, script injection, function discovery/execution, bindings |
| progressive-cloning | 10 | On-demand element expansion (styles, events, children, CSS, pseudo, animations) |
| cookies-storage | 3 | Cookie read/write/clear |
| tabs | 5 | Tab management |
| debugging | 7 | Screenshots, page content, debug view, hot reload, validation |
| dynamic-hooks | 10 | AI-generated Python functions for real-time traffic interception |

**Environment Variables:**
- `STEALTH_BROWSER_MCP_AUTH_TOKEN` — HTTP transport auth
- `BROWSER_IDLE_TIMEOUT` — Auto-close idle browsers (default 600s)
- `BROWSER_IDLE_REAPER_INTERVAL` — Reaper cadence (default 60s)
- `BROWSER_ORPHAN_PROFILE_MAX_AGE` — Stale profile cleanup (default 21600s)
- `BROWSER_FILE_UPLOAD_ALLOWED_DIRS` — File upload allowlist
- `STEALTH_BROWSER_DEBUG` — Debug logging

**Transports:**
- `stdio` (recommended for local MCP clients)
- HTTP (with optional bearer token auth)

### 4.3 Quality Assessment

**Tests:**
- `STEALTH_TESTS.md` — Stealth bypass test documentation
- `validate_browser_environment_tool()` — Runtime environment diagnostics
- No visible CI pipeline (only 44 commits, early stage)
- Dev deps: pytest, pytest-asyncio, black, isort, mypy

**Security:**
- HTTP auth via bearer token (STEALTH_BROWSER_MCP_AUTH_TOKEN)
- File upload directory allowlisting (BROWSER_FILE_UPLOAD_ALLOWED_DIRS)
- Orphan process cleanup (startup sweep)
- Idle browser reaping
- `--sandbox=false` for container environments
- SECURITY.md present
- CODEOWNERS file present

**Maintenance:**
- Solo developer (vibheksoni)
- Early stage: 44 commits, 1 open issue, 0 PRs
- ROADMAP.md with active plans
- CHANGELOG.md maintained
- Active Discord community (discord.gg/secrets)

### 4.4 ATLAS Fit

**Maps to:** Tool adapter layer + MCP sidecar

**Gap filled:**
1. **Anti-bot bypass** — ATLAS's `web_fetch` tool uses plain `urllib.request` — no Cloudflare bypass, no bot detection evasion
2. **CDP-level browser control** — Full Chrome DevTools Protocol access for complex automation
3. **Network interception** — Request/response capture for API reverse engineering
4. **Element cloning** — Pixel-perfect extraction for UI analysis
5. **Dynamic hooks** — AI-generated network traffic modification

**Integration options:**
- **Option A (MCP sidecar):** Run stealth-browser-mcp as a managed sidecar (like FreeLLMAPI). Expose its tools via ATLAS's tool manifest + Python adapter bridge.
- **Option B (library import):** Import `nodriver` + `fastmcp` directly into ATLAS's agent-runtime. Write a Python adapter that wraps the core capabilities.
- **Option C (tool adapter):** Create `stealth_browser` tool adapter in `atlas_runtime/tools/adapters/` that communicates with the running MCP server via HTTP transport.

**Recommendation:** Option C (tool adapter with HTTP transport sidecar). Aligns with existing patterns and keeps ATLAS lean.

### 4.5 Risk

| Risk | Severity | Notes |
|------|----------|-------|
| **Supply chain: py2js git dep** | HIGH | `py2js @ git+https://github.com/am230/py2js.git@31a83c7` — pinned to a specific commit, but git deps are a supply chain red flag |
| **Supply chain: nodriver** | MEDIUM | nodriver is a fork of undetected-chromedriver; small community, could be abandoned |
| **Supply chain: fastmcp** | LOW | Popular MCP framework, actively maintained |
| **Solo maintainer** | HIGH | 44 commits, 1 open issue, 0 PRs. Bus factor = 1. |
| **Anti-bot legality** | MEDIUM | Bypassing Cloudflare/Queue-It may violate ToS. Legal review needed for production use. |
| **Browser resource usage** | MEDIUM | Full Chrome instances consume significant RAM. Multiple instances = high memory. |
| **License: MIT** | CLEAR | No issues |
| **Early maturity** | HIGH | v0.2.5, 44 commits. API may break. |

---

## 5. Cross-Repo Integration Matrix

### 5.1 Capability Overlap

| Capability | ATLAS Current | OmniRoute | page-agent | stealth-browser-mcp |
|------------|---------------|-----------|------------|---------------------|
| LLM routing | Provider mesh (Python) | 237 providers, 17 strategies | BYO (client-side) | None |
| Token compression | None | RTK + Caveman (15-95%) | None | None |
| MCP server | None (tool manifests) | 95 tools | Beta | 97 tools |
| Browser automation | `web_fetch` (urllib GET) | Playwright (E2E only) | In-page JS agent | CDP + nodriver |
| SSRF protection | `_assert_safe` (DNS check) | Outbound URL guard | Client-side only | None |
| PII protection | None | Request + response guards | None | None |
| Guardrails | Audit-first design | Injection + PII + vision | None | File upload allowlist |
| GUI automation | None | None | Full (text-based DOM) | Full (CDP-based) |
| Stealth/bypass | None | TLS fingerprint (JA3/JA4) | None | Cloudflare + Queue-It bypass |
| Cost tracking | None | Per-request USD headers | None | None |
| Provider fallback | Single provider | 4-tier auto-fallback | None | None |

### 5.2 Language & Runtime Compatibility

| Repo | Language | ATLAS Compatibility | Migration Path |
|------|----------|---------------------|----------------|
| OmniRoute | TypeScript/Node.js | **Conflict** — ATLAS is Python + Rust (D-013/D-022). Node.js 22+ adds a third runtime. | Extract compression/routing as Python package, or run as sidecar |
| page-agent | TypeScript/Node.js | **Compatible** — Client-side only, no runtime conflict. Can be loaded as script. | npm install, expose via MCP sidecar or CDN injection |
| stealth-browser-mcp | Python 3.10+ | **Compatible** — Same language, same Pydantic v2. Direct import possible. | Import nodriver + fastmcp, write adapter |

### 5.3 Integration Effort Estimate

| Repo | Effort | Complexity | Value |
|------|--------|------------|-------|
| OmniRoute (sidecar) | 2-3 days | Low | HIGH |
| OmniRoute (library extraction) | 2-3 weeks | High | HIGH |
| page-agent (MCP sidecar) | 1-2 days | Low | MEDIUM |
| page-agent (CDN injection) | 1 day | Very Low | LOW |
| stealth-browser-mcp (adapter) | 1-2 days | Low | MEDIUM |
| stealth-browser-mcp (import) | 3-5 days | Medium | MEDIUM |

---

## 6. ATLAS Integration Risk Register

### 6.1 OmniRoute Risks

| ID | Risk | Mitigation |
|----|------|------------|
| O-1 | **Node.js runtime proliferation** — Adds third runtime to Python+Rust stack | Containerize or extract only the compression module |
| O-2 | **Next.js framework bloat** — 300MB+ for a sidecar is excessive | Use only the CLI/backend mode (`build:backend`), not the dashboard |
| O-3 | **Port conflict** — OmniRoute :20128 vs ATLAS :8484 vs FreeLLMAPI :3001 | Configure OmniRoute on a non-conflicting port; document port map |
| O-4 | **Auth model mismatch** — OmniRoute uses JWT sessions + API keys; ATLAS uses gateway tokens + owner tokens | Don't merge auth models; use internal-only proxy auth |
| O-5 | **170+ dependency attack surface** | Pin versions, run `npm audit` in CI, consider SBOM generation |
| O-6 | **Provider credential exposure** — OmniRoute stores API keys in SQLite with AES | Ensure ATLAS never passes real keys through OmniRoute unless intended |

### 6.2 page-agent Risks

| ID | Risk | Mitigation |
|----|------|------------|
| P-1 | **Client-side only architecture** — Runs IN the web page, not server-side | Bridge via MCP server or HTTP transport |
| P-2 | **BYO LLM dependency** — Needs its own LLM keys separate from ATLAS provider mesh | Route page-agent LLM calls through ATLAS gateway |
| P-3 | **MCP Beta stability** — API may change | Pin version, write adapter with fallback |
| P-4 | **Browser extension governance** — Chrome Web Store review delays | Extension is optional; core works without it |

### 6.3 stealth-browser-mcp Risks

| ID | Risk | Mitigation |
|----|------|------------|
| S-1 | **py2js git dependency** — Supply chain vulnerability | Replace with stable PyPI package or vendor |
| S-2 | **Solo maintainer** — 44 commits, bus factor 1 | Fork and maintain internally if adopted |
| S-3 | **Anti-bot legality** — Bypassing Cloudflare may violate ToS | Legal review before production deployment |
| S-4 | **Chrome resource consumption** — Multiple instances = high RAM | Implement instance pooling + idle reaping (already has this) |
| S-5 | **nodriver fork stability** — Depends on upstream Chrome updates | Monitor, pin versions, have fallback plan |

---

## 7. Recommended Integration Path

### Phase 1: OmniRoute as Provider Gateway (Week 1)

**Action:** Run OmniRoute as a sidecar on port 20128 (backend-only mode). ATLAS gateway :8484 proxies LLM calls to OmniRoute :20128.

**Files to create:**
- `services/atlas-omniroute/` — Sidecar control module (mirroring `freellmapi_control.py`)
- `atlas_runtime/tools/adapters/omniroute_proxy.py` — Tool adapter for provider routing
- `atlas_runtime/tools/manifests/omniroute.yaml` — Tool manifest

**Config changes:**
- Add `ATLAS_OMNIROUTE_DIR` env var
- Add `ATLAS_OMNIROUTE_PORT` (default 20128)
- Add OmniRoute routes to Rust gateway (`/v1/omniroute/*` dispatch-only)

**Verification:** ATLAS agent can route LLM calls through OmniRoute with auto-fallback enabled.

### Phase 2: Compression Extraction (Week 2-3)

**Action:** Extract OmniRoute's RTK + Caveman compression engines as a standalone Python or Rust module.

**Target:** Port the compression pipeline to Python (using existing Pydantic models) or Rust (native/atlas-core-rs). This gives ATLAS token compression without the full OmniRoute dependency.

**Files to create:**
- `atlas_runtime/compression/` — Python compression engines
- Or `native/atlas-compression-rs/` — Rust compression crate

**Verification:** ATLAS agent can compress prompts by 30-60% before sending to providers.

### Phase 3: Stealth Browser Sidecar (Week 3-4)

**Action:** Run stealth-browser-mcp as a managed sidecar. Create a tool adapter that bridges ATLAS tools to MCP.

**Files to create:**
- `services/stealth-browser/` — Sidecar control module
- `atlas_runtime/tools/adapters/stealth_browser.py` — MCP bridge adapter
- `atlas_runtime/tools/manifests/stealth_browser.yaml` — Tool manifest

**Verification:** ATLAS agent can browse anti-bot-protected sites and extract data.

### Phase 4: Page Agent Integration (Week 4-5)

**Action:** Install page-agent as an npm dependency. Expose via MCP server sidecar or inject into ATLAS cockpit.

**Files to create:**
- `services/page-agent/` — Sidecar control module
- `atlas_runtime/tools/adapters/page_agent.py` — Bridge adapter
- `atlas_runtime/tools/manifests/page_agent.yaml` — Tool manifest

**Verification:** ATLAS agent can interact with web pages using natural language.

---

## 8. Dependency & Supply Chain Analysis

### 8.1 OmniRoute Critical Dependencies

| Package | Version | Risk | Notes |
|---------|---------|------|-------|
| next | 16.2.6 | MEDIUM | Major framework; update velocity high |
| express | 5.2.1 | LOW | Stable, well-audited |
| @modelcontextprotocol/sdk | 1.29.0 | LOW | Official MCP SDK |
| sql.js | 1.14.1 | LOW | SQLite WASM; stable |
| jose | 6.2.3 | LOW | JWT library; well-maintained |
| bcryptjs | 3.0.3 | LOW | Password hashing |
| undici | 8.3.0 | LOW | Node.js HTTP client |
| ws | 8.18.0 | LOW | WebSocket; stable |
| zod | 4.4.3 | LOW | Schema validation |
| better-sqlite3 | 12.10.0 | MEDIUM | Native SQLite; optional |
| wreq-js | 2.3.1 | HIGH | TLS fingerprint spoofing; niche |
| keytar | 7.9.0 | MEDIUM | Native credential storage; optional |
| @ngrok/ngrok | 1.7.0 | MEDIUM | Tunnel; optional |

### 8.2 page-agent Dependencies

| Package | Version | Risk | Notes |
|---------|---------|------|-------|
| vite | 8.1.4 | LOW | Build tool; well-audited |
| typescript | 6.0.3 | LOW | Language compiler |
| vitest | 4.1.10 | LOW | Test framework |
| happy-dom | 20.10.6 | LOW | DOM simulation for tests |

**Verdict:** Very lightweight dependency tree. Minimal risk.

### 8.3 stealth-browser-mcp Dependencies

| Package | Version | Risk | Notes |
|---------|---------|------|-------|
| fastmcp | 2.11.2 | LOW | MCP framework; popular |
| nodriver | 0.47.0 | HIGH | Fork of undetected-chromedriver; niche |
| pydantic | 2.11.7 | LOW | Data validation |
| python-dotenv | 1.1.1 | LOW | Env loading |
| **py2js** | **git+commit** | **CRITICAL** | **Git dependency pinned to specific commit. Supply chain risk.** |
| jsbeautifier | 1.15.4 | LOW | JS formatting |
| strinpy | 0.0.4 | LOW | String processing |
| strbuilder | 1.1.3 | LOW | String building |
| psutil | 7.0.0 | LOW | Process utilities |
| pillow | 11.3.0 | LOW | Image processing |
| requests | 2.33.1 | LOW | HTTP client |
| uvicorn | 0.35.0 | LOW | ASGI server |

**Critical finding:** `py2js` is a git dependency (`git+https://github.com/am230/py2js.git@31a83c7`). This is a direct supply chain risk. If the commit is force-pushed or the repo is compromised, builds silently change. Must be vendored or replaced with a PyPI package before production use.

### 8.4 ATLAS Approved Dependencies (D-013/D-022)

Per AGENTS.md, approved Python deps are: `pydantic`, `prompt_toolkit`, `rich`, `pytest`, `ruff`.

**Compatibility:**
- OmniRoute: Node.js — NOT in approved list; requires decision
- page-agent: TypeScript/Node.js — NOT in approved list; optional (client-side only)
- stealth-browser-mcp: Python — `pydantic` OK; `fastmcp`, `nodriver`, `uvicorn` need approval

---

## Appendix: ATLAS Existing Integration Surface

**Current tool adapters:**
- `web_fetch` — GET-only HTTP with SSRF guard (82 lines)
- `workspace` — File operations with boundary enforcement
- `github` — GitHub CLI integration
- `webhook_notify` — HTTP webhook (approval-gated)
- `golden_review_write` — Review output writer

**Current sidecars:**
- FreeLLMAPI (Node.js, :3001) — 18 free providers
- Discord bot (Node.js) — Read/write operations
- Cashflow (Next.js, :3000) — Financial tracking

**Gateway routes (Rust, :8484):**
- 79 paths / 86 endpoints
- Dispatch-only pattern: Rust gateway → Python CLI subprocess
- `/v1/freellmapi/*` — Sidecar management
- `/v1/models/refresh` — Registry refresh
- Auth: owner tokens, surface ownership

**Key architectural constraint (D-022):**
> Rust-first for new infrastructure. Python confined to Hermes foundation surface, LLM adapters, and throwaway scripts.

This means:
- OmniRoute integration MUST go through Python adapter (not Rust rewrite)
- Stealth-browser-mcp integration is Python-native (OK per D-022)
- page-agent integration can be Node.js sidecar (like FreeLLMAPI)

---

*End of report. File saved to `.planning/ultra/ULTRARESEARCH-deep-omniroute-browser-2026-07-11.md`*
