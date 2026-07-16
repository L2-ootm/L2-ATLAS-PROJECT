# Deep Analysis: agent-skills + anthropics/skills + loop-engineering

**Date:** 2026-07-11  
**Purpose:** Rigorous technical analysis for ATLAS skill integration

---

## 1. addyosmani/agent-skills — Engineering Skills (77.3k stars)

### Skill Format
```yaml
---
name: lowercase-hyphen-name
description: Guides agents through [task]. Use when…
---
# Overview → What this skill does
# When to Use → Triggering conditions
# Process → Step-by-step workflow
# Rationalizations → Excuses + rebuttals (anti-skip table)
# Red Flags → Signs something's wrong
# Verification → Evidence requirements
```

### Complete Skill Inventory (24 skills)

**Define (3):**
| Skill | Purpose | ATLAS Gap? |
|-------|---------|------------|
| interview-me | One-question-at-a-time requirements extraction | Partial — ATLAS has brainstorming |
| idea-refine | Divergent/convergent thinking for vague ideas | Overlaps with brainstorming |
| spec-driven-development | PRD before code | Maps to ATLAS plan phase |

**Plan (1):**
| Skill | Purpose | ATLAS Gap? |
|-------|---------|------------|
| planning-and-task-breakdown | Decompose specs into verifiable tasks | Maps to gsd-plan-phase |

**Build (7):**
| Skill | Purpose | ATLAS Gap? |
|-------|---------|------------|
| incremental-implementation | Vertical slices, feature flags | Complements gsd-execute-phase |
| test-driven-development | Red-Green-Refactor, test pyramid | **YES — ATLAS lacks formal TDD** |
| context-engineering | Right info at right time | Complements ATLAS context assembly |
| source-driven-development | Framework decisions from official docs | Useful for ATLAS development |
| doubt-driven-development | Adversarial fresh-context review | **YES — ATLAS lacks this** |
| frontend-ui-engineering | Component architecture, a11y, design systems | **YES — addresses cockpit UI quality** |
| api-and-interface-design | Contract-first, Hyrum's Law | Useful for gateway API design |

**Verify (2):**
| Skill | Purpose | ATLAS Gap? |
|-------|---------|------------|
| browser-testing-with-devtools | Chrome DevTools for live runtime | Useful for cockpit testing |
| debugging-and-error-recovery | Five-step triage | Overlaps with gsd-debug |

**Review (4):**
| Skill | Purpose | ATLAS Gap? |
|-------|---------|------------|
| code-review-and-quality | Five-axis review, change sizing | Overlaps with gsd-code-review |
| code-simplification | Chesterton's Fence, Rule of 500 | Useful for entropy reduction |
| security-and-hardening | OWASP Top 10, auth, secrets, deps | **YES — addresses SEC-3** |
| performance-optimization | Core Web Vitals, profiling | **YES — addresses perf gap** |

**Ship (5):**
| Skill | Purpose | ATLAS Gap? |
|-------|---------|------------|
| git-workflow-and-versioning | Trunk-based, atomic commits | Useful for ATLAS git discipline |
| ci-cd-and-automation | Shift Left, feature flags | **YES — addresses CI gap** |
| deprecation-and-migration | Code-as-liability | Useful for D-022 Rust migration |
| documentation-and-adrs | ADRs, API docs | Overlaps with ATLAS ADR system |
| observability-and-instrumentation | Structured logging, RED, OpenTelemetry | **YES — addresses monitoring gap** |

**Meta (1):** using-agent-skills — how to use the pack

### Agent Personas (4)
- code-reviewer (Senior Staff Engineer)
- test-engineer (QA Specialist)
- security-auditor (Security Engineer)
- web-performance-auditor (Web Performance Engineer)

### Quality
- **Tests:** Evals in `evals/` directory
- **CI:** GitHub Actions with validation
- **Maintenance:** 341 commits, 8.3k forks, Addy Osmani (Google Chrome team)
- **Documentation:** Excellent — comparison docs, setup guides per tool

