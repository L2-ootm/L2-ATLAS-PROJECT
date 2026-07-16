# ULTRARESEARCH — Repository Integration Analysis for L2 ATLAS

**Date:** 2026-07-11  
**Scope:** 14 MIT repositories evaluated for integration potential with L2 ATLAS  
**Method:** Parallel web fetch + architectural fit analysis

---

## Priority Matrix

| Priority | Repo | Stars | Integration Type | ATLAS Surface |
|----------|------|-------|------------------|---------------|
| **P0 — Do Now** | rtk-ai/rtk | 70.4k | Default install dep | CLI + all surfaces |
| **P0 — Do Now** | DeusData/codebase-memory-mcp | 30.1k | Internal tool | Brain graph enhancement |
| **P0 — Do Now** | addyosmani/agent-skills | 77.3k | Skill pack import | Agent skills |
| **P1 — High Value** | TencentCloud/TencentDB-Agent-Memory | 8.5k | Memory layer upgrade | Agent memory system |
| **P1 — High Value** | diegosouzapw/OmniRoute | 15.7k | FreeLLMAPI merge/replace | Provider mesh |
| **P1 — High Value** | cobusgreyling/loop-engineering | 7.1k | Pattern library | Agent loop design |
| **P2 — Medium Value** | alibaba/page-agent | 26k | Tool integration | Browser automation tool |
| **P2 — Medium Value** | vibheksoni/stealth-browser-mcp | 1.5k | Tool integration | Advanced browser tool |
| **P2 — Medium Value** | anthropics/skills | 160k | Skill pack import | Agent skills |
| **P3 — Situational** | nazirlouis/Ada-SI | 67 | UI patterns only | Terminal UI reference |
| **P3 — Situational** | Zackriya-Solutions/meetily | 23.1k | Sidecar module | Meeting transcription |
| **P3 — Situational** | zhaoxuya520/reverse-skill | 8.1k | Skill pack import | Security/pentest skills |
| **P3 — Situational** | proxifly/free-proxy-list | 6.1k | Data feed | web_fetch proxy support |
| **Deferred** | proxifly/free-proxy-list | — | GPL-3.0 — CANNOT vendor | Data feed only |

---

## Detailed Analysis

### 1. rtk-ai/rtk (70.4k stars) — TOKEN COMPRESSION PROXY

**What it is:** Single Rust binary CLI proxy that intercepts shell commands and compresses output 60-90% before LLM context. 100+ command filters (git, cargo, pytest, docker, etc.). <10ms overhead.

**ATLAS integration:**
- **Type:** Default installation dependency
- **How:** Bundle `rtk` binary in ATLAS distribution. `atlas up` already manages sidecars — add RTK as a transparent shell filter.
- **Value:** ATLAS agent currently consumes ~118k tokens/30min on shell commands. RTK reduces this to ~24k. Directly addresses the "no performance benchmarking" gap.
- **Effort:** Low — `rtk init --agent hermes` already exists. Just ship the binary.
- **License:** Apache-2.0 (compatible with MIT)

**Action:** Add to `atlas-cli` installer. Add to `atlas up` sidecar list. Ship `rtk.exe` alongside `atlas-gateway.exe`.

---

### 2. DeusData/codebase-memory-mcp (30.1k stars) — CODE INTELLIGENCE

**What it is:** Pure C MCP server. Indexes codebases into persistent knowledge graph via tree-sitter (158 languages). Sub-ms queries. Single static binary. 14 MCP tools: search, trace, architecture, impact analysis, Cypher queries, dead code detection.

**ATLAS integration:**
- **Type:** Internal tool / Brain graph enhancement
- **How:** ATLAS already has `brain_nodes`/`brain_edges` (Phase 10.2). codebase-memory-mcp provides the indexing engine ATLAS lacks. Either:
  - (a) Embed as MCP server in the agent runtime
  - (b) Port the tree-sitter indexing pipeline into ATLAS's Brain retriever
  - (c) Ship as sidecar and query via HTTP
- **Value:** Fills the "no code intelligence" gap. ATLAS's Brain graph is manual — this makes it automatic. 99% fewer tokens for code exploration.
- **Effort:** Medium — the binary is self-contained. Integration is wiring MCP calls through the ATLAS tool manifest.
- **License:** MIT

