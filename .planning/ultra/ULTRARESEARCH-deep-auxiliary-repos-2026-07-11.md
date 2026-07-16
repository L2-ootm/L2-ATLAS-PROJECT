# UltraResearch: Deep Auxiliary Repos Integration Analysis

**Date:** 2026-07-11
**Scope:** 5 external repositories for L2 ATLAS integration assessment
**Method:** Live GitHub data fetch + cross-reference with ATLAS roadmap (Phases 10-14), existing skill registry (~266 classified skills), and current architecture

---

## Executive Summary

| # | Repository | Stars | ATLAS Gap Filled | Integration Type | Risk | Verdict |
|---|-----------|-------|-----------------|-----------------|------|---------|
| 1 | meetily | 23.1k | STT/TTS Voice (Phase 13) | Rust lib extraction | MEDIUM | ADOPT (components) |
| 2 | reverse-skill | 8.1k | Pentest/reverse-eng skill gap | SKILL.md copy (MIT only) | MEDIUM | ADOPT (curated subset) |
| 3 | free-proxy-list | 6.1k | web_fetch proxy rotation | Data feed + adapter | HIGH | USE-FEED (GPL-3.0 incompatible) |
| 4 | Ada-SI | 67 | Runtime skill forging concept | Design reference only | LOW | STUDY (do not integrate) |
| 5 | anthropics/skills | 160k | Document skills + spec reference | SKILL.md copy (Apache 2.0) | LOW | ADOPT (selected skills) |

---

## 1. Zackriya-Solutions/meetily

**URL:** https://github.com/Zackriya-Solutions/meetily
**Stars:** 23.1k | **Forks:** 2.4k | **License:** MIT
**ATLAS Phase alignment:** Phase 13 -- STT/TTS Voice Integration

### Architecture

| Layer | Tech | Notes |
|-------|------|-------|
| Frontend | Next.js / TypeScript | 29.7% TS, production-ready |
| Backend/Core | Rust (Tauri) | 46.2% Rust -- the primary runtime |
| STT Engine | Parakeet (NVIDIA) + Whisper (OpenAI) | ONNX-converted models, 4x faster than raw Whisper |
| Summarization | Ollama (local) + Claude/Groq/OpenRouter/OpenAI | Multi-provider LLM routing |
| Audio | Rust audio mixing, GPU accel | Metal (macOS), CUDA (NVIDIA), Vulkan (AMD/Intel) |
| Build | Cargo workspace | frontend/src-tauri + llama-helper crates |
| Other | C++ 9.9%, Python 3.1%, Shell 4.1% | C++ for whisper.cpp bindings |

**Structure:**
`
meetily/
+-- backend/          # Rust backend logic
+-- frontend/src-tauri/ # Tauri app + Next.js frontend
+-- llama-helper/     # Ollama/LLM integration crate
+-- docs/             # Architecture docs, build guides
+-- scripts/          # Build/setup helpers
+-- Cargo.toml        # Workspace root
`

**Data flow:**
`
System Audio + Mic -> Rust Audio Mixer -> STT (Parakeet/Whisper ONNX) -> Transcript
Transcript + User Prompt -> LLM (Ollama/Claude/Groq) -> Summary
All local; zero cloud dependency for core path
`

### Complete Inventory

| Component | Purpose |
|-----------|---------|
| backend/ | Audio capture, device selection, mixing with ducking/clipping prevention |
| llama-helper/ | Ollama integration, custom OpenAI endpoint support |
| frontend/ | React/Next.js UI -- meeting list, live transcript, summary generation, settings |
| Parakeet STT | NVIDIA TDT model (0.6B params), ONNX-converted, 4x Whisper speed |
| Whisper STT | OpenAI Whisper, fallback/alternative |
| GPU detection | Auto-enables Metal/CUDA/Vulkan at build time |
| Import & Enhance | Re-transcribe existing audio files with different model/language |
| Custom endpoint | OpenAI-compatible API for organizations with custom AI infra |

### Quality Assessment

| Aspect | Rating | Evidence |
|--------|--------|---------|
| Activity | HIGH | 556 commits, 11 releases, latest v0.4.0 (Jun 5 2026), 186 open issues, 87 open PRs |
| Maintenance | HIGH | Active development, pre-release cadence, community Discord |
| Tests | LOW-VISIBLE | No test directory found in repo structure; CONTRIBUTING.md exists but test suite unclear |
| Security | MEDIUM | Privacy-first design is a strength; no SECURITY.md visible; MIT license; some borrowed code (whisper.cpp, screenpipe) needs attribution audit |
| Code quality | MEDIUM-HIGH | Rust 46% is solid; Tauri is production-grade; ONNX model integration is well-structured |
| Documentation | HIGH | Architecture docs, build guides for Linux/macOS/Windows, privacy policy |

