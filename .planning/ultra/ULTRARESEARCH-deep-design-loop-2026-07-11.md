# ULTRARESEARCH: Deep Analysis - emilkowalski/skills + cobusgreyling/loop-engineering

> Generated 2026-07-11
> Source repos: emilkowalski/skills (9.8k stars), cobusgreyling/loop-engineering (7.1k stars)
> Target: L2 ATLAS integration

---

## 1. emilkowalski/skills - Complete Analysis

### 1.1 Repository Metadata

| Field | Value |
|-------|-------|
| URL | https://github.com/emilkowalski/skills |
| Stars | 9.8k |
| License | MIT |
| Commits | 35 |
| Language | Markdown (SKILL.md files) |
| Author | Emil Kowalski (Vercel, Linear, Sonner) |
| Install | npx skills@latest add emilkowalski/skills |
| Skill format | skills/<name>/SKILL.md with YAML frontmatter |

### 1.2 Complete Skill Inventory

#### Skill 1: emil-design-eng (Main Skill)

- File: skills/emil-design-eng/SKILL.md (679 lines, 26.7KB)
- Purpose: Encodes Emil Kowalski philosophy on UI polish, component design, animation decisions, and the invisible details that make software feel great.
- Content coverage:
  - Core philosophy (taste, unseen details, beauty as leverage)
  - Animation Decision Framework (should it animate? purpose? easing? speed?)
  - Easing curves (custom cubic-bezier, never ease-in for UI)
  - Duration budgets (100-300ms for UI elements)
  - Spring animations (when, config, interruptibility)
  - Component building (buttons, popovers, tooltips, CSS transitions vs keyframes)
  - CSS Transform mastery (translateY, scale, 3D, transform-origin)
  - clip-path animation patterns (inset, tabs, hold-to-delete, reveals, comparison sliders)
  - Gesture and drag interactions (momentum, damping, pointer capture, multi-touch, friction)
  - Performance rules (GPU-only properties, CSS variables caveat, Framer Motion caveats, WAAPI)
  - Accessibility (prefers-reduced-motion, touch hover states)
  - Sonner principles (developer experience, defaults, naming, edge cases)
  - Stagger animations, Debugging (slow motion, frame-by-frame, real devices)
  - Review checklist (14-item table)
- Review format: Mandatory Before/After/Why markdown table format

#### Skill 2: review-animations

- File: skills/review-animations/SKILL.md (112 lines, 7.93KB)
- Purpose: Specialized review skill - review animation and motion code against a high craft bar. Does ONE thing: review.
- Supporting files: STANDARDS.md (precise easing/duration/spring values)
- Key features:
  - Ten Non-Negotiable Standards (justified motion, frequency-appropriate, responsive easing, sub-300ms, origin correctness, interruptibility, GPU-only, accessibility, asymmetric timing, cohesion)
  - Aggressive Escalation Triggers (14 items flagged on sight)
  - Remedial Preference Hierarchy (delete > reduce > fix easing > fix origin > interruptible > GPU > asymmetric > polish > a11y)
  - Required Output: Findings table + Verdict with impact tiers
  - Verdict: Block or Approve with explicit criteria
  - disable-model-invocation: true (pure review, no code generation)

#### Skill 3: improve-animations

- File: skills/improve-animations/SKILL.md (101 lines, 7.73KB)
- Purpose: Survey a codebase animation code as a senior motion advisor, produce prioritized audit and self-contained implementation plans.
- Supporting files: AUDIT.md (8 audit categories), PLAN-TEMPLATE.md
- Key features:
  - 4-phase workflow: Recon > Audit > Vet/Prioritize > Write Plans
  - Three effort levels: quick (5 findings), standard (full table), deep (full table + polish)
  - Parallel subagents (one per audit category)
  - Plans fully self-contained (exact file paths, exact cubic-beziers, exact durations)
  - Never modifies source code - plans only
  - Invocation variants: bare, quick/deep, category focus, plan, execute, reconcile
  - plans/ output directory with README.md execution order

#### Skill 4: animation-vocabulary

- File: skills/animation-vocabulary/SKILL.md (173 lines, 12.8KB)
- Purpose: Reverse-lookup glossary - turns vague motion descriptions into exact terms.
- 12 categories, 80+ terms covering: Entrances/Exits, Sequencing/Timing, Movement/Transforms, State Transitions, Scroll, Feedback/Interaction, Easing, Spring Animations, Looping/Ambient Motion, Polish/Effects, Performance, Principles