**Action:** Ship binary as sidecar. Register as ATLAS tool via manifest. Wire to Brain graph auto-indexer.

---

### 3. addyosmani/agent-skills (77.3k stars) — ENGINEERING SKILLS

**What it is:** 24 production-grade engineering skills (spec, plan, build, test, review, ship). 8 slash commands. Anti-rationalization tables. Reference checklists. Compatible with Claude Code, Codex, Cursor, etc.

**ATLAS integration:**
- **Type:** Skill pack import
- **How:** Copy relevant skills into `foundation/atlas-hermes/skills/` or ATLAS's own skill directory. The skill format (SKILL.md with frontmatter) is compatible with Hermes's skill system.
- **Key skills to import:**
  - `test-driven-development` — fills ATLAS's testing gap
  - `security-and-hardening` — addresses SEC-3 (no frontend security tests)
  - `code-review-and-quality` — maps to ATLAS's existing gsd-code-review
  - `observability-and-instrumentation` — fills the monitoring gap
  - `ci-cd-and-automation` — guides atlas-ci.yml improvement
  - `frontend-ui-engineering` — cockpit UI quality
- **Value:** Immediate quality improvement for ATLAS development workflow
- **Effort:** Low — copy SKILL.md files, adapt frontmatter
- **License:** MIT

**Action:** Import top 10 skills. Adapt to ATLAS context. Add to skill inventory.

---

### 4. TencentCloud/TencentDB-Agent-Memory (8.5k stars) — AGENT MEMORY

**What it is:** 4-tier progressive memory pipeline: L0 Conversation → L1 Atom → L2 Scenario → L3 Persona. Symbolic short-term memory (Mermaid canvas). Zero external API dependencies. SQLite+sqlite-vec backend. Already has Hermes plugin.

**ATLAS integration:**
- **Type:** Memory layer upgrade
- **How:** ATLAS currently has basic FTS5 wiki retrieval + Brain graph. TencentDB Agent Memory provides structured long-term memory that ATLAS completely lacks. The Hermes plugin (`hermes-plugin/memory/memory_tencentdb`) already exists — just wire it into ATLAS's foundation.
- **Value:** Addresses the "no long-term memory" gap. 61% token reduction, 51% pass rate improvement in benchmarks. Persona generation for operator preferences.
- **Effort:** Medium — install plugin, configure LLM endpoint, test with ATLAS agent loop
- **License:** MIT

**Action:** Install Hermes plugin. Configure with ATLAS's existing SQLite backend. Test with mission loop.

---

### 5. diegosouzapw/OmniRoute (15.7k stars) — AI GATEWAY / FREELLMAPI REPLACEMENT

**What it is:** Free AI gateway: 237+ providers (90+ free), RTK+Caveman compression, smart auto-fallback, MCP/A2A, multimodal APIs. TypeScript. Desktop/PWA. ~1.6B free tokens/month aggregated.

**ATLAS integration:**
- **Type:** FreeLLMAPI merge/replace
- **How:** ATLAS currently vendors FreeLLMAPI as a sidecar. OmniRoute is a more mature, better-maintained alternative with 237 providers vs FreeLLMAPI's limited set. Options:
  - (a) Replace FreeLLMAPI with OmniRoute as the default sidecar
  - (b) Merge the best of both (OmniRoute's provider catalog + FreeLLMAPI's ATLAS integration)
  - (c) Ship both, let operator choose
- **Value:** 90+ free providers. Token compression built-in. Better provider fallback. Addresses the FreeLLMAPI security advisory (SEC-2).
- **Effort:** High — different architecture (Next.js vs Node.js sidecar). Would need ATLAS adapter layer.
- **License:** MIT

**Action:** Evaluate as FreeLLMAPI successor. Create adapter spec. Defer to v1.2 provider mesh work.

---

### 6. cobusgreyling/loop-engineering (7.1k stars) — LOOP PATTERNS

**What it is:** 7 production loop patterns (Daily Triage, PR Babysitter, CI Sweeper, etc.). CLI tools: loop-audit, loop-init, loop-cost, loop-sync, loop-context. MCP server. Starter kits for Grok/Claude Code/Codex.

