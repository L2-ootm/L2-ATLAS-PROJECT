# ULTRARESEARCH — Final Integration Master Plan

**Date:** 2026-07-11  
**Total repos analyzed:** 14  
**Reports produced:** 7 files in `.planning/ultra/`  
**Status:** Ready for operator review

---

## Report Index

| # | Report | Content |
|---|--------|---------|
| 1 | `ULTRARESEARCH-full-codebase-analysis-2026-07-11.md` | ATLAS architecture, tech stack, all routes, all calls |
| 2 | `ULTRARESEARCH-repo-integration-analysis-2026-07-11.md` | 14 repos evaluated for fit, priority matrix |
| 3 | `ULTRARESEARCH-deep-analysis-memory-token-2026-07-11.md` | RTK + codebase-memory + TencentDB deep dive |
| 4 | `ULTRARESEARCH-deep-analysis-skills-patterns-2026-07-11.md` | agent-skills + anthropics/skills + loop-engineering deep dive |
| 5 | `ULTRARESEARCH-deep-analysis-browser-gateway-2026-07-11.md` | page-agent + stealth-browser + OmniRoute deep dive |
| 6 | `ULTRARESEARCH-deep-analysis-auxiliary-2026-07-11.md` | Ada-SI + meetily + reverse-skill + proxifly + emilkowalski deep dive |
| 7 | `ULTRARESEARCH-atlas-integration-memory-token-2026-07-11.md` | Integration spec: RTK + codebase-memory + TencentDB |
| 8 | `ULTRARESEARCH-atlas-integration-skills-patterns-2026-07-11.md` | Integration spec: skills + loop patterns + design skills |
| 9 | `ULTRARESEARCH-atlas-integration-browser-gateway-2026-07-11.md` | Integration spec: browser tools + OmniRoute + auxiliary |
| 10 | `ULTRARESEARCH-FINAL-integration-master-plan-2026-07-11.md` | This file — master plan |

---

## Integration Summary

### Wave 1: Immediate (Before Phase 10.8)

| # | Tool | Stars | Effort | Files to Change | Value |
|---|------|-------|--------|-----------------|-------|
| 1 | **RTK** | 70.4k | LOW | installer scripts + 1 CLI module | 60-90% token savings |
| 2 | **addyosmani/agent-skills** | 77.3k | LOW | 10 new SKILL.md files | TDD, security, perf, observability |
| 3 | **emilkowalski/skills** | 9.8k | LOW | 5 new SKILL.md files | Design quality, animation polish |
| 4 | **loop-engineering patterns** | 7.1k | LOW | 4 new SKILL.md + 1 CLI module | loop-cost, CI sweeper, PR babysitter |

### Wave 2: Short-term (v1.2 Provider Mesh)

| # | Tool | Stars | Effort | Files to Change | Value |
|---|------|-------|--------|-----------------|-------|
| 5 | **codebase-memory-mcp** | 30.1k | MEDIUM | tool manifest + adapter + Brain wire | Code intelligence, 99% token reduction |
| 6 | **TencentDB-Agent-Memory** | 8.5k | MEDIUM | Hermes plugin + config + CLI | Long-term memory, 61% token reduction |
| 7 | **OmniRoute** | 15.7k | HIGH | sidecar control + provider mesh + gateway routes | 237 providers, compression |

### Wave 3: Medium-term (v1.2–v1.3)

| # | Tool | Stars | Effort | Files to Change | Value |
|---|------|-------|--------|-----------------|-------|
| 8 | **page-agent** | 26k | MEDIUM | tool manifest + adapter | In-page browser automation |
| 9 | **stealth-browser-mcp** | 1.5k | MEDIUM | tool manifest + adapter + venv | Anti-bot browser automation |
| 10 | **reverse-skill** | 8.1k | LOW | 5 SKILL.md files (MIT only) | Pentest/reverse-engineering |

### Wave 4: Long-term (v2.0)

| # | Tool | Stars | Effort | Files to Change | Value |
|---|------|-------|--------|-----------------|-------|
| 11 | **meetily** | 23.1k | HIGH | module adapter + Tauri integration | Meeting transcription |
| 12 | **proxifly data** | 6.1k | LOW | web_fetch proxy rotation (runtime only) | Proxy support (GPL — no vendoring) |

### Reference Only (No Integration)

| # | Tool | Stars | Reason |
|---|------|-------|--------|
| 13 | **Ada-SI** | 67 | Pattern reference only, weak security |
| 14 | **anthropics/skills** | 160k | Document skills already in ATLAS, compare only |

---

## New ATLAS Capabilities Gained

### New CLI Commands (4)
- `atlas rtk status|gain|discover` — token compression analytics
- `atlas codebase status|index|search` — code intelligence
- `atlas memory status|search|persona` — agent memory
- `atlas loop cost|audit|sync` — loop engineering

### New Tools (2)
- `codebase_memory` — code graph queries (read-only)
- `page_agent` — in-page web automation (shell)
- `stealth_browser` — anti-bot browser (shell)

### New Skills (19)
- 10 from addyosmani (TDD, security, perf, observability, CI/CD, frontend, doubt, context, source, browser-testing)
- 5 from emilkowalski (design-eng, review-animations, improve-animations, animation-vocabulary, apple-design)
- 4 from loop-engineering (loop-cost, loop-audit, ci-sweeper, pr-babysitter)
- 5 from reverse-skill (apk-reverse, binary-reverse, js-reverse, pentest-tools, firmware-pentest)

### Provider Mesh Expansion
- OmniRoute: 237+ providers, 90+ free tiers, token compression
- FreeLLMAPI: retained as fallback

---

## License Compliance

| Tool | License | Can Vendor? |
|------|---------|-------------|
| RTK | Apache-2.0 | YES |
| codebase-memory-mcp | MIT | YES |
| TencentDB-Agent-Memory | MIT | YES |
| addyosmani/agent-skills | MIT | YES |
| emilkowalski/skills | MIT | YES |
| loop-engineering | MIT | YES |
| OmniRoute | MIT | YES |
| page-agent | MIT | YES |
| stealth-browser-mcp | MIT | YES |
| reverse-skill | MIT (main) | YES (skip GPLv3 CTF) |
| meetily | MIT | YES |
| proxifly | **GPL-3.0** | **NO** (data feed only) |
| anthropics/skills | Apache 2.0 / source-available | Partial |

---

## Risk Summary

| Risk | Mitigation |
|------|------------|
| 38 unpushed commits | Push first, let CI validate |
| OmniRoute complexity | Evaluate before replacing FreeLLMAPI |
| GPL proxifly contamination | Runtime data consumption only, no vendoring |
| reverse-skill GPLv3 CTF | Import MIT skills only, reference CTF patterns |
| TencentDB maintenance | Corporate-backed, but monitor |
| Stealth browser ethics | Document authorized use only in tool manifest |

---

## Next Steps

1. **Operator review** of this master plan
2. **Push 38 commits** to validate CI
3. **Start Wave 1** integration (RTK + skills + patterns)
4. **Phase 10.8 execution** with new skills available
5. **Begin Wave 2** evaluation (codebase-memory + TencentDB + OmniRoute)

---

*Master plan complete. 14 repos analyzed, 12 integrable, 7 reports produced.*
