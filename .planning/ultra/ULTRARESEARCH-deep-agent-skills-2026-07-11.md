# ULTRARESEARCH  addyosmani/agent-skills Deep Integration Analysis

> Generated 2026-07-11 | 77.3k stars | 24 skills | MIT License
> Author: Addy Osmani (Chrome PM lead), Federico Bartoli, Joan Leon
> Repo: https://github.com/addyosmani/agent-skills

---

## Executive Summary

Addy Osmani's agent-skills is the most mature open-source skill system for AI coding agents. It provides 24 production-grade engineering skills organized by development lifecycle phase (Define, Plan, Build, Verify, Review, Ship), 4 specialist agent personas, 7 reference checklists, 8 slash commands, and multi-tool compatibility (Claude Code, Cursor, Codex, Copilot, Gemini CLI, Windsurf, Kiro, Antigravity).

**ATLAS fit: HIGH.** 7 of 7 ATLAS gaps are directly filled. 8 of 24 skills overlap with existing ATLAS Ultra skills (complementary, not duplicative). The remaining 15 skills fill ATLAS gaps or extend its engineering discipline.

**Recommended integration strategy:** Import 17 new skills that do not overlap with Ultra. Refactor 8 overlapping skills into thin wrappers that delegate to Ultra modes. Register all 24 in Hermes skill discovery with ATLAS-specific frontmatter.

---

## 1. Complete Skill Inventory (24 Skills)

### 1.1 Meta Phase

| # | Skill | Directory | Purpose | ATLAS Gap? |
|---|-------|-----------|---------|------------|
| 1 | using-agent-skills | using-agent-skills/ | Meta-router: maps incoming work to the right skill, defines shared operating rules, lifecycle sequencing. The orchestrator. | NO  ATLAS has Ultra mode router. BUT the shared operating behaviors (surface assumptions, manage confusion, push back, enforce simplicity, scope discipline) are **missing from ATLAS**. |

### 1.2 Define Phase

| # | Skill | Directory | Purpose | ATLAS Gap? |
|---|-------|-----------|---------|------------|
| 2 | interview-me | interview-me/ | One-question-at-a-time interview to extract what the user actually wants. Hypothesize + confidence scoring. 95% confidence stop condition. | NO  ATLAS has no equivalent. Gap. |
| 3 | idea-refine | idea-refine/ | Divergent/convergent thinking: restate as How Might We, generate 5-8 variations via 7 lenses (inversion, constraint removal, audience shift, combination, simplification, 10x, expert lens), stress-test, produce one-pager. | NO  ATLAS has no structured ideation skill. Gap. |
| 4 | spec-driven-development | spec-driven-development/ | Gated SPECIFY -> PLAN -> TASKS -> IMPLEMENT workflow. Spec template with 6 core areas (objective, commands, structure, code style, testing strategy, boundaries). Human review gates. | OVERLAP  ULTRAPLAN covers research/planning. But spec writing with human gates is missing. |

### 1.3 Plan Phase

| # | Skill | Directory | Purpose | ATLAS Gap? |
|---|-------|-----------|---------|------------|
| 5 | planning-and-task-breakdown | planning-and-task-breakdown/ | Dependency graph mapping, vertical slicing, task sizing (XS/S/M/L/XL), acceptance criteria, checkpoints, parallelization analysis. Outputs 	asks/plan.md and 	asks/todo.md. | PARTIAL OVERLAP  ULTRAPLAN does research-oriented planning. Task breakdown with sizing tables and dependency graphs is not in Ultra. |

### 1.4 Build Phase