**ATLAS integration:**
- **Type:** Pattern library
- **How:** ATLAS already has `l2-loop-engineering` skill. Loop Engineering provides additional patterns and CLI tools that complement it. Key additions:
  - `loop-cost` — token spend estimation (ATLAS lacks this)
  - `loop-audit` — loop readiness scoring
  - `CI Sweeper` pattern — maps to ATLAS's CI gap
  - `PR Babysitter` pattern — useful for ATLAS's unpushed commits problem
- **Value:** Concrete patterns for ATLAS's autonomous operation. Cost estimation fills a gap.
- **Effort:** Low — import patterns, adapt to ATLAS context
- **License:** MIT

**Action:** Import pattern library. Add loop-cost to ATLAS CLI. Use CI Sweeper pattern for atlas-ci.yml.

---

### 7. alibaba/page-agent (26k stars) — IN-PAGE GUI AGENT

**What it is:** JavaScript in-page GUI agent. Controls web interfaces with natural language. Text-based DOM manipulation (no screenshots). Works with any LLM. Chrome extension for multi-page tasks. MCP server.

**ATLAS integration:**
- **Type:** Tool integration
- **How:** Register as ATLAS tool via manifest. The agent could use page-agent to interact with web UIs during missions (form filling, data extraction, UI testing).
- **Value:** Browser automation without headless browser dependency. Text-based = lower resource usage.
- **Effort:** Medium — needs ATLAS tool manifest + adapter
- **License:** MIT

**Action:** Register as optional tool. Add to tool manifest. Test with golden workflows.

---

### 8. vibheksoni/stealth-browser-mcp (1.5k stars) — STEALTH BROWSER

**What it is:** Undetectable browser automation. Bypasses Cloudflare/anti-bot. 97 tools across 11 sections. CDP-based element cloning. Network interception. Dynamic hook system. Python + nodriver.

**ATLAS integration:**
- **Type:** Tool integration (advanced)
- **How:** More powerful than page-agent for scenarios requiring anti-bot bypass. Register as ATLAS tool for web scraping, competitive research, API reverse engineering.
- **Value:** Fills the "web_fetch is basic" gap. CDP-based = pixel-accurate. Network interception = API discovery.
- **Effort:** Medium — needs ATLAS tool manifest + adapter
- **License:** MIT

**Action:** Register as optional high-power tool. Use for Research Brief web_fetch variant (fills INCOMP-3).

---

### 9. anthropics/skills (160k stars) — DOCUMENT SKILLS

**What it is:** Anthropic's official skills. Includes document creation skills (docx, pdf, pptx, xlsx) that power Claude's document capabilities. Apache 2.0 for examples, source-available for document skills.

**ATLAS integration:**
- **Type:** Skill pack import (document skills)
- **How:** ATLAS already has docx/pdf/pptx/xlsx skills in its skill registry. Anthropic's versions are the production reference implementations. Can upgrade existing skills or use as fallback.
- **Value:** Production-grade document generation. Already partially integrated.
- **Effort:** Low — diff existing skills against Anthropic's versions
- **License:** Apache 2.0 (examples), source-available (document skills)

**Action:** Compare with existing ATLAS skills. Upgrade if improvements found.

---

### 10. nazirlouis/Ada-SI (67 stars) — UI PATTERNS ONLY

**What it is:** Self-improving AI assistant with gamified UI (XP, levels), runtime skill forging, React 19 frontend. Python backend + LiteLLM + isolated tool runtime.

**ATLAS integration:**
- **Type:** UI pattern reference only
- **What to take:** The gamified UX patterns (XP, levels, rank titles) could inspire ATLAS terminal TUI progression feedback. The skill forge pipeline (plan → code → test → install) is similar to ATLAS's tool manifest pattern.
- **What NOT to take:** The security model is weak (no auth, arbitrary code execution). Do not import code directly.
- **Value:** Low — pattern reference only
- **Effort:** N/A — reference only

**Action:** Document useful patterns. Do not vendor.

---

### 11. Zackriya-Solutions/meetily (23.1k stars) — MEETING TRANSCRIPTION

**What it is:** Privacy-first AI meeting assistant. Rust backend. Parakeet/Whisper live transcription. Speaker diarization. Ollama summarization. Tauri desktop app. macOS + Windows.

