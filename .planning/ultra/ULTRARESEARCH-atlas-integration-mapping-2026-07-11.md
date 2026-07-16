# ATLAS Integration Mapping — How Each Repo Connects

**Date:** 2026-07-11  
**Purpose:** Map each of 14 repos to specific ATLAS components, wiring points, and effort

---

## ATLAS Component Reference

| Layer | Component | Path | Language |
|-------|-----------|------|----------|
| Foundation | Hermes plugin API | foundation/ | Python |
| Schemas | atlas-core Pydantic v2 | atlas-core/ | Python |
| Runtime | Agent orchestration | agent-runtime/ | Python |
| Gateway | Rust axum dispatch proxy | gateway/ | Rust |
| CLI | Atlas CLI | atlas-cli/ | Python |
| Surface | React cockpit | web-ui-react/ | TypeScript |
| Surface | atlas-terminal | atlas-terminal/ | Bun/Solid |
| Surface | Go TUI (legacy) | services/atlas-tui/ | Go |
| Context | Brain graph | brain_nodes/brain_edges | SQLite |
| Context | Wiki retrieval | memory_router.py | Python |
| Provider | FreeLLMAPI sidecar | _EXTERNAL_REPOS/freellmapi | Node.js |
| Provider | Provider mesh | config_service.py | Python |

---

## 1. rtk-ai/rtk → ATLAS CLI + Runtime

### Wiring Points
- **atlas-cli install:** Add RTK binary download to `atlas setup` or `atlas up`
- **atlas-cli doctor:** Add RTK version check
- **agent-runtime:** RTK hook rewrites shell commands before execution
- **atlas-terminal:** RTK hook applies to terminal shell commands

### Exact Integration Steps
1. Ship `rtk.exe` (Windows) / `rtk` (Linux/macOS) alongside `atlas-gateway.exe`
2. Add `atlas setup rtk` command that runs `rtk init --agent hermes`
3. Add RTK version to `atlas doctor` output
4. Add RTK config to ATLAS config schema (optional, TOML at `~/.config/rtk/config.toml`)

### Effort: LOW (1-2 days)
### Risk: LOW

---

## 2. codebase-memory-mcp → ATLAS Brain Graph

### Wiring Points
- **Brain graph:** ATLAS brain_nodes/brain_edges tables ↔ codebase-memory-mcp knowledge graph
- **Context assembly:** BrainRetriever could query codebase-memory-mcp for code context
- **Tool manifest:** Register as ATLAS tool (14 MCP tools)

### Exact Integration Steps
1. Ship `codebase-memory-mcp` binary as sidecar (alongside gateway)
2. Register in ATLAS tool manifest with 14 tools
3. Wire BrainRetriever to optionally query codebase-memory-mcp for code-related missions
4. Add `atlas brain index` command to trigger indexing

### Effort: MEDIUM (3-5 days)
### Risk: LOW

---

## 3. TencentDB-Agent-Memory → ATLAS Memory System

### Wiring Points
- **memory_router.py:** Current FTS5 wiki retrieval → replace/augment with 4-tier pipeline
- **Context assembly:** L0-L3 memory feeds into context brief
- **Hermes plugin:** Already exists at `hermes-plugin/memory/memory_tencentdb/`

### Exact Integration Steps
1. Install Hermes plugin into ATLAS foundation
2. Configure `memory.provider: memory_tencentdb` in ATLAS config
3. Point gateway at `~/.openclaw/memory-tdai/` for memory persistence
4. Test with mission loop (10-run battery)
5. Add `atlas memory status` command

### Effort: MEDIUM (3-5 days)
### Risk: MEDIUM (Tencent backing)

---

## 4. addyosmani/agent-skills → ATLAS Skill Pack

### Wiring Points
- **foundation/atlas-hermes/skills/:** Import skills here
- **Skill format:** SKILL.md with frontmatter — identical to ATLAS format
- **Agent personas:** Import as ATLAS agent personas

### Exact Integration Steps
1. Copy 10 highest-value skills to `foundation/atlas-hermes/skills/`:
   - `test-driven-development` → fills TDD gap
   - `security-and-hardening` → fills SEC-3
   - `performance-optimization` → fills perf gap
   - `observability-and-instrumentation` → fills monitoring gap
   - `ci-cd-and-automation` → fills CI gap
   - `frontend-ui-engineering` → cockpit UI quality
   - `doubt-driven-development` → adversarial review
   - `context-engineering` → context assembly
   - `source-driven-development` → framework decisions
   - `browser-testing-with-devtools` → cockpit testing
2. Add ATLAS-specific context to each skill's frontmatter
3. Import 4 agent personas as ATLAS agent configs

### Effort: LOW (1-2 days)
### Risk: LOW

---

## 5. loop-engineering → ATLAS Loop Design

### Wiring Points
- **CLI tools:** `loop-cost` → `atlas cost` command
- **Patterns:** CI Sweeper → atlas-ci.yml improvement
- **PR Babysitter:** → ATLAS git discipline

### Exact Integration Steps
1. Import `loop-cost` as `atlas cost` CLI command
2. Import CI Sweeper pattern to guide atlas-ci.yml enhancement
3. Import PR Babysitter pattern for unpushed commits monitoring
4. Add `loop-audit` scoring to `atlas doctor`

### Effort: LOW (1-2 days)
### Risk: LOW

---

## 6. OmniRoute → ATLAS Provider Mesh (FreeLLMAPI Successor)