### ATLAS Fit Assessment

| Gap | How meetily fills it |
|-----|---------------------|
| Phase 13: STT/TTS Voice | Direct candidate. Parakeet/Whisper STT engine is production-ready, Rust-native, and 4x faster than raw Whisper. TTS not yet in meetily (PRO has ElevenLabs planned) |
| Rust-first directive (D-022) | Fully aligned -- 46% Rust backend, Cargo workspace, Tauri framework |
| Local-first privacy | All processing local, zero cloud -- matches ATLAS operator-first philosophy |

**What to adopt:**
1. **Parakeet STT crate** -- Extract the ONNX Parakeet integration from llama-helper or backend. Highest-value component: production-tested, GPU-accelerated, Rust-native speech-to-text.
2. **Audio mixing module** -- Rust audio capture with ducking/clipping. Useful for ATLAS voice input pipeline.
3. **GPU acceleration pattern** -- The Metal/CUDA/Vulkan detection and auto-selection is reusable.

**What NOT to adopt:**
- The Tauri frontend (ATLAS uses its own web cockpit)
- The meeting-specific business logic (meeting storage, summary generation)
- Ollama integration (ATLAS already has its own LLM provider mesh)

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Borrowed code attribution (whisper.cpp, screenpipe, transcribe-rs) | MEDIUM | Audit LICENSE.md and .gitmodules before extracting code; ensure permissive license compatibility |
| No visible test suite | MEDIUM | Write integration tests for any extracted crate before depending on it |
| ONNX model distribution | LOW | Parakeet model is publicly available on HuggingFace; download at build time |
| CUDA/Metal dependency complexity | MEDIUM | Extract only the CPU fallback path first; add GPU acceleration as opt-in |

### Integration Effort

- **Extract Parakeet STT crate:** MEDIUM (2-3 weeks) -- isolate from Tauri dependencies, add to native/ Rust layer
- **Extract audio mixer:** LOW-MEDIUM (1-2 weeks) -- if needed for voice input
- **License check:** LOW (1 day) -- MIT compatible, but audit third-party attributions

---

## 2. zhaoxuya520/reverse-skill

**URL:** https://github.com/zhaoxuya520/reverse-skill
**Stars:** 8.1k | **Forks:** 1.3k | **License:** MIT (main) + GPLv3 (CTF submodule) + AGPL-3.0 (Pentest Swarm, called only)
**ATLAS Gap:** Pentest/reverse-engineering skills -- currently zero coverage in ATLAS

### Architecture

| Layer | Tech | Notes |
|-------|------|-------|
| Skill format | Markdown (SKILL.md + routing.md + tool-index.md) | AI-agent-oriented, compatible with ATLAS |
| Routing | RULES.md -> skills/routing.md -> target SKILL.md | 3-axis routing: target type + user intent + toolchain |
| Tools | Python, Java, PowerShell, Bash, Node.js | Wrapper scripts for external tools |
| Platforms | Kali Linux, Ubuntu/Debian, macOS, Windows | Platform-specific install guides |
| Security tools | IDA Pro, radare2, Ghidra, jadx, Frida, BurpSuite MCP, Nmap, SQLMap, etc. | 50+ tools indexed |

**Structure:**
`
reverse-skill/
+-- skills/
|   +-- SKILL.md              # Master entry point
|   +-- routing.md            # 3-axis routing matrix
|   +-- field-journal/        # Experience log (knowledge base)
|   +-- apk-reverse/          # APK/Android reverse engineering
|   +-- js-reverse/           # JS/frontend signature/encryption
|   +-- ida-reverse/          # IDA Pro workflows (72 tools via MCP)
|   +-- radare2/              # radare2 CLI analysis
|   +-- reverse-engineering/  # General methodology (OLLVM, patterns)
|   +-- pentest-tools/        # Penetration testing (Nmap, SQLMap, etc.)
|   +-- pwn-chain/            # Exploit development
|   +-- patch-diff-exploit/   # N-day analysis
|   +-- firmware-pentest/     # Firmware/IoT
|   +-- edr-bypass-re/        # EDR bypass techniques
|   +-- binary-diff/          # Symbol migration
|   +-- browser-automation/   # Playwright/OpenReverse
|   +-- diagram-generator/    # Mermaid/Graphviz/PlantUML
|   +-- docs-generator/       # Report generation
|   +-- llm-security/         # OWASP LLM Top 10 + ASI Top 10
|   +-- api-security/         # REST/GraphQL/JWT/OAuth
|   +-- supply-chain-security/# Trivy/Syft/Gitleaks
|   +-- mobile-reverse/       # iOS/Android mobile
|   +-- malware-analysis/     # YARA/Sigma/IOC
|   +-- attack-chain/         # Full attack chain orchestration
+-- CTF-Sandbox-Orchestrator/ # 40+ CTF sub-skills (GPLv3)
+-- burp-mcp-full/            # BurpSuite MCP integration
+-- kali/                     # Kali Linux helper scripts
+-- RULES.md                  # Global routing rules
+-- README_AI.md              # AI agent configuration guide
`

