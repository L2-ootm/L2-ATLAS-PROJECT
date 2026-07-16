# ATLAS Integration Specification: External Skill & Pattern Libraries

> Generated 2026-07-11 via ULTRARESEARCH mode
> Libraries: addyosmani/agent-skills (24 skills), emilkowalski/skills (5 skills), cobusgreyling/loop-engineering (7 patterns + 6 CLI tools)
> ATLAS state: Phase 9/10 executing, 90% complete
> Document version: 2.0 (detailed rewrite)

---

## Table of Contents

1. Executive Summary
2. ATLAS Skill System Architecture
3. Library Inventory and Overlap Analysis
4. Exact Files to Create
5. Frontmatter Adaptation Rules
6. CLI Integration
7. Skill Discovery Registration
8. Verification and Rollback
9. Implementation Priority and Phasing
10. Risk Register
11. Source Attribution
12. Appendices

---

## 1. Executive Summary

Three external skill/pattern libraries offer 36 new capabilities that complement the ATLAS/Hermes skill ecosystem. After detailed source-code-level analysis of both the libraries and the ATLAS codebase:

- **12 skills have partial overlap** with existing Hermes skills (requiring adaptation, not duplication)
- **18 skills are genuinely new** (adding capabilities ATLAS currently lacks)
- **6 skills are skipped** (Hermes has superior native versions)
- **6 CLI tools** require wrapping in the ATLAS CLI Typer sub-app system
- **30 new SKILL.md files** will be created across 10 new/expanded categories

The integration adds approximately 27 net new skills (from 36 evaluated, minus 6 skips and 3 near-identical overlaps) plus 6 CLI tool wrappers. Total Hermes skill count rises from approximately 83 to approximately 110.

---

## 2. ATLAS Skill System Architecture

### 2.1 Skill Locations (Current State)