| # | Skill | Directory | Purpose | ATLAS Gap? |
|---|-------|-----------|---------|------------|
| 6 | incremental-implementation | incremental-implementation/ | Thin vertical slices: implement -> test -> verify -> commit -> next. Slicing strategies (vertical, contract-first, risk-first). 5 rules (simplicity first, scope discipline, one thing, compilable, feature flags, safe defaults, rollback-friendly). | OVERLAP  ULTRAEXECUTE covers wave-based parallel execution. Incremental slice discipline complements it. |
| 7 | test-driven-development | 	est-driven-development/ | **Red-Green-Refactor. Prove-It Pattern (bug fixes). Test pyramid (80/15/5). Test sizes (small/medium/large). Beyonce Rule. DAMP > DRY in tests. Browser testing with DevTools. Anti-patterns table.** | **YES  ATLAS GAP: No formal TDD skill.** |
| 8 | context-engineering | context-engineering/ | 5-level context hierarchy (rules files -> specs -> source files -> error output -> conversation history). Brain dump, selective include, hierarchical summary patterns. MCP integration table. | PARTIAL OVERLAP  ATLAS has CLAUDE.md/AGENTS.md conventions. Formal context engineering skill is new. |
| 9 | source-driven-development | source-driven-development/ | Fetch official docs before coding. Source hierarchy (official docs > blog > web standards > browser compat). DETECT -> FETCH -> IMPLEMENT -> CITE pipeline. Deprecation detection. | NO  ATLAS has no equivalent. Gap. |
| 10 | doubt-driven-development | doubt-driven-development/ | **Adversarial fresh-context review: CLAIM -> EXTRACT -> DOUBT -> RECONCILE -> STOP (3 cycles max). Cross-model escalation (Gemini, Codex). Anti-rationalization: doubt theater detection.** | **YES  ATLAS GAP: No doubt-driven development skill.** |
| 11 | frontend-ui-engineering | rontend-ui-engineering/ | **Component architecture, design system adherence, state management hierarchy, WCAG 2.1 AA accessibility, responsive design, loading/transition patterns, anti-AI-aesthetic table.** | **YES  ATLAS GAP: No frontend UI engineering skill.** |
| 12 | api-and-interface-design | pi-and-interface-design/ | **Contract-first design, Hyrum's Law, One-Version Rule, error semantics, boundary validation, REST patterns, TypeScript interface patterns (discriminated unions, branded types).** | NO  ATLAS has no equivalent. Gap. |

### 1.5 Verify Phase

| # | Skill | Directory | Purpose | ATLAS Gap? |
|---|-------|-----------|---------|------------|
| 13 | browser-testing-with-devtools | rowser-testing-with-devtools/ | Chrome DevTools MCP: screenshot, DOM inspection, console analysis, network monitor, performance trace, accessibility tree. Security boundaries (profile isolation, untrusted browser data). | NO  ATLAS has no equivalent. Gap. |
| 14 | debugging-and-error-recovery | debugging-and-error-recovery/ | Stop-the-line rule. 6-step triage: reproduce -> localize -> reduce -> fix -> guard -> verify. Bisection, error-specific patterns, safe fallbacks, instrumentation guidelines. | PARTIAL OVERLAP  ULTRAREVIEW covers code forensics. Structured triage with bisection is complementary. |

### 1.6 Review Phase

| # | Skill | Directory | Purpose | ATLAS Gap? |
|---|-------|-----------|---------|------------|
| 15 | code-review-and-quality | code-review-and-quality/ | Five-axis review (correctness, readability, architecture, security, performance). Change sizing (~100/300/1000 lines). Severity labels (Critical/Required/Nit/Optional/FYI). Multi-model review pattern. Dependency discipline. Dead code hygiene. | OVERLAP  ULTRAREVIEW covers investigation/forensics. This is the review-gate counterpart. |
| 16 | code-simplification | code-simplification/ | Five principles: preserve behavior, follow conventions, clarity over cleverness, maintain balance, scope to what changed. Chesterton's Fence. Rule of 500. Language-specific guidance (TypeScript, Python, React). | NO  ATLAS has no equivalent. Gap. |
| 17 | security-and-hardening | security-and-hardening/ | **OWASP Top 10 prevention patterns. STRIDE threat modeling. Three-tier boundary system (Always/Ask First/Never). Supply-chain hygiene. SSRF prevention. AI/LLM security (OWASP Top 10 for LLMs).** | **YES  ATLAS GAP: No security hardening skill.** |
| 18 | performance-optimization | performance-optimization/ | **Measure-first approach. Core Web Vitals targets. Optimization workflow (measure -> identify -> fix -> verify -> guard). Anti-patterns (N+1, unbounded fetch, missing image optimization, unnecessary re-renders, large bundles, missing caching). Performance budgets.** | **YES  ATLAS GAP: No performance optimization skill.** |