**Data flow:**
`
User Task -> RULES.md (routing) -> Skill Router (3-axis match) -> Target SKILL.md
-> Tool/MCP/Script execution -> Report + Experience log
`

### Complete Skill Inventory

| Category | Skills | Tools Covered |
|----------|--------|---------------|
| Android/APK | apk-reverse/ | jadx, apktool, Frida |
| Binary reverse | ida-reverse/, radare2/ | IDA Pro (72 MCP tools), radare2, Ghidra, GDB |
| JS/Web | js-reverse/ | anything-analyzer MCP, jshookmcp |
| Pentest | pentest-tools/ | Nmap, SQLMap, Nuclei, FFUF, Gobuster, Hashcat, BurpSuite, SSTImap, XSStrike, WPProbe, AdaptixC2, ProxyCat |
| Exploit | pwn-chain/ | pwntools, ROP, ret2libc |
| N-day | patch-diff-exploit/ | ghidriff, Diaphora, DeepDiff |
| Firmware | firmware-pentest/ | binwalk, ARM/MIPS analysis |
| EDR | edr-bypass-re/ | EDR/AV evasion techniques |
| Binary diff | binary-diff/ | LLM symbol migration, BinDiff |
| Browser | browser-automation/ | Playwright, OpenReverse |
| Diagrams | diagram-generator/ | Mermaid, Graphviz, PlantUML |
| Reports | docs-generator/ | CTF writeup, pentest report |
| LLM security | llm-security/ | OWASP LLM Top 10, garak, PyRIT, promptfoo |
| API security | api-security/ | BOLA, BFLA, JWT, OAuth |
| Supply chain | supply-chain-security/ | Trivy, Syft, Gitleaks, OSV-Scanner |
| Mobile | mobile-reverse/ | class-dump, Hopper, Frida iOS, Objection |
| Malware | malware-analysis/ | YARA, Sigma, IOC |
| Attack chain | attack-chain/ | Cobalt Strike, Sliver, Havoc, full chain orchestration |
| OLLVM | reverse-engineering/references/ | D-810, obpo, Miasm, angr, SiMBA |
| CTF | CTF-Sandbox-Orchestrator/ | 40+ sub-skills (GPLv3) |

### Quality Assessment

| Aspect | Rating | Evidence |
|--------|--------|---------|
| Activity | MEDIUM | 71 commits, 0 open issues, 0 open PRs, 1 tag |
| Maintenance | LOW-MEDIUM | Single maintainer, bilingual (CN/EN), no releases |
| Tests | NONE | No test suite visible; tool-index.md is auto-generated |
| Security | LOW | Security tool wrappers without sandboxing; AGPL-3.0 dependency (Pentest Swarm) called via CLI |
| Code quality | MEDIUM | Well-organized routing matrix; skill structure is clean; PowerShell/Shell scripts functional |
| Documentation | HIGH | Bilingual README, platform install guides, routing matrix, AI agent guide |

### ATLAS Fit Assessment

| Gap | How reverse-skill fills it |
|-----|---------------------------|
| Pentest/reverse-eng skills | ATLAS has zero pentest skills. This repo has 20+ security skill categories |
| Skill routing pattern | 3-axis routing matrix (target type + user intent + toolchain) -- more sophisticated than ATLAS keyword-match |
| LLM security | llm-security/ covers OWASP LLM Top 10 -- directly relevant for ATLAS security posture |
| Report generation | docs-generator/ pattern for technical documentation is reusable |

**What to adopt (MIT-only subset):**
1. **llm-security/ SKILL.md** -- OWASP LLM Top 10, prompt injection defense
2. **diagram-generator/ SKILL.md** -- Mermaid/Graphviz/PlantUML
3. **docs-generator/ SKILL.md** -- Technical report generation pattern
4. **api-security/ SKILL.md** -- REST/GraphQL/JWT/OAuth testing
5. **supply-chain-security/ SKILL.md** -- Trivy/Syft/Gitleaks
6. **browser-automation/ SKILL.md** -- Playwright patterns