| Layer | Path | Count | Discovery |
|-------|------|-------|-----------|
| Hermes built-in | foundation/atlas-hermes/skills/<category>/<name>/SKILL.md | ~90 | Auto-loaded |
| Hermes optional | optional-skills/ (hermes skills install) | ~30 | Manual install |
| ATLAS project-level | .mimocode/skills/<name>/SKILL.md | 2 | Auto-discovered |
| External index-cache | skills/index-cache/*.json | 4 files | Cached repos |

### 2.2 SKILL.md Frontmatter Contract

`yaml
---
name: lowercase-hyphen-name          # Required. Matches directory name.
description: "<=60 chars, one sentence, ends with period."  # Required.
version: X.Y.Z                       # Required. Semver.
author: "Human Name (handle) + Hermes Agent"  # Required. Human first.
license: MIT                          # Required.
platforms: [linux, macos, windows]    # Required. OS gating.
metadata:
  hermes:
    tags: [tag1, tag2, ...]           # Required. For search/discovery.
    related_skills: [other-skill-1]   # Recommended. Cross-references.
---
`

### 2.3 Key Constraints (Hardline Standards)

1. **Tool references MUST use Hermes native tools**: terminal, read_file, search_files, patch, delegate_task, todo, web_extract, vision_analyze, browser_navigate, web_search
2. **No shell utility names in prose**: grep -> search_files, cat/head/tail -> read_file, sed/awk -> patch, find/ls -> search_files
3. **description <= 60 characters**: no marketing words
4. **Author credits human first**: contributor name + GitHub handle first, "Hermes Agent" second
5. **Scripts in scripts/**, references in references/, templates in templates/
6. **Tests at tests/skills/test_<skill>_skill.py**: stdlib + pytest only

### 2.4 ATLAS CLI Structure

The ATLAS CLI (services/agent-runtime/atlas_runtime/cli/main.py) uses Typer with sub-apps:

`
mission, project, db, gateway, module, tools, foundation, config, auth,
models, provider, channels, discord, tools, surface, terminal, golden,
runtime, wiki, graph, run, focus, goal, task, observe, operation
`

No skill or loop sub-app exists yet. Integration requires adding both.

### 2.5 ULTRA Mode Router

The ULTRA skill at .mimocode/skills/ultra/SKILL.md defines 5 modes: ultraplan, ultrareview, ultradesign, ultraexecute, ultraresearch. All use the subagent orchestration pattern.

---

## 3. Library Inventory and Overlap Analysis

### 3A. addyosmani/agent-skills (24 skills)

Source: https://github.com/addyosmani/agent-skills | License: MIT | Author: Addy Osmani

| # | Skill | Phase | Overlap | Action | Rationale |
|---|-------|-------|---------|--------|-----------|
| 1 | using-agent-skills | Meta | NEW | PORT | Meta-routing for skill packs |
| 2 | interview-me | Define | NEW | PORT | Structured requirements extraction |
| 3 | idea-refine | Define | PARTIAL | PORT+link | Divergent/convergent ideation |
| 4 | spec-driven-development | Define | PARTIAL | PORT+link | Contract-first specs |
| 5 | planning-and-task-breakdown | Plan | PARTIAL | PORT+link | Granular decomposition |
| 6 | incremental-implementation | Build | NEW | PORT | Vertical slice methodology |
| 7 | test-driven-development | Build | OVERLAP | SKIP | Hermes has 343-line native skill |
| 8 | context-engineering | Build | NEW | PORT | Context packing methodology |
| 9 | source-driven-development | Build | NEW | PORT | Doc-grounded decisions |
| 10 | doubt-driven-development | Build | NEW | PORT | Adversarial fresh-context review |
| 11 | frontend-ui-engineering | Build | NEW | PORT | Component architecture, a11y |
| 12 | api-and-interface-design | Build | NEW | PORT | Contract-first API design |
| 13 | browser-testing-with-devtools | Verify | NEW | PORT | Chrome DevTools workflow |
| 14 | debugging-and-error-recovery | Verify | OVERLAP | SKIP | Hermes has 367-line systematic-debugging |
| 15 | code-review-and-quality | Review | OVERLAP | SKIP | Hermes has github-code-review |
| 16 | code-simplification | Review | NEW | PORT | Chesterton's Fence, Rule of 500 |
| 17 | security-and-hardening | Review | NEW | PORT | OWASP Top 10, auth patterns |
| 18 | performance-optimization | Review | NEW | PORT | Core Web Vitals, profiling |
| 19 | git-workflow-and-versioning | Ship | PARTIAL | PORT+link | Trunk-based dev |
| 20 | ci-cd-and-automation | Ship | NEW | PORT | Pipeline design |
| 21 | deprecation-and-migration | Ship | NEW | PORT | Code-as-liability |
| 22 | documentation-and-adrs | Ship | NEW | PORT | ADR management |
| 23 | observability-and-instrumentation | Ship | NEW | PORT | RED metrics, tracing |
| 24 | shipping-and-launch | Ship | NEW | PORT | Pre-launch checklists |

**Summary:** SKIP: 3 | PORT: 19 | PARTIAL: 2

### 3B. emilkowalski/skills (5 skills)

Source: https://github.com/emilkowalski/skills | License: MIT | Author: Emil Kowalski

| # | Skill | Overlap | Action | Rationale |
|---|-------|---------|--------|-----------|
| 1 | emil-design-eng | NEW | PORT | Design engineering + animation |
| 2 | review-animations | NEW | PORT | Strict animation review |
| 3 | improve-animations | NEW | PORT | Codebase animation audit |
| 4 | animation-vocabulary | NEW | PORT | Animation terminology |
| 5 | apple-design | NEW | PORT | Apple HIG for web |

**Summary:** SKIP: 0 | PORT: 5 (new creative/design-engineering/ subcategory)

### 3C. cobusgreyling/loop-engineering (7 patterns + 6 CLI tools)

Source: https://github.com/cobusgreyling/loop-engineering | License: MIT | Author: Cobus Greyling

| # | Pattern/Tool | Overlap | Action | Rationale |
|---|-------------|---------|--------|-----------|
| 1 | daily-triage | PARTIAL | PORT+link | Scheduled triage cadence |
| 2 | pr-babysitter | NEW | PORT | PR monitoring loop |
| 3 | ci-sweeper | NEW | PORT | CI failure resolution |
| 4 | dependency-sweeper | NEW | PORT | Dependency update loop |
| 5 | post-merge-cleanup | NEW | PORT | Post-merge hygiene |
| 6 | changelog-drafter | NEW | PORT | Changelog generation |
| 7 | issue-triage | PARTIAL | PORT+link | Batch issue triage |
| 8 | loop-audit CLI | NEW | CLI WRAP | Loop readiness scoring |
| 9 | loop-cost CLI | NEW | CLI WRAP | Token spend estimation |
| 10 | loop-sync CLI | NEW | CLI WRAP | STATE.md drift detection |
| 11 | loop-init CLI | NEW | CLI WRAP | Scaffolding tool |
| 12 | loop-context CLI | NEW | CLI WRAP | Memory/circuit breaker |
| 13 | loop-worktree CLI | NEW | CLI WRAP | Isolated git worktrees |

**Summary:** SKIP: 0 | PORT: 7 | CLI WRAP: 6

---

## 4. Exact Files to Create

### 4.1 Directory Structure

All new skills go under foundation/atlas-hermes/skills/:

`
software-development/
  (12 existing unchanged)
  incremental-implementation/SKILL.md          # NEW - addyosmani
  context-engineering/SKILL.md                 # NEW - addyosmani
  source-driven-development/SKILL.md           # NEW - addyosmani
  doubt-driven-development/SKILL.md            # NEW - addyosmani
  code-simplification/SKILL.md                 # NEW - addyosmani
  api-and-interface-design/SKILL.md            # NEW - addyosmani

creative/
  (21 existing unchanged)
  design-engineering/                          # NEW subcategory
    SKILL.md                                   # NEW umbrella - emilkowalski
    review-animations/SKILL.md                 # NEW
    improve-animations/SKILL.md                # NEW
    animation-vocabulary/SKILL.md              # NEW
    apple-design-web/SKILL.md                  # NEW

security/                                      # NEW category
  security-and-hardening/SKILL.md              # NEW

performance/                                   # NEW category
  performance-optimization/SKILL.md            # NEW

frontend/                                      # NEW category
  frontend-ui-engineering/SKILL.md             # NEW

browser/                                       # NEW category
  browser-testing-with-devtools/SKILL.md       # NEW

devops/
  (3 existing unchanged)
  ci-cd-automation/SKILL.md                    # NEW
  deprecation-migration/SKILL.md               # NEW
  documentation-adrs/SKILL.md                  # NEW
  observability-instrumentation/SKILL.md       # NEW
  shipping-launch/SKILL.md                     # NEW

workflow/                                      # NEW category
  skill-router/SKILL.md                        # NEW meta
  interview-me/SKILL.md                        # NEW
  idea-refine/SKILL.md                         # NEW
  spec-driven-development/SKILL.md             # NEW
  planning-and-task-breakdown/SKILL.md         # NEW
  git-workflow/SKILL.md                        # NEW

loop-engineering/                              # NEW category
  loop-architecture/SKILL.md                   # NEW umbrella
  daily-triage-loop/SKILL.md                   # NEW
  pr-babysitter-loop/SKILL.md                  # NEW
  ci-sweeper-loop/SKILL.md                     # NEW
  dependency-sweeper-loop/SKILL.md             # NEW
  post-merge-cleanup-loop/SKILL.md             # NEW
  changelog-drafter-loop/SKILL.md              # NEW
  issue-triage-loop/SKILL.md                   # NEW
`

**Total: 30 new SKILL.md files + 7 DESCRIPTION.md files = 37 new files in skills/**

### 4.2 SKILL.md Frontmatter for All 30 Skills

Each skill follows the Hermes frontmatter contract. Here are all frontmatter blocks:

**software-development/incremental-implementation:**
`yaml
name: incremental-implementation
description: "Vertical-slice implementation: one complete feature at a time."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [implementation, vertical-slice, incremental, build, workflow]
    related_skills: [subagent-driven-development, test-driven-development, writing-plans]
`

**software-development/context-engineering:**
`yaml
name: context-engineering
description: "Pack optimal context for agent tasks: files, patterns, constraints."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [context, prompt-engineering, agent, optimization, workflow]
    related_skills: [ultra, skill-router, source-driven-development]
`

**software-development/source-driven-development:**
`yaml
name: source-driven-development
description: "Ground framework and library decisions in official documentation."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [documentation, research, framework, decision-making, workflow]
    related_skills: [ultraresearch, context-engineering, writing-plans]
`

**software-development/doubt-driven-development:**
`yaml
name: doubt-driven-development
description: "Adversarial fresh-context review: challenge every assumption."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [review, adversarial, quality, verification, testing]
    related_skills: [ultrareview, systematic-debugging, requesting-code-review]
`

**software-development/code-simplification:**
`yaml
name: code-simplification
description: "Chestertons Fence, Rule of 500, complexity budgeting for code."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [simplification, refactoring, complexity, clarity, code-quality]
    related_skills: [requesting-code-review, doubt-driven-development, writing-plans]
`

**software-development/api-and-interface-design:**
`yaml
name: api-and-interface-design
description: "Contract-first API design: schemas, versions, error handling."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [api, design, contract, openapi, rest, interface]
    related_skills: [spec-driven-development, ultraexecute, documentation-adrs]
`

**creative/design-engineering (umbrella):**
`yaml
name: design-engineering
description: "Design engineering: animation, easing, motion for web UIs."
version: 1.0.0
author: "Emil Kowalski (emilkowalski) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [design, animation, frontend, motion, easing, css]
    related_skills: [frontend-ui-engineering, review-animations, apple-design-web]
`

**creative/design-engineering/review-animations:**
`yaml
name: review-animations
description: "Strict review of animation quality, timing, and performance."
version: 1.0.0
author: "Emil Kowalski (emilkowalski) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [animation, review, performance, quality, css]
    related_skills: [design-engineering, improve-animations, frontend-ui-engineering]
`

**creative/design-engineering/improve-animations:**
`yaml
name: improve-animations
description: "Codebase-wide animation audit and systematic improvement."
version: 1.0.0
author: "Emil Kowalski (emilkowalski) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [animation, audit, improvement, frontend, css]
    related_skills: [design-engineering, review-animations, code-simplification]
`

**creative/design-engineering/animation-vocabulary:**
`yaml
name: animation-vocabulary
description: "Animation terminology reference: easing, springs, physics, timing."
version: 1.0.0
author: "Emil Kowalski (emilkowalski) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [animation, terminology, reference, motion, physics]
    related_skills: [design-engineering, review-animations]
`

**creative/design-engineering/apple-design-web:**
`yaml
name: apple-design-web
description: "Apply Apple HIG design principles to web interfaces."
version: 1.0.0
author: "Emil Kowalski (emilkowalski) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [apple, design, hig, web, ui, ios]
    related_skills: [design-engineering, frontend-ui-engineering]
`

**security/security-and-hardening:**
`yaml
name: security-and-hardening
description: "OWASP Top 10 prevention, auth patterns, secrets management."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [security, owasp, auth, secrets, hardening, vulnerability]
    related_skills: [code-simplification, doubt-driven-development, github-code-review]
`

**performance/performance-optimization:**
`yaml
name: performance-optimization
description: "Core Web Vitals, profiling, render optimization for web apps."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [performance, web-vitals, profiling, optimization, rendering]
    related_skills: [frontend-ui-engineering, design-engineering, ultrareview]
`

**frontend/frontend-ui-engineering:**
`yaml
name: frontend-ui-engineering
description: "Component architecture, accessibility, responsive design patterns."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [frontend, components, accessibility, responsive, architecture]
    related_skills: [design-engineering, apple-design-web, performance-optimization]
`

**browser/browser-testing-with-devtools:**
`yaml
name: browser-testing-with-devtools
description: "Chrome DevTools MCP workflow for runtime debugging and profiling."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [browser, devtools, debugging, profiling, chrome, testing]
    related_skills: [dogfood, frontend-ui-engineering, performance-optimization]
`

**devops/ci-cd-automation:**
`yaml
name: ci-cd-automation
description: "Pipeline design, feature flags, deployment automation patterns."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ci-cd, pipeline, deployment, automation, devops]
    related_skills: [shipping-launch, git-workflow, observability-instrumentation]
`

**devops/deprecation-migration:**
`yaml
name: deprecation-migration
description: "Code-as-liability: deprecation strategies, migration patterns."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [deprecation, migration, refactoring, maintenance, lifecycle]
    related_skills: [code-simplification, documentation-adrs, git-workflow]
`

**devops/documentation-adrs:**
`yaml
name: documentation-adrs
description: "Architecture Decision Records, API docs, documentation standards."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [documentation, adr, architecture, decisions, standards]
    related_skills: [spec-driven-development, source-driven-development, deprecation-migration]
`

**devops/observability-instrumentation:**
`yaml
name: observability-instrumentation
description: "RED metrics, OpenTelemetry, logging and tracing patterns."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [observability, metrics, tracing, logging, opentelemetry]
    related_skills: [performance-optimization, ci-cd-automation, security-and-hardening]
`

**devops/shipping-launch:**
`yaml
name: shipping-launch
description: "Pre-launch checklists, rollback procedures, launch day playbooks."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [shipping, launch, deployment, rollback, checklist]
    related_skills: [ci-cd-automation, observability-instrumentation, git-workflow]
`

**workflow/skill-router:**
`yaml
name: skill-router
description: "Meta-routing: select the right skill pack based on task intent."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [meta, routing, skill-selection, workflow, orchestrator]
    related_skills: [ultra, interview-me, idea-refine]
`

**workflow/interview-me:**
`yaml
name: interview-me
description: "Structured requirements extraction through targeted questions."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [requirements, interview, specification, clarification, workflow]
    related_skills: [ultraplan, idea-refine, spec-driven-development]
`

**workflow/idea-refine:**
`yaml
name: idea-refine
description: "Divergent/convergent thinking for idea refinement and scoping."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [ideation, brainstorming, refinement, scoping, creative]
    related_skills: [ultraplan, interview-me, writing-plans]
`

**workflow/spec-driven-development:**
`yaml
name: spec-driven-development
description: "Write API/contract specs before implementation code."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [specification, contract, api, openapi, tdd, workflow]
    related_skills: [api-and-interface-design, writing-plans, test-driven-development]
`

**workflow/planning-and-task-breakdown:**
`yaml
name: planning-and-task-breakdown
description: "Decompose complex goals into granular, independently testable tasks."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [planning, decomposition, tasks, estimation, workflow]
    related_skills: [writing-plans, ultraplan, incremental-implementation]
`

**workflow/git-workflow:**
`yaml
name: git-workflow
description: "Trunk-based dev, atomic commits, branching strategies for teams."
version: 1.0.0
author: "Addy Osmani (addyosmani) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [git, workflow, branching, commits, version-control]
    related_skills: [github-pr-workflow, ci-cd-automation, shipping-launch]
`

**loop-engineering/loop-architecture (umbrella):**
`yaml
name: loop-architecture
description: "Loop design patterns: cadence, budgets, circuit breakers, stop conditions."
version: 1.0.0
author: "Cobus Greyling (cobusgreyling) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [loop, automation, patterns, cadence, circuit-breaker]
    related_skills: [kanban-orchestrator, daily-triage-loop, ci-sweeper-loop]
`

**loop-engineering/daily-triage-loop:**
`yaml
name: daily-triage-loop
description: "Scheduled loop: scan issues/PRs, triage, update STATE.md."
version: 1.0.0
author: "Cobus Greyling (cobusgreyling) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [loop, triage, issues, prs, daily, automation]
    related_skills: [loop-architecture, kanban-orchestrator, github-issues]
    config:
      loop_cadence: "0 9 * * *"
      loop_level: "L1"
`

**loop-engineering/pr-babysitter-loop:**
`yaml
name: pr-babysitter-loop
description: "Monitor PR status, respond to reviews, track CI checks."
version: 1.0.0
author: "Cobus Greyling (cobusgreyling) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [loop, pr, monitoring, reviews, ci, automation]
    related_skills: [loop-architecture, github-pr-workflow, ci-cd-automation]
    config:
      loop_cadence: "*/15 * * * *"
      loop_level: "L1"