### Wiring Points
- **config_service.py:** Provider resolution → OmniRoute catalog
- **gateway:** Provider mesh routing → OmniRoute smart fallback
- **atlas-cli:** `atlas freellmapi start|status|stop` → `atlas provider start|status|stop`

### Exact Integration Steps (Phase PM-01)
1. Evaluate OmniRoute as FreeLLMAPI replacement
2. Create ATLAS adapter layer (OmniRoute's Next.js ↔ ATLAS Rust gateway)
3. Migrate 14 API keys from FreeLLMAPI to OmniRoute catalog
4. Test provider fallback chain
5. Brand as "L2 Provider Mesh" per user directive

### Effort: HIGH (2-3 weeks)
### Risk: HIGH (different architecture, complex migration)

---

## 7. page-agent → ATLAS Browser Tool

### Wiring Points
- **Tool manifest:** Register as ATLAS tool
- **Context assembly:** Browser automation for research missions

### Exact Integration Steps
1. Register page-agent as ATLAS tool via manifest
2. Add `browser` tool category to ATLAS tool registry
3. Wire to Research Brief for interactive web data extraction

### Effort: MEDIUM (2-3 days)
### Risk: MEDIUM

---

## 8. stealth-browser-mcp → ATLAS Advanced Browser Tool

### Wiring Points
- **Tool manifest:** Register as high-power ATLAS tool
- **web_fetch variant:** Research Brief with anti-bot capability

### Exact Integration Steps
1. Register as ATLAS tool (97 tools, modular — use 20-tool core)
2. Add to tool manifest with `--minimal` mode
3. Wire to Research Brief for anti-bot sites

### Effort: MEDIUM (2-3 days)
### Risk: MEDIUM (ethical considerations)

---

## 9. anthropics/skills → ATLAS Document Skills Upgrade

### Wiring Points
- **Skills directory:** Upgrade existing docx/pdf/pptx/xlsx skills

### Exact Integration Steps
1. Diff existing ATLAS document skills against Anthropic's versions
2. Apply improvements if found
3. Note: document skills are source-available, not open source — reference only

### Effort: LOW (0.5-1 day)
### Risk: LOW

---

## 10. Ada-SI → ATLAS Self-Evolution Reference

### Wiring Points
- **v1.3 Self-Evolution:** Study skill forge pipeline for EV-01
- **Gamification:** XP/levels pattern for terminal TUI progression

### Exact Integration Steps
1. Document skill forge pipeline pattern
2. Study persona system (SOUL/IDENTITY/MARK)
3. Reference for v1.3 EV-01 implementation

### Effort: N/A (reference only)
### Risk: N/A

---

## 11. meetily → ATLAS Voice Module (v2.0)

### Wiring Points
- **Phase 13 Voice Integration:** Reference architecture for STT/TTS
- **Rust backend:** Aligns with D-022 Rust-first

### Exact Integration Steps
1. Study transcription pipeline architecture
2. Reference for ATLAS voice module design
3. Defer to v2.0 Phase 13

### Effort: N/A (deferred)
### Risk: N/A

---

## 12. reverse-skill → ATLAS Security Skills

### Wiring Points
- **Skills directory:** Import pentest/reverse-engineering skills

### Exact Integration Steps
1. Import MIT-licensed skills to ATLAS skill directory
2. Reference CTF patterns (GPLv3 — do not vendor)
3. Add security audit skill for ATLAS self-testing

### Effort: LOW (1 day)
### Risk: LOW (GPLv3 boundary clear)

---

## 13. proxifly/free-proxy-list → ATLAS web_fetch Proxy

### Wiring Points
- **web_fetch tool:** Runtime proxy rotation

### Exact Integration Steps
1. Fetch proxy list from CDN at runtime
2. Rotate proxies for web_fetch requests
3. Do NOT vendor (GPL-3.0)

### Effort: LOW (0.5 day)
### Risk: LOW (data consumption only)

---

## 14. emilkowalski/skills → ATLAS Design Skills

### Wiring Points
- **Skills directory:** Import design skills

### Exact Integration Steps
1. Full analysis pending
2. Import design skills to ATLAS skill directory
3. Complement existing frontend-design skill

### Effort: TBD
### Risk: TBD

---

## Integration Roadmap

### Wave 1 — Immediate (this sprint)
1. **RTK** — Add to installer, ship binary (1-2 days)
2. **agent-skills** — Import 10 skills (1-2 days)
3. **loop-engineering** — Import patterns + loop-cost (1-2 days)
4. **anthropics/skills** — Diff document skills (0.5 day)
5. **reverse-skill** — Import pentest skills (1 day)

### Wave 2 — Short-term (next 2 weeks)
6. **codebase-memory-mcp** — Wire to Brain graph (3-5 days)
7. **TencentDB-Agent-Memory** — Install plugin (3-5 days)
8. **page-agent** — Register as tool (2-3 days)
9. **stealth-browser-mcp** — Register as tool (2-3 days)
10. **proxifly** — Runtime proxy feed (0.5 day)

### Wave 3 — Medium-term (v1.2 Provider Mesh)
11. **OmniRoute** — Evaluate + adapter layer (2-3 weeks)

### Wave 4 — Long-term (v2.0)
12. **meetily** — Voice module reference (deferred)
13. **emilkowalski/skills** — Design skills (pending analysis)
14. **Ada-SI** — Self-evolution reference (v1.3)

---

*All 14 repos mapped to ATLAS components with wiring points and effort estimates.*