**What NOT to adopt:**
- CTF-Sandbox-Orchestrator/ (GPLv3 -- incompatible with MIT ATLAS)
- burp-mcp-full/ (requires BurpSuite license)
- Offensive tool wrappers (Nmap, SQLMap, Metasploit) unless explicitly opted-in
- edr-bypass-re/, pwn-chain/, attack-chain/ -- too offensive for ATLAS scope

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| GPLv3 contamination via CTF submodule | HIGH | Do NOT copy CTF-Sandbox-Orchestrator/; treat as external reference only |
| AGPL-3.0 call dependency (Pentest Swarm) | MEDIUM | Only reference via CLI/MCP; do not link or embed |
| Offensive tool wrappers may be misused | MEDIUM | Gate behind explicit opt-in consent; do not ship in default skill pack |
| Single maintainer, bilingual | LOW-MEDIUM | Fork and maintain locally; skill format is stable |
| No test coverage | LOW | Skills are markdown instructions, not executable code |

### Integration Effort

- **Copy 5-6 MIT SKILL.md files:** LOW (1-2 days)
- **Adapt routing pattern:** MEDIUM (1 week)
- **License audit:** LOW (1 day)

---

## 3. proxifly/free-proxy-list

**URL:** https://github.com/proxifly/free-proxy-list
**Stars:** 6.1k | **Forks:** 710 | **License:** GPL-3.0
**ATLAS Gap:** web_fetch proxy rotation for gateway/external API calls

### Architecture

| Layer | Tech | Notes |
|-------|------|-------|
| Data source | GitHub Actions (cron) | Auto-updates every 5 minutes |
| Data format | JSON, TXT, CSV | CDN-served via jsDelivr |
| Coverage | 3,241 proxies, 105 countries | HTTP (582), HTTPS (1,220), SOCKS4 (373), SOCKS5 (1,066) |
| NPM module | proxifly package | Programmatic access with API key |
| Desktop app | Windows/macOS/Linux | Proxy scraper software |

**Structure:**
`
free-proxy-list/
+-- proxies/
|   +-- all/              # Combined: data.json, data.txt, data.csv
|   +-- protocols/
|   |   +-- http/         # HTTP proxies
|   |   +-- https/        # HTTPS proxies
|   |   +-- socks4/       # SOCKS4 proxies
|   |   +-- socks5/       # SOCKS5 proxies
|   +-- countries/        # Per-country proxy lists (105 countries)
+-- README.md
+-- LICENSE               # GPL-3.0
+-- CONTRIBUTING.md
`

**Data flow:**
`
Web Sources -> Proxifly scraper (cron every 5 min) -> Validation -> CDN (jsDelivr)
-> Client (curl / NPM / download) -> Proxy rotation for HTTP requests
`

### Complete Inventory

| Component | Purpose |
|-----------|---------|
| proxies/all/data.{json,txt,csv} | All 3,241 validated proxies |
| proxies/protocols/{http,https,socks4,socks5}/data.* | Protocol-filtered lists |
| proxies/countries/{CC}/data.* | Country-filtered lists (105 countries) |
| NPM proxifly module | getProxy({protocol, anonymity, country, https, format, quantity}) |
| CDN URLs | cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/... |
| Desktop scraper app | GUI proxy scraper (Windows/macOS/Linux) |

### Quality Assessment

| Aspect | Rating | Evidence |
|--------|--------|---------|
| Activity | VERY HIGH | 59,990 commits (automated cron), continuous updates |
| Maintenance | HIGH | Automated via GitHub Actions; updates every 5 minutes |
| Tests | NONE | Data-only repo; validation built into the scraper |
| Security | LOW | Free proxies are inherently untrusted; no encryption of proxy data |
| Code quality | N/A | Data repo, not code |
| Documentation | MEDIUM | README is clear; usage examples provided |

### ATLAS Fit Assessment

| Gap | How free-proxy-list fills it |
|-----|----------------------------|
| web_fetch proxy rotation | ATLAS gateway could use rotating proxies for external API calls |
| Research/data collection | Proxy rotation useful for web research skills |

**What to adopt:**
- **Data feed only** -- Use CDN URLs as proxy data source for ATLAS proxy-rotation adapter
- **Pattern** -- Protocol/country/anonymity classification scheme is reusable