`

**loop-engineering/ci-sweeper-loop:**
`yaml
name: ci-sweeper-loop
description: "Detect and auto-resolve common CI failures (lint, format, type errors)."
version: 1.0.0
author: "Cobus Greyling (cobusgreyling) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [loop, ci, automation, lint, fix, continuous-integration]
    related_skills: [loop-architecture, ci-cd-automation, test-driven-development]
    config:
      loop_cadence: "0 * * * *"
      loop_level: "L2"
`

**loop-engineering/dependency-sweeper-loop:**
`yaml
name: dependency-sweeper-loop
description: "Check for dependency updates, security patches, compatibility."
version: 1.0.0
author: "Cobus Greyling (cobusgreyling) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [loop, dependencies, updates, security, maintenance]
    related_skills: [loop-architecture, security-and-hardening, shipping-launch]
    config:
      loop_cadence: "0 10 * * 1"
      loop_level: "L1"
`

**loop-engineering/post-merge-cleanup-loop:**
`yaml
name: post-merge-cleanup-loop
description: "Clean up merged branches, update docs, verify deployments."
version: 1.0.0
author: "Cobus Greyling (cobusgreyling) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [loop, post-merge, cleanup, branches, documentation]
    related_skills: [loop-architecture, git-workflow, shipping-launch]
    config:
      loop_cadence: "*/30 * * * *"
      loop_level: "L1"
