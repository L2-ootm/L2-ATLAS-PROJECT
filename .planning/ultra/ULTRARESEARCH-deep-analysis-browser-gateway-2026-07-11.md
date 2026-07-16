# Deep Analysis: page-agent + stealth-browser-mcp + OmniRoute

**Date:** 2026-07-11  
**Purpose:** Rigorous technical analysis for ATLAS tool/gateway integration

---

## 1. alibaba/page-agent — In-Page GUI Agent (26k stars)

### Architecture
- **Language:** TypeScript (82.6%), JavaScript (11.8%)
- **Runtime:** Browser (no server required), npm package
- **Approach:** Text-based DOM manipulation (no screenshots, no multi-modal LLM)
- **LLM integration:** Bring your own (OpenAI-compatible API)
- **Chrome extension:** Optional, for multi-page tasks
- **MCP Server:** Beta — control from external agents

### How It Works
1. Script injected into web page (`<script src="page-agent">`)
2. Agent reads DOM as text (accessibility tree)
3. LLM decides actions (click, fill, scroll, navigate)
4. Actions executed via standard DOM APIs
5. No headless browser needed — runs in-page

### MCP Tools
- Page navigation, element interaction, form filling
- DOM inspection, screenshot capture
- Multi-page coordination via Chrome extension

### Quality
- **Tests:** CI with GitHub Actions
- **Maintenance:** 1,104 commits, 2.4k forks, Alibaba-backed
- **Security:** DOMPurify for output sanitization
- **Bundle:** Minified for web delivery

### ATLAS Fit
- **Gap addressed:** ATLAS web_fetch is basic HTTP GET. This enables interactive web automation.
- **Integration:** Register as ATLAS tool via manifest. Agent calls page-agent for form filling, data extraction, UI testing.
- **Advantage:** No headless browser dependency — runs in-page
- **Limitation:** Requires page to load in browser (not for server-side automation)
- **Effort:** MEDIUM — needs ATLAS tool manifest + adapter
- **License:** MIT

### Risk
- **Security:** In-page execution = full DOM access — needs SSRF-style guards
- **Alibaba backing:** Corporate — MEDIUM risk
- **Maintenance:** Active — LOW risk

---

## 2. vibheksoni/stealth-browser-mcp — Stealth Browser (1.5k stars)

### Architecture
- **Language:** Python (93.7%)
- **Runtime:** Python venv + Chrome/Chromium/Edge
- **Core:** nodriver (undetected Chrome) + Chrome DevTools Protocol + FastMCP
- **Transport:** stdio (MCP) or HTTP
- **Tools:** 97 tools across 11 sections

### Tool Sections (97 tools)

| Section | Tools | Description |
|---------|-------|-------------|
| browser-management | 8 | Core operations (spawn, navigate, close) |
| element-interaction | 12 | Click, type, scroll, wait, screenshot |
| element-extraction | 9 | CDP-based complete element cloning |
| file-extraction | 9 | Save extractions to files |
| network-debugging | 10 | Request/response inspection, blocking |
| cdp-functions | 14 | Direct CDP command execution |
| progressive-cloning | 10 | On-demand expansion of cloned elements |
| cookies-storage | 3 | Cookie/storage management |
| tabs | 5 | Multi-tab management |
| debugging | 7 | Debug views, logs, hot reload |
| dynamic-hooks | 10 | AI-generated Python network interceptors |

### Anti-Bot Capabilities
- **Cloudflare bypass:** Consistently bypasses
- **Queue-It bypass:** Works
- **Banking/Gov portals:** Works (where Playwright fails)
- **Social media:** Full automation (where others get blocked)

### Quality
- **Tests:** STEALTH_TESTS.md with bypass verification
- **Security:** Bearer token auth for HTTP, file upload allowlisting
- **Maintenance:** 44 commits, 227 forks, smaller community
- **Modular:** Can run with 20-97 tools (customizable)

### ATLAS Fit
- **Gap addressed:** ATLAS web_fetch cannot handle anti-bot sites. This can.
- **Integration:** Register as high-power ATLAS tool. Use for Research Brief web_fetch variant (fills INCOMP-3).
- **Use cases:** Competitive research, API reverse engineering, market data extraction
- **Effort:** MEDIUM — needs ATLAS tool manifest + adapter
- **License:** MIT

### Risk
- **Ethical:** Anti-bot bypass — must document authorized use only
- **Security:** CDP gives full browser control — needs sandboxing
- **Maintenance:** Smaller community — MEDIUM risk
- **Dependencies:** Python venv + Chrome — heavier than page-agent

---

## 3. diegosouzapw/OmniRoute — AI Gateway (15.7k stars)

### Architecture
- **Language:** TypeScript (94.1%)
- **Runtime:** Node.js 22+, Docker, Electron desktop
- **Providers:** 237+ (90+ free tiers aggregated)
- **Token savings:** RTK + Caveman stacked compression (15-95%)
- **Features:** Smart auto-fallback, MCP/A2A, multimodal APIs

### Provider Catalog
- **Free tiers:** ~1.6B tokens/month aggregated
- **Provider pools:** OpenAI, Anthropic, Google, Groq, DeepSeek, Qwen, SiliconFlow, etc.
- **Routing:** 17 routing strategies, combo chains
- **Compression:** RTK engine, Caveman engine, headroom, LLMLingua, session-dedup

### Key Difference from FreeLLMAPI
| Feature | FreeLLMAPI | OmniRoute |
|---------|-----------|-----------|
| Providers | Limited | 237+ |
| Free tiers | Few | 90+ |
| Compression | None | RTK+Caveman (15-95%) |
| Auto-fallback | Basic | Smart multi-provider |
| MCP support | No | Yes |
| Desktop app | No | Electron PWA |
| Maintenance | Stale | Very active (4,550 commits) |
| Community | Small | 280+ contributors |

### Quality
- **Tests:** Vitest + Playwright E2E + Stryker mutation testing
- **Security:** Gitleaks, Trivy, SonarQube, Helmet.js, SSRF protection
- **Maintenance:** 4,550 commits, 2.4k forks, 275 releases, very active
- **CI:** GitHub Actions with full pipeline

### ATLAS Fit
- **Gap addressed:** FreeLLMAPI is stale, limited providers, no compression
- **Integration options:**
  - (a) Replace FreeLLMAPI entirely with OmniRoute
  - (b) Merge best of both (OmniRoute catalog + ATLAS integration layer)
  - (c) Ship both, operator chooses
- **Recommended:** Option (b) — use OmniRoute's provider catalog and compression in ATLAS's existing provider mesh
- **Effort:** HIGH — different architecture (Next.js vs Node sidecar), needs full adapter layer
- **License:** MIT

### Risk
- **Supply chain:** 237 providers = many third-party API keys — needs careful secret management
- **Compression:** RTK+Caveman is lossy — may affect agent output quality
- **Complexity:** Much larger codebase than FreeLLMAPI — maintenance burden
- **Windows:** Docker required for full setup — MEDIUM friction

---

*Analysis complete. page-agent = lightweight in-browser. stealth-browser = heavyweight anti-bot. OmniRoute = comprehensive provider gateway.*