### ATLAS Integration
- **Overlap with existing:** 8 skills overlap with ATLAS's GSD skills
- **New value:** 10 skills fill ATLAS gaps (TDD, security, performance, observability, CI/CD, frontend, doubt-driven, context-engineering, source-driven, browser-testing)
- **Format compatibility:** SKILL.md format is identical to ATLAS skill format
- **Effort:** LOW — copy SKILL.md files, add ATLAS-specific context to frontmatter

---

## 2. anthropics/skills — Official Anthropic Skills (160k stars)

### Skill Sets

**Example Skills (open source, Apache 2.0):**
- Creative: art, music, design
- Development: testing web apps, MCP server generation
- Enterprise: communications, branding

**Document Skills (source-available, NOT open source):**
- `skills/docx` — Word document creation/editing
- `skills/pdf` — PDF creation/extraction
- `skills/pptx` — PowerPoint creation
- `skills/xlsx` — Excel creation/manipulation

### Quality
- **Maintenance:** 43 commits, 18.9k forks, Anthropic official
- **Documentation:** Links to support.claude.com guides
- **License:** Apache 2.0 (examples), source-available (document skills)

### ATLAS Integration
- **ATLAS already has:** docx, pdf, pptx, xlsx skills in its registry
- **Value:** Reference implementation comparison. May have improvements.
- **Action:** Diff existing ATLAS skills against Anthropic's versions
- **License concern:** Document skills are source-available, not open source — need to check if ATLAS can reference them

---

## 3. cobusgreyling/loop-engineering — Loop Patterns (7.1k stars)

### Pattern Inventory (7 patterns)

| Pattern | Cadence | Token Cost | Week 1 |
|---------|---------|------------|--------|
| Daily Triage | 1d–2h | Low | L1 report |
| PR Babysitter | 5–15m | High | L1 watch |
| CI Sweeper | 5–15m | Very high | L2 cautious |
| Dependency Sweeper | 6h–1d | Medium | L2 patch-only |
| Changelog Drafter | 1d or tag | Low | L1 draft |
| Post-Merge Cleanup | 1d–6h | Low | L1 off-peak |
| Issue Triage | 2h–1d | Low | L1 propose-only |

### CLI Tools (7 tools)

| Tool | Purpose | ATLAS Equivalent |
|------|---------|------------------|
| loop-audit | Loop readiness score | None — **NEW** |
| loop-init | Scaffold skills+state+budget | None — **NEW** |
| loop-cost | Token spend estimator | None — **NEW** |
| loop-sync | Drift detection STATE↔LOOP | Maps to STATE.md updates |
| loop-context | Stateful memory + circuit breaker | Partial — ATLAS has context assembly |
| loop-mcp-server | MCP runtime lookup | None — **NEW** |
| loop-worktree | Isolated git worktrees | Maps to compose:worktree |

### Five Building Blocks
1. Automations/Scheduling — discovery + triage on cadence
2. Worktrees — safe parallel execution
3. Skills — persistent project knowledge
4. Plugins/Connectors — reach into real tools (MCP)
5. Sub-agents — maker/checker split
6. Memory/State — durable spine outside conversation

### Quality
- **Tests:** CI validation, loop-audit dogfood
- **Maintenance:** 200 commits, 896 forks, active community
- **npm packages:** 7 published packages
- **Documentation:** Excellent — quickstart, pattern picker, failure modes, anti-patterns

### ATLAS Integration
- **ATLAS already has:** l2-loop-engineering skill, GSD workflow
- **New value:**
  - `loop-cost` — token spend estimation (ATLAS lacks this)
  - `loop-audit` — loop readiness scoring (ATLAS lacks this)
  - `CI Sweeper` pattern — maps to ATLAS CI gap
  - `PR Babysitter` pattern — useful for ATLAS's unpushed commits
  - `loop-sync` drift detection — improves STATE.md discipline
- **Overlap:** Daily Triage, Issue Triage overlap with GSD workflow
- **Effort:** LOW — import patterns, add loop-cost to ATLAS CLI

---

*Analysis complete. 10+ skills fill ATLAS gaps. 3 CLI tools are new capabilities. Format is compatible.*