`

**loop-engineering/changelog-drafter-loop:**
`yaml
name: changelog-drafter-loop
description: "Generate changelog from commits, PRs, and releases."
version: 1.0.0
author: "Cobus Greyling (cobusgreyling) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [loop, changelog, release, documentation, automation]
    related_skills: [loop-architecture, git-workflow, documentation-adrs]
    config:
      loop_cadence: "0 11 * * 5"
      loop_level: "L1"
`

**loop-engineering/issue-triage-loop:**
`yaml
name: issue-triage-loop
description: "Batch triage new issues: categorize, label, assign priority."
version: 1.0.0
author: "Cobus Greyling (cobusgreyling) + Hermes Agent"
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [loop, issue-triage, labels, priority, batch]
    related_skills: [loop-architecture, github-issues, daily-triage-loop]
    config:
      loop_cadence: "0 9 * * 1-5"
      loop_level: "L1"
`

### 4.3 New Category DESCRIPTION.md Files (7 files)

`
security/DESCRIPTION.md:
  "Security hardening, OWASP prevention, authentication patterns, and secrets management."

performance/DESCRIPTION.md:
  "Performance optimization, Core Web Vitals, profiling, and render optimization."

frontend/DESCRIPTION.md:
  "Frontend component architecture, accessibility (WCAG), and responsive design patterns."