**What NOT to adopt:**
- NPM module (GPL-3.0, adds Node.js dependency)
- Desktop scraper app (irrelevant)
- Any GPL-3.0 code

### Critical License Issue

**GPL-3.0 is INCOMPATIBLE with ATLAS MIT license.** The proxy data (IP:port lists) is factual data and not copyrightable, so consuming the raw data is fine. However:
- Do NOT copy the NPM module code (GPL-3.0)
- Do NOT copy the desktop scraper (GPL-3.0)
- DO use the CDN-served data files directly (factual data, no license restriction)
- Build an ATLAS-native proxy adapter in Rust/Python that reads the CDN data

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| GPL-3.0 license contamination | HIGH | Use CDN data only; build adapter from scratch |
| Free proxies are unreliable/untrusted | HIGH | Always validate proxies before use; never use for sensitive data |
| Proxy quality varies | MEDIUM | Implement health-check + scoring before routing |
| Rate limiting on CDN | LOW | Cache proxy list locally; refresh every 5-10 minutes |
| Privacy implications | MEDIUM | Third-party proxies add a trust hop; document this tradeoff |

### Integration Effort

- **Proxy rotation adapter:** MEDIUM (1-2 weeks) -- Rust module fetching CDN data
- **CDN data consumption:** LOW (1 day) -- Direct URL fetch
- **License compliance:** LOW (1 day) -- Verify data-only consumption

---

## 4. nazirlouis/Ada-SI

**URL:** https://github.com/nazirlouis/Ada-SI
**Stars:** 67 | **Forks:** 23 | **License:** MIT
**ATLAS Gap:** Runtime skill forging concept (experimental reference)

### Architecture

| Layer | Tech | Notes |
|-------|------|-------|
| Backend | Python 3.12, FastAPI, Uvicorn | SSE streaming, forge APIs |
| LLM routing | LiteLLM proxy (port 4000) | Multi-provider: OpenAI, Anthropic, Gemini, Groq |
| Tool runtime | Separate FastAPI service (port 8090) | Executes forged Python skills in isolated venv |
| Frontend | React 19, TypeScript, Vite 8 | Framer Motion, Three.js, Zustand |
| UI graphics | Three.js, @react-three/fiber | 3D avatar visualizer |
| Persistence | File-based (staging/, custom_tools/) | No database; localStorage for XP |
| Voice | Web Speech API (input) + ElevenLabs (TTS output) | Browser-native STT |
| Container | Docker Compose | Three containers: chat, litellm, tool-runtime |

**Structure:**
`
Ada-SI/
+-- chat/
|   +-- app.py                  # FastAPI main server
|   +-- frontend/               # React 19 + Vite
|   |   +-- src/
|   |       +-- components/     # UI components
|   |       +-- api/client.ts   # API client
|   |       +-- stores/         # Zustand stores
|   +-- custom_tools/           # Forged Python skills (runtime)
|   +-- staging/                # Secrets, persona, config
|   +-- persona_defaults/       # Default persona templates
|   +-- requirements.txt        # fastapi, uvicorn, httpx
|   +-- test_*.py               # Basic tests
+-- tool_runtime/
|   +-- server.py               # FastAPI tool execution
|   +-- requirements.txt        # fastapi, uvicorn
+-- litellm/
|   +-- config.yaml             # LiteLLM proxy config
+-- docker-compose.yml
+-- .env.example
+-- install-*.bat/sh/ps1        # Cross-platform installers
`

**Data flow:**
`
Browser -> Chat Server (:8080) -> LiteLLM proxy (:4000) -> LLM providers
         |
     Tool Runtime (:8090) -> Forged Python skills (isolated venv)
         |
     Chat UI <- SSE stream <- Chat Server
`

### Complete Skill Inventory

Ada-SI does NOT have pre-built skills. It has a **runtime skill forging pipeline**:

| Pipeline Stage | What Happens |
|----------------|-------------|
| generate_code | AI generates skill code from description |
| validate_code | Inspects module structure |
| sandbox_test | Trial run in test venv |
| validate_ui | Validates interactive app UI |
| contract_test | Tests skill API contract |
| preview_review | Automated app review |
| ui_preview | Preview interactive app |
| pip_review | Reviews pip package dependencies |
| runtime_verify | Verifies skill runtime |
| install_tool | Unlocks skill for use |

**Gamification system:**
- XP for chatting (10/msg), forging skills (180/skill), using skills (30/action)
- Levels 1-50 with rank titles
- 3D avatar that reacts to activity

### Quality Assessment