### 1.7 Ship Phase

| # | Skill | Directory | Purpose | ATLAS Gap? |
|---|-------|-----------|---------|------------|
| 19 | git-workflow-and-versioning | git-workflow-and-versioning/ | Trunk-based development. Atomic commits. Semantic versioning. Change summaries. Pre-commit hygiene. Git worktrees for parallel agents. Save-point pattern. Changelog conventions. | NO  ATLAS has no equivalent. Gap. |
| 20 | ci-cd-and-automation | ci-cd-and-automation/ | **Shift Left principle. Quality gate pipeline (lint -> type check -> unit -> build -> integration -> e2e -> security -> bundle). GitHub Actions configs. Feature flag strategy. CI optimization.** | **YES  ATLAS GAP: No CI/CD guidance skill.** |
| 21 | deprecation-and-migration | deprecation-and-migration/ | Code-as-liability mindset. Compulsory vs advisory deprecation. Strangler pattern, adapter pattern, feature flag migration. Expand/contract for DB schema migrations. Zombie code. | NO  ATLAS has no equivalent. Gap. |
| 22 | documentation-and-adrs | documentation-and-adrs/ | ADR template and lifecycle. Inline documentation (why, not what). API docs (OpenAPI, JSDoc). README structure. Changelog maintenance. Agent-specific documentation. | NO  ATLAS has no equivalent. Gap. |
| 23 | observability-and-instrumentation | observability-and-instrumentation/ | **Structured logging. RED metrics. USE metrics. OpenTelemetry distributed tracing. Symptom-based alerting. Cardinality discipline. Define questions before instrumenting.** | **YES  ATLAS GAP: No observability skill.** |
| 24 | shipping-and-launch | shipping-and-launch/ | Pre-launch checklists (code quality, security, performance, accessibility, infrastructure, documentation). Feature flag lifecycle. Staged rollout with decision thresholds. Rollback strategy. Post-launch verification. | NO  ATLAS has no equivalent. Gap. |
---

## 2. Skill Format Analysis

### 2.1 Frontmatter Spec

Every skill uses YAML frontmatter with two required fields:

- **name**: Lowercase, hyphen-separated. Must match directory name.
- **description**: Third-person verb phrase plus Use when triggers. Max 1024 chars. Injected into system prompt.

The description is injected into the agent system prompt. It must tell the agent BOTH what the skill provides AND when to activate it.

### 2.2 Standard Section Anatomy

| Section | Purpose | Required? |
|---------|---------|-----------|
| Overview | 1-2 sentence elevator pitch | Recommended |
| When to Use | Trigger conditions + exclusions | Recommended |
| Core Process | Step-by-step workflow (the heart) | Required |
| Common Rationalizations | Excuse -> rebuttal table | Recommended |
| Red Flags | Observable violation signals | Recommended |
| Verification | Exit criteria checklist | Recommended |

### 2.3 Anti-Rationalization Tables

Every skill includes a table mapping common agent excuses to factual rebuttals. This is the most distinctive design feature.

### 2.4 Verification Gates

Every skill ends with a checklist of evidence requirements. No skill accepts seems right as completion.

### 2.5 Cross-Skill References

Skills reference each other by name, not by path. This enables tool-agnostic loading.

### 2.6 Progressive Disclosure

- SKILL.md is the entry point (recommended under 500 lines)
- Supporting references load only when needed
- This keeps token usage minimal during normal operation