#### Skill 5: apple-design

- File: skills/apple-design/SKILL.md (282 lines, 22.2KB)
- Purpose: Apple approach to interface design and fluid, physical motion, translated for the web.
- 17 sections: Response, Direct manipulation, Interruptibility, Springs, Velocity handoff, Momentum projection, Spatial consistency, Gesture hints, Rubber-banding, Gesture details, Frame smoothness, Materials/depth, Multimodal feedback, Reduced motion, Typography, 8 Design foundations, Process

### 1.3 Skill Format Specification

Frontmatter: name (required), description (required), disable-model-invocation (optional boolean).
Structure: Each skill is a single SKILL.md file. Supporting references co-located in same directory.
Discovery: npx skills@latest add <user>/<repo> copies all skills/*/SKILL.md into local skills directory.

### 1.4 Quality Assessment

| Dimension | Rating | Evidence |
|-----------|--------|----------|
| Documentation | Excellent | Every skill self-contained, comprehensive, production-tested |
| Tests | None | No test files, no CI workflow |
| CI | None | No .github/workflows/ |
| Maintenance | Active | 35 commits, 528 forks, referenced by Vercel ecosystem |
| Code quality | N/A | Pure Markdown - no code to test |
| Community | Strong | 9.8k stars, 42 watchers, referenced by shadcn/improve |

### 1.5 ATLAS Gap Fill Analysis

| ATLAS Gap | Filled by | Skill |
|-----------|-----------|-------|
| No design-specific skills | emil-design-eng, apple-design | Full design engineering philosophy |
| No animation review rigor | review-animations | 10 non-negotiable standards + verdict |
| No codebase animation audit | improve-animations | Recon-audit-plan workflow |
| No animation vocabulary | animation-vocabulary | 80+ term glossary |
| ultradesign has no animation depth | emil-design-eng, apple-design | Specific easing/spring/gesture rules |
| ultrareview has no design review mode | review-animations | Design-specific review standards |

### 1.6 Overlap with Existing ATLAS Skills

| Existing Skill | Overlap | Assessment |
|----------------|---------|------------|
| ultradesign | Low | ultradesign is UI/UX design process (diagnose/select/implement), not animation craft. Complementary. |
| ultrareview | Low | ultrareview is code forensics, not design review. Complementary. |
| ultraresearch | None | No overlap |
| l2-extra-marathon-review | Low | extra-marathon is general quality, not animation-specific |

**Verdict: emilkowalski/skills fills a COMPLETE GAP in ATLAS. Zero meaningful redundancy.**

---

## 2. cobusgreyling/loop-engineering - Complete Analysis

### 2.1 Repository Metadata

| Field | Value |
|-------|-------|
| URL | https://github.com/cobusgreyling/loop-engineering |
| Stars | 7.1k |
| License | MIT |
| Commits | 200 |
| Languages | JavaScript 55%, TypeScript 34.9%, Shell 5.1%, Python 5% |
| Author | Cobus Greyling |
| Latest Release | v1.5.0 (2026-06-30) |
| npm packages | 7 (loop-audit, loop-init, loop-cost, loop-sync, loop-context, loop-mcp-server, loop-worktree) |

### 2.2 Complete Pattern Inventory (7 Production Patterns)

| Pattern | ID | Cadence | Risk | Token Cost | Goal |
|---------|----|---------|------|------------|------|
| Daily Triage | daily-triage | 1d-2h | Low | Low | Morning scan of CI, issues, commits, chat |
| PR Babysitter | pr-babysitter | 5-15m | Medium | High | Shepherd PRs through review, CI, rebase, merge |
| CI Sweeper | ci-sweeper | 5-15m | Medium | Very high | React to failing CI with minimal fixes |
| Post-Merge Cleanup | post-merge-cleanup | 1d-6h | Low | Low | Tech debt cleanup after merges to main |
| Dependency Sweeper | dependency-sweeper | 6h-1d | Medium | Medium | Dependency + vulnerability updates |
| Changelog Drafter | changelog-drafter | 1d | Low | Low | Draft categorized release notes |
| Issue Triage | issue-triage | 2h-1d | Low | Low | Deduplicate, prioritize, label issues |

Registry: patterns/registry.yaml - machine-readable YAML with per-pattern fields (id, name, file, goal, cadence, risk, tools, skills, state, phases, human_gates, starter, week_one_mode, token_cost, cost breakdown).

### 2.3 Complete Tool Inventory (7 CLI Tools)

| Tool | npm Package | Purpose | Tests |
|------|-------------|---------|-------|
| loop-audit | @cobusgreyling/loop-audit | Loop Readiness Score (0-100), L0-L3 levels, 20+ signals | Yes |
| loop-init | @cobusgreyling/loop-init | Scaffold skills, state, budget files + Loop Ready score | Yes |
| loop-cost | @cobusgreyling/loop-cost | Token spend estimation by cadence and readiness level | Yes |
| loop-sync | @cobusgreyling/loop-sync | Drift detection between STATE.md and LOOP.md | Yes |
| loop-context | @cobusgreyling/loop-context | Stateful memory manager + circuit breaker for long runs | Unknown |
| loop-mcp-server | @cobusgreyling/loop-mcp-server | MCP runtime lookup for patterns, skills, state | Unknown |
| loop-worktree | @cobusgreyling/loop-worktree | Isolated git worktrees per fix attempt | Unknown |

loop-audit signals (20+): State file, triage skill, verifier skill, LOOP.md/config, AGENTS.md/CLAUDE.md, safety docs, GitHub workflows, MCP/connectors, worktree evidence, patterns/registry.yaml, loop-budget.md, loop-run-log.md, LOOP.md budget section, loop-budget skill, least-privilege tool scope, stall/no-progress detection, human-escalation path, loopActivity.

Loop Readiness Levels: L0 (draft), L1 (report-only), L2 (assisted auto-fix with verifier), L3 (unattended with human gates).

### 2.4 Five Building Blocks + Memory

| Primitive | Role |
|-----------|------|
| Automations / Scheduling | Discovery + triage on a cadence |
| Worktrees | Safe parallel execution |
| Skills | Persistent project knowledge |
| Plugins and Connectors (MCP) | Reach into real tools |
| Sub-agents | Maker / checker split |
| + Memory / State | Durable spine outside conversations |

### 2.5 Supporting Infrastructure

- Starters (starters/): Clone-and-run kits for Grok, Claude Code, Codex, Opencode
- Templates (templates/): Pattern template, skill templates
- Docs (docs/): Quickstart, pattern picker, primitives matrix, failure modes, anti-patterns, multi-loop coordination, operating loops, safety, concepts, loop design checklist, release process
- Examples (examples/): Grok, Claude Code, Codex, OpenClaw, Opencode, GitHub Actions
- Stories (stories/): Real wins and honest failures
- Budget files: loop-budget.md, loop-constraints.md, loop-run-log.md, LOOP.md, STATE.md
- CI: GitHub Actions for audit dogfooding + pattern validation

### 2.6 Quality Assessment

| Dimension | Rating | Evidence |
|-----------|--------|----------|
| Documentation | Excellent | Quickstart, pattern picker, primitives matrix, checklist, failure modes, anti-patterns |
| Tests | Good | test/ dirs in loop-audit, loop-cost, loop-sync, loop-init |
| CI | Yes | GitHub Actions for audit dogfooding + validate-patterns |
| Maintenance | Active | 200 commits, v1.5.0, 22 open issues, active discussions |
| Code quality | Good | TypeScript/JS monorepo, npm packages, tsconfig, dist/ builds |
| Community | Strong | 7.1k stars, 896 forks, adopters list, contributor ladder |

### 2.7 ATLAS Gap Fill Analysis

| ATLAS Gap | Filled by | Specific Asset |
|-----------|-----------|----------------|
| No loop-cost / token estimation | loop-cost CLI | Per-pattern token budgets, scenario modeling |
| No loop-audit / readiness scoring | loop-audit CLI | 20+ signal checks, L0-L3 scoring |
| No drift detection | loop-sync CLI | STATE.md / LOOP.md consistency |
| No production loop patterns | 7 patterns + registry.yaml | Battle-tested patterns with cost/gates |
| No starter scaffolding | loop-init CLI | Instant scaffold with budget + run-log |
| No circuit breaker | loop-context CLI | Stateful memory + circuit breaker |
| No MCP runtime lookup | loop-mcp-server CLI | Pattern/skill/state lookup |
| No worktree isolation tooling | loop-worktree CLI | Per-attempt isolated worktrees |
| No failure mode catalog | docs/failure-modes.md | Incident-style catalog |
| No anti-pattern catalog | docs/anti-patterns.md | Design mistake prevention |
| No multi-loop coordination docs | docs/multi-loop.md | When loops collide |
| No safety/denylist docs | docs/safety.md + SECURITY.md | Denylist, auto-merge, MCP scopes |

### 2.8 Overlap with Existing ATLAS / L2 Skills

| Existing Skill | Overlap | Assessment |
|----------------|---------|------------|
| l2-loop-engineering | Significant conceptual | Both define loop anatomy, verification gates, maker/checker. cobusgreyling adds: registry, 7 patterns, 7 CLI tools, scaffolding, cost estimation, drift detection, failure modes. L2 adds: GSD workflow, handoff routing, entropy, idempotency. Complementary. |
| l2-agent-handoff | Low | Different scope |
| l2-handoff-verifier | Low | Different scope |
| l2-entropy-reduction | None | Different scope |
| ultra | Low | Task decomposition vs loop automation |
| GSD workflow | Medium | Inline continuation vs scheduled autonomous loops |

**Verdict: cobusgreyling/loop-engineering fills CRITICAL INFRASTRUCTURE GAPS in ATLAS.**

---

## 3. Integration Plan

### 3.1 Priority: cobusgreyling/loop-engineering (Highest Impact)

Phase 1: Direct npm tool adoption (no code changes needed)

| Action | Command | Purpose |
|--------|---------|---------|
| Install loop-cost | npm install -g @cobusgreyling/loop-cost | Token estimation |
| Install loop-audit | npm install -g @cobusgreyling/loop-audit | Readiness scoring |
| Install loop-sync | npm install -g @cobusgreyling/loop-sync | Drift detection |
| Install loop-init | npm install -g @cobusgreyling/loop-init | Scaffold projects |

Phase 2: Pattern knowledge import

Create .mimocode/skills/l2-loop-patterns/ with:

| File to Create | Source | Changes |
|----------------|--------|---------|
| SKILL.md | New | Pattern router for ATLAS context |
| references/pattern-registry.md | registry.yaml | YAML to markdown, add ATLAS notes |
| references/pattern-templates/*.md (7) | patterns/*.md | Copy + ATLAS loop anatomy mapping |
| references/failure-modes.md | docs/failure-modes.md | Copy as-is |
| references/anti-patterns.md | docs/anti-patterns.md | Copy as-is |
| references/primitives-matrix.md | docs/primitives-matrix.md | Copy as-is |
| references/loop-design-checklist.md | docs/loop-design-checklist.md | Copy as-is |

Phase 3: Update l2-loop-engineering SKILL.md

Add to Skill Routing:
- Token cost estimation for a loop: run npx @cobusgreyling/loop-cost --pattern <name> --level L1
- Loop readiness audit: run npx @cobusgreyling/loop-audit . --suggest
- Drift detection: run npx @cobusgreyling/loop-sync .
- Production loop patterns: load l2-loop-patterns skill

Add to Common Pitfalls:
- Running loops without cost estimation - always run loop-cost before scheduling autonomous loops
- No readiness audit before enabling L2/L3 loops - run loop-audit first, start at L1

### 3.2 Priority: emilkowalski/skills (High Quality Impact)

Phase 1: Direct skill adoption

Create .mimocode/skills/design-engineering/ with:

| File to Create | Source | Changes |
|----------------|--------|---------|
| SKILL.md | New | Design-engineering router skill |
| references/emil-design-eng.md | skills/emil-design-eng/SKILL.md | Copy as-is |
| references/review-animations.md | skills/review-animations/SKILL.md | Copy as-is |
| references/improve-animations.md | skills/improve-animations/SKILL.md | Copy as-is |
| references/animation-vocabulary.md | skills/animation-vocabulary/SKILL.md | Copy as-is |
| references/apple-design.md | skills/apple-design/SKILL.md | Copy as-is |

Phase 2: Enhance ultradesign.md

Add to Step 6 VERIFY:
- Animation review via design-engineering skill (10 non-negotiable standards)
- No ease-in on UI elements
- All animations under 300ms
- GPU-only properties (transform + opacity only)
- prefers-reduced-motion honored

Add to Subagent Prompt:
- Follow animation rules from design-engineering skill (easing, duration, springs, accessibility)

### 3.3 Complete File Manifest

New files (19):

  mimocode/skills/l2-loop-patterns/SKILL.md
  mimocode/skills/l2-loop-patterns/references/pattern-registry.md
  mimocode/skills/l2-loop-patterns/references/pattern-templates/daily-triage.md
  mimocode/skills/l2-loop-patterns/references/pattern-templates/pr-babysitter.md
  mimocode/skills/l2-loop-patterns/references/pattern-templates/ci-sweeper.md
  mimocode/skills/l2-loop-patterns/references/pattern-templates/post-merge-cleanup.md
  mimocode/skills/l2-loop-patterns/references/pattern-templates/dependency-sweeper.md
  mimocode/skills/l2-loop-patterns/references/pattern-templates/changelog-drafter.md
  mimocode/skills/l2-loop-patterns/references/pattern-templates/issue-triage.md
  mimocode/skills/l2-loop-patterns/references/failure-modes.md
  mimocode/skills/l2-loop-patterns/references/anti-patterns.md
  mimocode/skills/l2-loop-patterns/references/primitives-matrix.md
  mimocode/skills/l2-loop-patterns/references/loop-design-checklist.md
  mimocode/skills/design-engineering/SKILL.md
  mimocode/skills/design-engineering/references/emil-design-eng.md
  mimocode/skills/design-engineering/references/review-animations.md
  mimocode/skills/design-engineering/references/improve-animations.md
  mimocode/skills/design-engineering/references/animation-vocabulary.md
  mimocode/skills/design-engineering/references/apple-design.md

Modified files (2):

  hermes/skills/l2/l2-loop-engineering/SKILL.md
  mimocode/skills/ultra/ultradesign.md

### 3.4 Integration Sequence

| Step | Action | Depends On | Risk |
|------|--------|------------|------|
| 1 | Install npm CLIs (loop-cost, loop-audit, loop-sync, loop-init) | None | Low |
| 2 | Create l2-loop-patterns skill | Step 1 | Low |
| 3 | Create design-engineering skill | None | Low |
| 4 | Update l2-loop-engineering SKILL.md | Steps 1-2 | Low |
| 5 | Enhance ultradesign.md | Step 3 | Low |
| 6 | Test loop-audit on ATLAS project | Step 1 | Low |
| 7 | Test loop-cost for known pattern | Step 1 | Low |

---

## 4. Risk Assessment

| Risk | Mitigation |
|------|------------|
| cobusgreyling patterns are tool-specific | Patterns in markdown - adapt triggers to ATLAS/Hermes |
| emilkowalski skills assume npx installer | Copy SKILL.md files directly |
| Skill bloat from reference files | Router SKILL.md loads references on demand |
| npm tools require Node.js | ATLAS already runs Node.js |
| Overlap with l2-loop-engineering | l2-loop-engineering becomes orchestrator routing to patterns |

---

## 5. Value Summary

### cobusgreyling/loop-engineering

| Capability | Current ATLAS | After Integration |
|------------|---------------|-------------------|
| Token cost estimation | None | Per-pattern budgets, scenario modeling |
| Loop readiness scoring | Manual checklist | 20+ signal automated audit, L0-L3 |
| Drift detection | None | STATE.md / LOOP.md consistency |
| Production patterns | 0 | 7 battle-tested patterns |
| Starter scaffolding | Manual | loop-init instant scaffold |
| Circuit breaker | None | loop-context for long runs |
| Failure mode catalog | None | Incident-style catalog |
| Anti-pattern catalog | None | Design mistake prevention |

### emilkowalski/skills

| Capability | Current ATLAS | After Integration |
|------------|---------------|-------------------|
| Design philosophy | Generic process | Emil specific rules |
| Animation review | None | 10 standards + verdict |
| Animation audit | None | 8-category recon-audit-plan |
| Animation vocabulary | None | 80+ term glossary |
| Apple design | None | 17-section reference |
| UI polish | Research only | Actionable review + audit |

---

## 6. Decision Record

| Decision | Rationale |
|----------|-----------|
| Import as knowledge, not fork | Patterns/SKILL.md are markdown - copy, keep npm tools as external CLIs |
| Do NOT merge l2-loop-engineering | L2 is the orchestrator; cobusgreyling patterns are implementations |
| Enhance ultradesign, not new skill | Minimal change - add animation check to existing VERIFY step |
| Use npm CLIs directly | Tools are standalone, MIT, well-maintained. Vendor only when customization needed |