| Aspect | Rating | Evidence |
|--------|--------|---------|
| Activity | LOW | 38 commits, 0 open issues, 2 open PRs, no releases |
| Maintenance | LOW | Single author, experimental status explicitly stated |
| Tests | LOW | test_calc_snippet.py visible; pytest mentioned but minimal |
| Security | VERY LOW | Explicitly warns: no auth, AI can execute arbitrary Python, no sandbox, API keys in plaintext |
| Code quality | MEDIUM | Well-structured FastAPI app; clear separation of concerns |
| Documentation | HIGH | Comprehensive README with security threat model, architecture diagrams, API reference |

### ATLAS Fit Assessment

| Gap | How Ada-SI fills it |
|-----|-------------------|
| Runtime skill forging | Demonstrates production-ish forge pipeline (plan -> code -> test -> install). ATLAS skill system is currently static. |
| Gamified UX | XP/levels/rank system is a reference for ATLAS operator engagement metrics |
| Multi-provider LLM routing | Validates the LiteLLM proxy pattern (ATLAS has its own provider mesh) |
| Forge batch | Parallel tool creation (2-10 at once) is a useful concept for ATLAS skill authoring |

**What to adopt:**
- **Nothing directly.** Ada-SI is a design reference, not a code source. Its value is in demonstrating:
  1. The forge pipeline pattern (plan -> code -> validate -> install with human-in-the-loop)
  2. The gamification engagement model
  3. The multi-service architecture (chat + LLM proxy + tool runtime)
- The security warnings are instructive for ATLAS tool execution design

**What NOT to adopt:**
- Any code (Python/FastAPI conflicts with ATLAS Rust-first directive)
- Security model (no auth, no sandbox, arbitrary code execution)
- LiteLLM dependency (ATLAS has its own provider mesh)
- React frontend (ATLAS has its own cockpit)

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Security model is fundamentally unsafe | CRITICAL | Do not replicate; study threat model for what to avoid |
| Small project, experimental | MEDIUM | Use as design reference only; do not depend on for production |
| Python/FastAPI stack | LOW | ATLAS is Rust-first; concepts must be reimplemented in Rust |
| No test coverage | LOW | Not relevant since we are not integrating code |

### Integration Effort

- **Design reference:** ZERO code integration
- **Forge pattern study:** LOW (2-3 days) -- Document the forge pipeline pattern
- **Gamification study:** LOW (1 day) -- Note XP/level system for potential ATLAS operator engagement

---

## 5. anthropics/skills

**URL:** https://github.com/anthropics/skills
**Stars:** 160k | **Forks:** 18.9k | **License:** Apache 2.0 (most skills) + Source-Available (docx/pdf/pptx/xlsx)
**ATLAS Gap:** Document skills (existing ATLAS docs are basic), Agent Skills specification reference

### Architecture

| Layer | Tech | Notes |
|-------|------|-------|
| Skill format | SKILL.md with YAML frontmatter | name + description fields; markdown instructions below |
| Spec | spec/agent-skills-spec.md -> agentskills.io | Defines the Agent Skills standard |
| Template | template/ | Starting point for new skills |
| Document skills | Python 84.4% | Production-grade (powers Claude document capabilities) |
| Example skills | HTML 12.4%, JS 1.3% | Creative, technical, enterprise skills |

**Structure:**
`
anthropics/skills/
+-- skills/
|   +-- algorithmic-art/       # Creative: generative art
|   +-- brand-guidelines/      # Enterprise: brand consistency
|   +-- canvas-design/         # Creative: canvas design
|   +-- claude-api/            # Technical: Claude API usage
|   +-- doc-coauthoring/       # Enterprise: document co-authoring
|   +-- docx/                  # Document: Word creation (source-available)
|   +-- frontend-design/       # Technical: frontend design
|   +-- internal-comms/        # Enterprise: internal communications
|   +-- mcp-builder/           # Technical: MCP server generation
|   +-- pdf/                   # Document: PDF creation (source-available)
|   +-- pptx/                  # Document: PowerPoint (source-available)
|   +-- skill-creator/         # Meta: create new skills
|   +-- slack-gif-creator/     # Creative: Slack GIF creation
|   +-- theme-factory/         # Creative: theme generation
|   +-- web-artifacts-builder/ # Technical: web artifacts
|   +-- webapp-testing/        # Technical: web app testing
|   +-- xlsx/                  # Document: Excel (source-available)
+-- spec/
|   +-- agent-skills-spec.md   # Agent Skills specification
+-- template/
|   +-- SKILL.md               # Skill template
+-- .claude-plugin/            # Claude Code plugin config
`