---

## 3. Agent Personas

4 specialist personas for targeted reviews:

| Agent | Role | Perspective |
|-------|------|-------------|
| code-reviewer | Senior Staff Engineer | Five-axis code review with staff-engineer approval standard |
| test-engineer | QA Specialist | Test strategy, coverage analysis, Prove-It pattern |
| security-auditor | Security Engineer | Vulnerability detection, threat modeling, OWASP assessment |
| web-performance-auditor | Web Performance Engineer | Core Web Vitals audit with Quick/Deep modes and metric-honesty rule |

Design rules:
- Personas do not invoke other personas (orchestrator is the user or slash commands)
- Each persona has a single perspective, not balanced verdicts
- Personas are usable as subagents in parallel fan-out patterns
- Claude Code: plugin agents support name, description, tools, model, maxTurns, skills frontmatter

---

## 4. Reference Checklists (7)

| Reference | Covers |
|-----------|--------|
| definition-of-done.md | Project-wide standing bar every change clears (vs per-task acceptance criteria) |
| testing-patterns.md | Test structure, naming, mocking, React/API/E2E examples, anti-patterns |
| security-checklist.md | Pre-commit checks, auth, input validation, headers, CORS, OWASP Top 10, supply-chain, AI/LLM security |
| performance-checklist.md | Core Web Vitals targets, frontend/backend checklists, measurement commands |
| accessibility-checklist.md | Keyboard nav, screen readers, visual design, ARIA, testing tools |
| observability-checklist.md | On-call questions, structured logging, RED/USE metrics, tracing, symptom-based alerting, pre-launch gate |
| orchestration-patterns.md | Endorsed multi-persona orchestration patterns, anti-patterns, personas-do-not-invoke-personas rule |

---

## 5. Quality Assessment

### Tests
- Eval suite in evals/ directory
- CI runs automated evaluation of skill quality
- No traditional unit test suite for the skills themselves (skills are markdown, not code)

### CI/CD
- GitHub Actions in .github/workflows/
- 341 commits (active development)
- 5 releases (latest: 0.6.3, Jul 3 2026)
- 86 open PRs, 47 open issues (active community)

### Documentation
- README.md: comprehensive with quick-start, tool-specific setup guides
- docs/ directory: skill-anatomy.md, comparison.md, setup guides per tool
- CONTRIBUTING.md: contribution guidelines
- AGENTS.md, CLAUDE.md: agent context files

### Maintenance
- 77.3k stars, 8.3k forks (massive community validation)
- 3 named maintainers (Addy Osmani + 2 collaborators)
- MIT license (permissive, no IP concerns)
- Actively maintained: 341 commits, 5 releases, 86 open PRs

### Maturity Rating: HIGH
- Production-grade quality from Google/Chrome engineering culture
- Based on Software Engineering at Google and Google engineering practices guide
- Battle-tested workflows, not theoretical advice
- Multi-tool compatibility proves portability
---

## 6. ATLAS Fit Analysis

### 6.1 ATLAS Gaps Filled (7/7)

| ATLAS Gap | agent-skills Skill | Verdict |
|-----------|-------------------|---------|
| No formal TDD skill | test-driven-development | PERFECT FIT |
| No security hardening skill | security-and-hardening | PERFECT FIT |
| No performance optimization skill | performance-optimization | PERFECT FIT |
| No observability skill | observability-and-instrumentation | PERFECT FIT |
| No CI/CD guidance skill | ci-cd-and-automation | PERFECT FIT |
| No frontend UI engineering skill | frontend-ui-engineering | PERFECT FIT |
| No doubt-driven development skill | doubt-driven-development | PERFECT FIT |

### 6.2 Skills with ATLAS Overlap (8)