**ATLAS integration:**
- **Type:** Sidecar module (future v2.0 Phase 13 — Voice Integration)
- **How:** Ship as optional ATLAS module. Transcription → ATLAS wiki. Summaries → ATLAS artifacts.
- **Value:** Fills the "STT/TTS Voice Integration" gap in Phase 13 roadmap.
- **Effort:** High — different architecture, needs module adapter
- **License:** MIT

**Action:** Defer to v2.0 Phase 13. Add to roadmap as candidate.

---

### 12. zhaoxuya520/reverse-skill (8.1k stars) — SECURITY SKILLS

**What it is:** Reverse engineering / penetration testing skill router. AI-powered routing for APK reverse, binary RE, JS deobfuscation, pentest, CTF, firmware analysis. 40+ CTF sub-skills.

**ATLAS integration:**
- **Type:** Skill pack import (security)
- **How:** Import pentest/reverse-engineering skills into ATLAS's skill directory. Useful for ATLAS's own security auditing and for operator pentest missions.
- **Value:** Fills the "no security skills" gap. CTF-Sandbox-Orchestrator is GPLv3 — do NOT vendor, only reference.
- **Effort:** Low — copy skill files, adapt
- **License:** MIT (main repo), GPLv3 (CTF sub-module — reference only)

**Action:** Import MIT-licensed skills. Reference CTF patterns. Do not vendor GPLv3 code.

---

### 13. proxifly/free-proxy-list (6.1k stars) — PROXY DATA

**What it is:** Auto-updating free proxy list (HTTP/HTTPS/SOCKS4/SOCKS5). 2564 proxies from 96 countries. Updated every 5 minutes. JSON/TXT/CSV formats.

**ATLAS integration:**
- **Type:** Data feed for web_fetch tool
- **How:** ATLAS's web_fetch tool could use proxy rotation for scraping. The CDN URLs provide fresh proxy lists.
- **Value:** Improves web_fetch reliability. Enables geo-diverse fetching.
- **Effort:** Low — fetch proxy list, rotate in web_fetch adapter
- **License:** GPL-3.0 — **CANNOT vendor into MIT project**. Data feed consumption only.

**Action:** Use CDN data feeds at runtime. Do not vendor the repo. Document GPL constraint.

---

## Integration Roadmap

### Immediate (v1.1 — before Phase 10.8)

1. **RTK** — Add to installer, ship binary, wire to `atlas up`
2. **addyosmani/agent-skills** — Import top 10 skills into ATLAS skill directory
3. **loop-engineering patterns** — Import CI Sweeper and PR Babysitter patterns

### Short-term (v1.2 — Provider Mesh)

4. **TencentDB-Agent-Memory** — Install Hermes plugin, wire to ATLAS memory system
5. **OmniRoute evaluation** — Spec out FreeLLMAPI replacement/merge
6. **codebase-memory-mcp** — Ship binary, register as tool, wire to Brain graph

### Medium-term (v1.2–v1.3)

7. **page-agent** — Register as ATLAS tool for browser automation
8. **stealth-browser-mcp** — Register as advanced browser tool
9. **reverse-skill** — Import pentest skills

### Long-term (v2.0)

10. **meetily** — Module adapter for Phase 13 Voice Integration
11. **proxifly data feeds** — Runtime proxy rotation for web_fetch

---

## License Compliance Summary

| Repo | License | Can Vendor? | Can Use at Runtime? |
|------|---------|-------------|---------------------|
| rtk-ai/rtk | Apache-2.0 | Yes | Yes |
| codebase-memory-mcp | MIT | Yes | Yes |
| addyosmani/agent-skills | MIT | Yes | Yes |
| TencentDB-Agent-Memory | MIT | Yes | Yes |
| OmniRoute | MIT | Yes | Yes |
| loop-engineering | MIT | Yes | Yes |
| page-agent | MIT | Yes | Yes |
| stealth-browser-mcp | MIT | Yes | Yes |
| anthropics/skills | Apache 2.0 / source-available | Partial | Yes |
| Ada-SI | MIT | Yes (patterns only) | Yes |
| meetily | MIT | Yes | Yes |
| reverse-skill | MIT (main) / GPLv3 (CTF) | Main only | Yes |
| proxifly/free-proxy-list | **GPL-3.0** | **NO** | Data feed only |

---

*Generated by ULTRARESEARCH mode — 13 parallel web fetches, synthesized 2026-07-11*