### Complete Skill Inventory

| Category | Skill | Purpose | License |
|----------|-------|---------|---------|
| Document | docx/ | Word document creation/editing | Source-Available (not open source) |
| Document | pdf/ | PDF creation/editing | Source-Available |
| Document | pptx/ | PowerPoint creation/editing | Source-Available |
| Document | xlsx/ | Excel creation/editing | Source-Available |
| Technical | claude-api/ | Claude API usage patterns | Apache 2.0 |
| Technical | mcp-builder/ | MCP server generation | Apache 2.0 |
| Technical | web-artifacts-builder/ | Web artifact creation | Apache 2.0 |
| Technical | webapp-testing/ | Web app testing | Apache 2.0 |
| Technical | frontend-design/ | Frontend design guidance | Apache 2.0 |
| Creative | algorithmic-art/ | Generative art | Apache 2.0 |
| Creative | canvas-design/ | Canvas design | Apache 2.0 |
| Creative | slack-gif-creator/ | Slack GIF creation | Apache 2.0 |
| Creative | theme-factory/ | Theme generation | Apache 2.0 |
| Enterprise | brand-guidelines/ | Brand consistency | Apache 2.0 |
| Enterprise | doc-coauthoring/ | Document co-authoring | Apache 2.0 |
| Enterprise | internal-comms/ | Internal communications | Apache 2.0 |
| Meta | skill-creator/ | Skill creation guide | Apache 2.0 |
| Spec | spec/agent-skills-spec.md | Agent Skills standard | -- |

### Quality Assessment

| Aspect | Rating | Evidence |
|--------|--------|---------|
| Activity | VERY HIGH | 43 commits, 288 open issues, 733 open PRs, 18.9k forks |
| Maintenance | VERY HIGH | Maintained by Anthropic; actively used in Claude.ai, Claude Code, Claude API |
| Tests | HIGH | Production-tested in Claude document capabilities |
| Security | HIGH | Anthropic security standards; disclaimer about demonstration purposes |
| Code quality | VERY HIGH | Production-grade document skills (docx/pdf/pptx/xlsx power Claude actual features) |
| Documentation | HIGH | README, support articles, spec, template |

### ATLAS Fit Assessment

| Gap | How anthropics/skills fills it |
|-----|-------------------------------|
| Document creation skills | ATLAS has basic documentation but no structured document creation. The docx/pdf/pptx/xlsx skills are production-proven. |
| Skill format spec | The Agent Skills specification (spec/agent-skills-spec.md -> agentskills.io) is the reference standard. ATLAS SKILL.md format is compatible. |
| MCP server generation | mcp-builder/ teaches how to create MCP servers -- directly useful for ATLAS integration layer |
| Web app testing | webapp-testing/ is useful for ATLAS cockpit quality assurance |
| Skill creation guide | skill-creator/ teaches how to create new skills -- useful for ATLAS skill authoring workflow |

**What to adopt:**
1. **skill-creator/ SKILL.md** -- Meta-skill for creating new skills. Directly useful for ATLAS skill authoring.
2. **mcp-builder/ SKILL.md** -- MCP server generation. Useful for ATLAS integration layer.
3. **webapp-testing/ SKILL.md** -- Web app testing patterns. Useful for ATLAS cockpit QA.
4. **claude-api/ SKILL.md** -- Claude API patterns. Useful when ATLAS routes through Claude.
5. **Agent Skills spec** -- Reference for ATLAS skill format alignment.

**What NOT to adopt:**
- docx/, pdf/, pptx/, xlsx/ -- Source-available but NOT open source. Cannot include in ATLAS MIT codebase without Anthropic permission. Study patterns only.
- Creative skills (algorithmic-art, canvas-design, slack-gif-creator, theme-factory) -- Not relevant to ATLAS operator focus
- Enterprise skills (brand-guidelines, doc-coauthoring, internal-comms) -- ATLAS is not an enterprise comms tool

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Document skills are source-available, not open source | HIGH | Study patterns; do not copy code. Build ATLAS-native document skills if needed. |
| Claude-specific API patterns may not generalize | LOW | Only adopt patterns that work across providers |
| Large PR/issue backlog (733 PRs, 288 issues) | LOW | Community-driven; core skills maintained by Anthropic |
| Spec may evolve | LOW | Pin to specific commit when adopting |

### Integration Effort

- **Copy 3-4 Apache 2.0 SKILL.md files:** LOW (1 day) -- skill-creator, mcp-builder, webapp-testing, claude-api
- **Study Agent Skills spec:** LOW (1 day) -- Reference for ATLAS skill format
- **Document skills pattern study:** LOW (2-3 days) -- If ATLAS needs document creation, study source-available patterns