| agent-skills Skill | ATLAS Overlap | Relationship |
|-------------------|--------------|--------------|
| using-agent-skills | Ultra mode router | COMPLEMENTARY |
| spec-driven-development | ULTRAPLAN | COMPLEMENTARY |
| planning-and-task-breakdown | ULTRAPLAN | COMPLEMENTARY |
| incremental-implementation | ULTRAEXECUTE | COMPLEMENTARY |
| code-review-and-quality | ULTRAREVIEW | COMPLEMENTARY |
| debugging-and-error-recovery | ULTRAREVIEW | COMPLEMENTARY |
| context-engineering | CLAUDE.md/AGENTS.md | COMPLEMENTARY |
| source-driven-development | (none) | NEW to ATLAS |

### 6.3 Skills with No ATLAS Equivalent (9)

| Skill | ATLAS Value |
|-------|------------|
| interview-me | Extract real intent before building |
| idea-refine | Structured ideation with 7 lenses |
| api-and-interface-design | Contract-first, Hyrum Law, One-Version Rule |
| browser-testing-with-devtools | Chrome DevTools MCP runtime verification |
| code-simplification | Chesterton Fence, Rule of 500 |
| git-workflow-and-versioning | Trunk-based dev, atomic commits, semantic versioning |
| deprecation-and-migration | Code-as-liability, expand/contract DB migrations |
| documentation-and-adrs | ADR template, inline docs, changelog |
| shipping-and-launch | Pre-launch checklists, staged rollout, rollback |
---

## 7. Integration Plan

### 7.1 Files to Copy

Target directory: .mimocode/skills/ under the ATLAS project.

**New skills to import (17 skills that fill ATLAS gaps):**

1. test-driven-development/SKILL.md -> .mimocode/skills/tdd/SKILL.md
2. security-and-hardening/SKILL.md -> .mimocode/skills/security-hardening/SKILL.md
3. performance-optimization/SKILL.md -> .mimocode/skills/performance-optimization/SKILL.md
4. observability-and-instrumentation/SKILL.md -> .mimocode/skills/observability/SKILL.md
5. ci-cd-and-automation/SKILL.md -> .mimocode/skills/ci-cd-automation/SKILL.md
6. frontend-ui-engineering/SKILL.md -> .mimocode/skills/frontend-ui/SKILL.md
7. doubt-driven-development/SKILL.md -> .mimocode/skills/doubt-driven/SKILL.md
8. interview-me/SKILL.md -> .mimocode/skills/interview-me/SKILL.md
9. idea-refine/SKILL.md -> .mimocode/skills/idea-refine/SKILL.md
10. api-and-interface-design/SKILL.md -> .mimocode/skills/api-design/SKILL.md
11. browser-testing-with-devtools/SKILL.md -> .mimocode/skills/browser-testing/SKILL.md
12. code-simplification/SKILL.md -> .mimocode/skills/code-simplification/SKILL.md
13. git-workflow-and-versioning/SKILL.md -> .mimocode/skills/git-workflow/SKILL.md
14. deprecation-and-migration/SKILL.md -> .mimocode/skills/deprecation-migration/SKILL.md
15. documentation-and-adrs/SKILL.md -> .mimocode/skills/documentation-adr/SKILL.md
16. shipping-and-launch/SKILL.md -> .mimocode/skills/shipping-launch/SKILL.md
17. source-driven-development/SKILL.md -> .mimocode/skills/source-driven/SKILL.md

**Reference checklists to import (7 files):**

Copy all 7 to .mimocode/skills/references/:
- references/definition-of-done.md
- references/testing-patterns.md
- references/security-checklist.md
- references/performance-checklist.md
- references/accessibility-checklist.md
- references/observability-checklist.md
- references/orchestration-patterns.md

**Agent personas to import (4 files):**

Copy all 4 to .mimocode/skills/agents/:
- agents/code-reviewer.md
- agents/test-engineer.md
- agents/security-auditor.md
- agents/web-performance-auditor.md
### 7.2 Frontmatter Changes Needed

For ATLAS integration, each SKILL.md frontmatter needs these modifications:

1. Add ATLAS tags for skill discovery:
   tags: [atlas, lifecycle-phase]