browser/DESCRIPTION.md:
  "Browser-based testing, Chrome DevTools workflow, and runtime debugging."

workflow/DESCRIPTION.md:
  "Task routing, requirements extraction, ideation, specification, planning, and git workflow."

loop-engineering/DESCRIPTION.md:
  "Autonomous agent loop patterns: scheduled tasks, budgets, circuit breakers, and CLI tools."

creative/design-engineering/DESCRIPTION.md:
  "Design engineering: animation, easing, motion, and Apple HIG principles for web."
`

---

## 5. Frontmatter Adaptation Rules

When porting from any source library, apply these transformations:

### 5.1 Name Field
Source uses Title Case. ATLAS requires: lowercase, hyphen-separated, matches directory name.

### 5.2 Description Field
Source uses long multi-sentence descriptions. ATLAS requires: 60 chars max, one sentence, ends with period. No marketing words.

### 5.3 Author Field
Source: no author or single author. ATLAS requires: "Human Name (GitHub Handle) + Hermes Agent"

### 5.4 Tool Reference Mapping

| Source Reference | ATLAS/Hermes Equivalent |
|-----------------|------------------------|
| grep | search_files |
| cat / head / tail | read_file |
| sed / awk | patch |
| find / ls | search_files target='files' |
| git CLI | terminal("git ...") |
| npm / npx | terminal("npm ...") / terminal("npx ...") |
| curl / wget | web_extract |
| Shell pipelines | terminal("bash -c '...'") |

### 5.5 Related Skills Cross-References
Every ported skill must include related_skills pointing to ATLAS skills it complements.

### 5.6 Platform Gating
POSIX-only primitives -> platforms: [linux, macos]. Otherwise: platforms: [linux, macos, windows].

### 5.7 Source Attribution
Every ported SKILL.md must include a ## Source section at the end:
  "Adapted from {author}/{repo}: https://github.com/{author}/{repo}"

---

## 6. CLI Integration

### 6.1 Adding atlas skill Sub-App

File: services/agent-runtime/atlas_runtime/cli/main.py

Add after existing surface_app registration (around line 130):
`python
from atlas_runtime.cli.skill import skill_app
app.add_typer(skill_app, name="skill")
`

New file: services/agent-runtime/atlas_runtime/cli/skill.py

Commands:
- atlas skill list [--category X] [--json]  -- List all discovered skills
- atlas skill inspect NAME [--json]         -- Show SKILL.md frontmatter and preview
- atlas skill search QUERY [--json]         -- Search by name, description, or tags
- atlas skill install SOURCE [--skill-name] [--target-category]  -- Install from external repo

Implementation scan: scans foundation/atlas-hermes/skills/ recursively for SKILL.md files, extracts frontmatter with regex, filters by category/name/tags.

### 6.2 Adding atlas loop Sub-App

File: services/agent-runtime/atlas_runtime/cli/main.py

Add after existing surface_app registration:
`python
from atlas_runtime.cli.loop import loop_app
app.add_typer(loop_app, name="loop")
`

New file: services/agent-runtime/atlas_runtime/cli/loop.py

Commands:
- atlas loop audit [--path X] [--suggest] [--badge] [--json]  -- Loop readiness score
- atlas loop cost --pattern NAME [--level L1] [--cadence X]   -- Token spend estimate
- atlas loop sync [--path X] [--json]                          -- STATE.md drift detection
- atlas loop init [--path X] [--pattern X] [--tool hermes]    -- Scaffold loop files
- atlas loop context [--check] [--ledger X]                    -- Context/circuit breaker check
- atlas loop worktree ACTION [--run-id X] [--pattern X]        -- Isolated git worktrees

Each command wraps the corresponding npx package via subprocess.run():
`python
LOOP_TOOLS = {
    "audit": "@anthropic/loop-audit",
    "cost": "@anthropic/loop-cost",
    "sync": "@anthropic/loop-sync",
    "init": "@anthropic/loop-init",
    "context": "@anthropic/loop-context",
    "worktree": "@anthropic/loop-worktree",
}
`

Fallback: if npx is unavailable, print clear error message with remediation steps.

### 6.3 CLI Registration
No pyproject.toml change needed. The existing atlas_runtime.cli.main:app entry point handles sub-app discovery via app.add_typer() calls.

---

## 7. Skill Discovery Registration

### 7.1 Index Cache Update

After adding new skills, regenerate the index:
`python
# Scan all SKILL.md files under foundation/atlas-hermes/skills/
# Extract frontmatter (name, description, tags)
# Write to skills/index-cache/skills-index.json
`

### 7.2 Category Registration

New categories auto-discovered by scanning skills/*/ directories. No explicit registration needed beyond creating the directory and DESCRIPTION.md.

### 7.3 ULTRA Mode Router Update

Add to .mimocode/skills/ultra/SKILL.md Cross-Mode Dependencies:
`
External skill packs extend each mode:
- ultraplan: planning-and-task-breakdown, spec-driven-development, idea-refine
- ultrareview: code-simplification, security-and-hardening, performance-optimization
- ultradesign: frontend-ui-engineering, design-engineering, apple-design-web
- ultraexecute: incremental-implementation, subagent-driven-development, test-driven-development
- ultraresearch: context-engineering, source-driven-development, interview-me
`

---

## 8. Verification and Rollback

### 8.1 Pre-Installation Checklist

1. Validate SKILL.md exists at source
2. Validate frontmatter: name, description (60 chars), version
3. Check for shell tool references: grep/cat/head/tail/sed/awk in SKILL.md body
4. Check Hermes tool alignment: terminal, read_file, search_files, patch, delegate_task
5. Check for secrets: no hardcoded API keys or tokens
6. Check platform gates: platforms: matches actual script imports

### 8.2 Installation Verification

`ash
# 1. Verify SKILL.md parseable
python -c "import re,sys; from pathlib import Path;
[print(f'FAIL: {s}') for s in Path('skills').rglob('SKILL.md')
 if not re.search(r'^---
(.*?)
---', s.read_text(), re.DOTALL)]"

# 2. Verify no forbidden tool references
# 3. Verify index cache current
# 4. Run test suite
scripts/run_tests.sh tests/ -q
`

### 8.3 Rollback Procedure

`ash
rm -rf foundation/atlas-hermes/skills/<category>/<skill-name>/
# Regenerate index cache
git checkout -- services/agent-runtime/atlas_runtime/cli/main.py
rm -f services/agent-runtime/atlas_runtime/cli/skill.py
rm -f services/agent-runtime/atlas_runtime/cli/loop.py
scripts/run_tests.sh tests/ -q
`

### 8.4 Upgrade Procedure

`ash
# Diff upstream vs installed
diff <(curl -sL upstream_url) local_path/SKILL.md
# Re-port with ATLAS adaptations if meaningful changes
# Preserve ATLAS-specific additions (tool refs, delegate_task, related_skills, Source)
# Run verification suite
`

---

## 9. Implementation Priority and Phasing

### Phase 1: Core Integration (Week 1)

| Priority | Task | Effort |
|----------|------|--------|
| P0 | Create atlas skill CLI sub-app | 2h |
| P0 | Create atlas loop CLI sub-app | 3h |
| P0 | Port skill-router (meta-skill) | 1h |
| P0 | Port loop-architecture (umbrella) | 1h |
| P1 | Port interview-me, idea-refine | 2h |
| P1 | Port incremental-implementation, context-engineering | 2h |

### Phase 2: Engineering Skills (Week 2)

| Priority | Task | Effort |
|----------|------|--------|
| P2 | Port security-and-hardening | 1h |
| P2 | Port performance-optimization | 1h |
| P2 | Port code-simplification, api-and-interface-design | 2h |
| P2 | Port doubt-driven-development, source-driven-development | 2h |
| P2 | Port frontend-ui-engineering, browser-testing-with-devtools | 2h |

### Phase 3: DevOps and Ship Skills (Week 3)

| Priority | Task | Effort |
|----------|------|--------|
| P3 | Port ci-cd-automation, deprecation-migration | 2h |
| P3 | Port documentation-adrs, observability-instrumentation | 2h |
| P3 | Port shipping-launch, git-workflow | 2h |
| P3 | Port spec-driven-development, planning-and-task-breakdown | 2h |

### Phase 4: Design Engineering and Loop Patterns (Week 4)

| Priority | Task | Effort |
|----------|------|--------|
| P4 | Port all 5 emilkowalski/design-engineering skills | 3h |
| P4 | Port all 7 loop-engineering patterns | 4h |
| P4 | Wire loop-* CLIs into atlas loop sub-app | 2h |
| P4 | Regenerate index cache, full verification | 2h |

Total estimated effort: ~34 hours across 4 weeks.

---

## 10. Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Shell tool references leak into ported SKILL.md | Agent calls raw grep/cat | Pre-install grep check, automated validation |
| Upstream skill uses non-Hermes tool names | Agent hallucinates tool calls | Port with explicit tool mapping table |
| CLI npm dependencies unavailable offline | atlas loop commands fail | Cache npx packages, document offline fallback |
| Skill count bloat dilutes agent attention | Slower loading, lower quality | Skip overlaps (3 skipped), only port clear use cases |
| Frontmatter format mismatch | Skill discovery fails | Validate with Python script before committing |
| Upstream library changes | Ported skill becomes stale | Track upstream, document upgrade procedure |

---

## 11. Source Attribution

All ported skills retain original author attribution:

| Library | Author | License | Skills | URL |
|---------|--------|---------|--------|-----|
| agent-skills | Addy Osmani | MIT | 24 | https://github.com/addyosmani/agent-skills |
| skills | Emil Kowalski | MIT | 5 | https://github.com/emilkowalski/skills |
| loop-engineering | Cobus Greyling | MIT | 7+6 CLI | https://github.com/cobusgreyling/loop-engineering |

---

## 12. Appendices

### Appendix A: Skill Count After Integration

| Category | Before | After | Net New |
|----------|--------|-------|---------|
| software-development | 12 | 17 | +5 |
| creative | 21 | 26 | +5 |
| devops | 3 | 8 | +5 |
| github | 6 | 6 | 0 |
| research | 6 | 6 | 0 |
| workflow (NEW) | 0 | 6 | +6 |
| loop-engineering (NEW) | 0 | 8 | +8 |
| security (NEW) | 0 | 1 | +1 |
| performance (NEW) | 0 | 1 | +1 |
| frontend (NEW) | 0 | 1 | +1 |
| browser (NEW) | 0 | 1 | +1 |
| Other existing | ~35 | ~35 | 0 |
| **Total** | **~83** | **~110** | **+27 net** |

### Appendix B: Cross-Reference Matrix

| New Skill | Complements | Relationship |
|-----------|------------|--------------|
| skill-router | ultra (mode router) | Meta-routing for skill pack |
| interview-me | ultra ultraplan | Requirements extraction before planning |
| idea-refine | ultra ultraplan | Divergent/convergent thinking |
| spec-driven-development | writing-plans | Spec-first methodology |
| planning-and-task-breakdown | writing-plans | Granular task decomposition |
| incremental-implementation | subagent-driven-development | Vertical slice alternative |
| context-engineering | ultra (all modes) | Context packing |
| source-driven-development | ultra ultraresearch | Doc-grounded decisions |
| doubt-driven-development | ultrareview | Adversarial review layer |
| frontend-ui-engineering | ultradesign | Component architecture |
| api-and-interface-design | ultraexecute | Contract-first API design |
| browser-testing-with-devtools | ultrareview | Runtime verification |
| code-simplification | requesting-code-review | Chestertons Fence |
| security-and-hardening | github-code-review | Security review layer |
| performance-optimization | ultrareview | Performance audit |
| git-workflow | github-pr-workflow | Trunk-based dev |
| ci-cd-automation | kanban-orchestrator | Pipeline design |
| deprecation-migration | (none) | New: code-as-liability |
| documentation-adrs | (none) | New: ADR management |
| observability-instrumentation | (none) | New: RED metrics |
| shipping-launch | (none) | New: pre-launch checklists |
| design-engineering | (none) | New: motion/easing |
| review-animations | (none) | New: animation audit |
| improve-animations | (none) | New: animation survey |
| animation-vocabulary | (none) | New: animation terminology |
| apple-design-web | (none) | New: Apple design principles |
| loop-architecture | kanban-orchestrator | Loop design patterns |
| daily-triage-loop | kanban-orchestrator | Scheduled triage |
| pr-babysitter-loop | github-pr-workflow | PR monitoring |
| ci-sweeper-loop | kanban-orchestrator | CI failure resolution |
| dependency-sweeper-loop | (none) | New: dependency updates |
| post-merge-cleanup-loop | (none) | New: post-merge hygiene |
| changelog-drafter-loop | (none) | New: changelog generation |
| issue-triage-loop | github-issues | Batch issue triage |

### Appendix C: Tool Reference Mapping (Complete)

| Source Tool | ATLAS Equivalent | When to Use |
|------------|-----------------|-------------|
| grep "pattern" file | search_files("pattern", path="file") | Searching contents |
| cat file | read_file("file") | Reading files |
| head -n 50 file | read_file("file", limit=50) | First N lines |
| tail -n 50 file | read_file("file", offset=-50) | Last N lines |
| sed s/old/new/g file | patch("file", old="old", new="new") | String replacement |
| find . -name "*.py" | search_files("*.py", target="files") | Finding files |
| ls -la dir | search_files("*", path="dir", target="files") | Listing |
| git log --oneline -10 | terminal("git log --oneline -10") | Git history |
| curl URL | web_extract(url="URL") | Fetching web content |
| npm install | terminal("npm install") | Package install |
| python script.py | terminal("python script.py") | Running scripts |
| pytest tests/ | terminal("pytest tests/ -q") | Running tests |
| Subagent spawn | delegate_task(goal=..., context=...) | Parallel tasks |

### Appendix D: File Manifest

**SKILL.md files (30):**
`
foundation/atlas-hermes/skills/software-development/incremental-implementation/SKILL.md
foundation/atlas-hermes/skills/software-development/context-engineering/SKILL.md
foundation/atlas-hermes/skills/software-development/source-driven-development/SKILL.md
foundation/atlas-hermes/skills/software-development/doubt-driven-development/SKILL.md
foundation/atlas-hermes/skills/software-development/code-simplification/SKILL.md
foundation/atlas-hermes/skills/software-development/api-and-interface-design/SKILL.md
foundation/atlas-hermes/skills/creative/design-engineering/SKILL.md
foundation/atlas-hermes/skills/creative/design-engineering/review-animations/SKILL.md
foundation/atlas-hermes/skills/creative/design-engineering/improve-animations/SKILL.md
foundation/atlas-hermes/skills/creative/design-engineering/animation-vocabulary/SKILL.md
foundation/atlas-hermes/skills/creative/design-engineering/apple-design-web/SKILL.md
foundation/atlas-hermes/skills/security/security-and-hardening/SKILL.md
foundation/atlas-hermes/skills/performance/performance-optimization/SKILL.md
foundation/atlas-hermes/skills/frontend/frontend-ui-engineering/SKILL.md
foundation/atlas-hermes/skills/browser/browser-testing-with-devtools/SKILL.md
foundation/atlas-hermes/skills/devops/ci-cd-automation/SKILL.md
foundation/atlas-hermes/skills/devops/deprecation-migration/SKILL.md
foundation/atlas-hermes/skills/devops/documentation-adrs/SKILL.md
foundation/atlas-hermes/skills/devops/observability-instrumentation/SKILL.md
foundation/atlas-hermes/skills/devops/shipping-launch/SKILL.md
foundation/atlas-hermes/skills/workflow/skill-router/SKILL.md
foundation/atlas-hermes/skills/workflow/interview-me/SKILL.md
foundation/atlas-hermes/skills/workflow/idea-refine/SKILL.md
foundation/atlas-hermes/skills/workflow/spec-driven-development/SKILL.md
foundation/atlas-hermes/skills/workflow/planning-and-task-breakdown/SKILL.md
foundation/atlas-hermes/skills/workflow/git-workflow/SKILL.md
foundation/atlas-hermes/skills/loop-engineering/loop-architecture/SKILL.md
foundation/atlas-hermes/skills/loop-engineering/daily-triage-loop/SKILL.md
foundation/atlas-hermes/skills/loop-engineering/pr-babysitter-loop/SKILL.md
foundation/atlas-hermes/skills/loop-engineering/ci-sweeper-loop/SKILL.md
foundation/atlas-hermes/skills/loop-engineering/dependency-sweeper-loop/SKILL.md
foundation/atlas-hermes/skills/loop-engineering/post-merge-cleanup-loop/SKILL.md
foundation/atlas-hermes/skills/loop-engineering/changelog-drafter-loop/SKILL.md
foundation/atlas-hermes/skills/loop-engineering/issue-triage-loop/SKILL.md
`

**DESCRIPTION.md files (7):**
`
foundation/atlas-hermes/skills/security/DESCRIPTION.md
foundation/atlas-hermes/skills/performance/DESCRIPTION.md
foundation/atlas-hermes/skills/frontend/DESCRIPTION.md
foundation/atlas-hermes/skills/browser/DESCRIPTION.md
foundation/atlas-hermes/skills/workflow/DESCRIPTION.md
foundation/atlas-hermes/skills/loop-engineering/DESCRIPTION.md
foundation/atlas-hermes/skills/creative/design-engineering/DESCRIPTION.md
`

**CLI files (2):**
`
services/agent-runtime/atlas_runtime/cli/skill.py
services/agent-runtime/atlas_runtime/cli/loop.py
`

**Modified files (1):**
`
services/agent-runtime/atlas_runtime/cli/main.py  (add 2 import+add_typer lines)
`

**Total: 40 new files, 1 modified file.**