---

## Cross-Repository Integration Matrix

### ATLAS Skill Registry Impact

| Repo | Skills to Add | Category | public_safe | autonomy |
|------|--------------|----------|-------------|----------|
| anthropics/skills | skill-creator, mcp-builder, webapp-testing, claude-api | developer/operator | true | semi |
| reverse-skill | llm-security, diagram-generator, docs-generator, api-security, supply-chain-security, browser-automation | operator/security | true (partial) | guided |
| meetily | (none -- code extraction, not skills) | -- | -- | -- |
| free-proxy-list | (none -- data feed, not skills) | -- | -- | -- |
| Ada-SI | (none -- design reference only) | -- | -- | -- |

**Net new skills to ATLAS registry:** ~10 SKILL.md files

### License Compatibility Summary

| Repo | License | ATLAS MIT Compatible | Action |
|------|---------|---------------------|--------|
| meetily | MIT | YES | Adopt components |
| reverse-skill | MIT (main) + GPLv3 (CTF) + AGPL-3.0 (Pentest Swarm) | PARTIAL -- MIT-only subset only | Cherry-pick MIT files |
| free-proxy-list | GPL-3.0 | NO (code) / YES (data) | Use CDN data only |
| Ada-SI | MIT | YES | Study only (no code adoption) |
| anthropics/skills | Apache 2.0 (most) + Source-Available (docx/pdf/pptx/xlsx) | YES for Apache 2.0; NO for source-available | Adopt Apache 2.0 files only |

### Risk-Weighted Priority

| Priority | Repo | Rationale |
|----------|------|-----------|
| 1 (Highest) | anthropics/skills | Highest stars (160k), Apache 2.0, production-tested, fills document skills gap, defines spec standard |
| 2 | meetily | Fills Phase 13 STT/TTS gap directly, Rust-native, MIT, 23k stars |
| 3 | reverse-skill | Fills pentest/security skill gap (currently zero), MIT subset usable, 8k stars |
| 4 | free-proxy-list | Useful data feed but GPL-3.0 constrains code adoption; use CDN data only |
| 5 (Lowest) | Ada-SI | Design reference only; too experimental, too small (67 stars), security concerns |

### Recommended Integration Sequence

`
Phase A (Immediate -- 1 week):
  +-- anthropics/skills: Copy skill-creator, mcp-builder, webapp-testing, claude-api SKILL.md files
  +-- reverse-skill: Copy llm-security, diagram-generator, docs-generator SKILL.md files

Phase B (Short-term -- 2 weeks):
  +-- meetily: Extract Parakeet STT ONNX integration as Rust crate for native/ layer
  +-- reverse-skill: Copy api-security, supply-chain-security, browser-automation SKILL.md files

Phase C (Medium-term -- 1 month):
  +-- free-proxy-list: Build Rust proxy-rotation adapter consuming CDN data
  +-- anthropics/skills: Study docx/pdf patterns for future ATLAS document skills

Phase D (Long-term -- reference only):
  +-- Ada-SI: Document forge pipeline pattern for future ATLAS skill authoring
  +-- meetily: Evaluate TTS integration path (ElevenLabs or local)
`

---

## Appendices

### A. ATLAS Existing Skill Registry Context

From docs/imports/SKILL_INVENTORY.md (Phase 9):
- ~266 skills across 7 source groups
- ATLAS Core Pack: 7 credential-free public-safe skills
- Developer Operator Pack: ~18 opt-in skills
- L2 Systems Pack: 9 l2-internal/personal-private skills
- Format: SKILL.md with YAML frontmatter (name, version, class, autonomy_level, risk, requires_tools, requires_secrets, verification, public_safe)

### B. Phase 13 STT/TTS Voice Integration Status

From ROADMAP.md:
- Phase 13: STT/TTS Voice Integration -- status: Not started
- Part of v2.0 milestone (Phases 11-14)
- meetily provides the strongest STT candidate (Parakeet ONNX, Rust-native, 4x faster)

### C. Key Files Referenced

- .planning/ROADMAP.md -- Phase 13 definition
- .planning/milestones/v1.0-REQUIREMENTS.md -- SKILLS-01 through SKILLS-04
- docs/imports/SKILL_INVENTORY.md -- Existing 266-classified skill registry
- .planning/ultra/ULTRARESEARCH-FINAL-integration-master-plan-2026-07-11.md -- Prior integration plan