2. Add skill path prefix in cross-references:
   Change test-driven-development references to atlas/test-driven-development
3. Add Hermes compatibility note in Overview
4. Preserve the original description (do not truncate the Use when triggers)

Example modified frontmatter:
---
name: test-driven-development
description: Drives development with tests. Use when implementing any logic.
tags: [atlas, build, tdd]
source: addyosmani/agent-skills
license: MIT
---

### 7.3 Skill Discovery Registration

ATLAS uses Hermes skill discovery. Registration steps:

1. Create .mimocode/skills/registry.json with all 24+ skills
2. Update Ultra mode router to reference imported skills as sub-skills
3. Update AGENTS.md to document the new skill inventory and when each applies
---

## 8. Key Design Decisions from agent-skills to Adopt

### 8.1 Anti-Rationalization Tables (MUST ADOPT)

The single most valuable design pattern. Every ATLAS skill should include a table of common excuses agents use to skip steps, with factual rebuttals. This prevents the agent from rationalizing its way out of following the process.

### 8.2 Verification Gates (MUST ADOPT)

Every skill must end with a checklist of evidence requirements. No skill accepts seems right as completion. Checklists must be specific and verifiable (test output, build result, screenshot, etc.).

### 8.3 Red Flags Section (SHOULD ADOPT)

Observable signs that the skill is being violated. Useful during code review and self-monitoring. Every ATLAS skill should include this.

### 8.4 Progressive Disclosure (MUST ADOPT)

Keep SKILL.md under 500 lines. Reference supporting files that are read only when the workflow reaches them. This keeps token usage minimal.

### 8.5 When NOT to Use (SHOULD ADOPT)

Every skill should include exclusion criteria. Not every task needs every skill. The negative triggers are as important as the positive triggers.

---

## 9. Risk Assessment

| Risk | Mitigation |
|------|------------|
| License compatibility | MIT license. No IP concerns. Can copy and modify freely. |
| Skill format mismatch | agent-skills uses same frontmatter spec as ATLAS. Format is compatible. |
| Feature drift | Pin to specific commit/tag when importing. Track upstream releases. |
| Over-engineering risk | Only import 17 new skills. Do not import all 24 wholesale. |
| Ultra skill deprecation | Do NOT deprecate Ultra modes. agent-skills skills complement, not replace. |
| Context bloat | Progressive disclosure design keeps token usage manageable. |
| Hermes compatibility | Skills are plain Markdown. Hermes loads them by path. No special runtime needed. |

---

## 10. Recommended Import Sequence

Phase 1 (Immediate - fills all 7 ATLAS gaps):
1. test-driven-development
2. security-and-hardening
3. performance-optimization
4. observability-and-instrumentation
5. ci-cd-and-automation
6. frontend-ui-engineering
7. doubt-driven-development

Phase 2 (High value, no overlap):
8. git-workflow-and-versioning
9. documentation-and-adrs
10. api-and-interface-design
11. code-simplification
12. shipping-and-launch

Phase 3 (Complementary to existing Ultra):
13. interview-me
14. idea-refine
15. source-driven-development
16. browser-testing-with-devtools
17. deprecation-and-migration

Always:
- Import all 7 reference checklists
- Import all 4 agent personas
- Update skill discovery registry

---

## Appendix: Source Repository Metadata

- Repository: https://github.com/addyosmani/agent-skills
- Stars: 77,300
- Forks: 8,300
- Commits: 341
- Releases: 5 (latest: 0.6.3, Jul 3 2026)
- Open PRs: 86
- Open Issues: 47
- License: MIT
- Languages: JavaScript 52.4%, Shell 47.6%
- Maintainers: Addy Osmani, Federico Bartoli, Joan Leon
- Tools supported: Claude Code, Cursor, Codex, Copilot, Gemini CLI, Windsurf, Kiro, Antigravity, OpenCode
- Compatibility: Works with any agent that accepts system prompts or instruction files