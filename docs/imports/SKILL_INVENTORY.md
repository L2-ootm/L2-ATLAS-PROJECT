# ATLAS Skill Inventory & Classification

**Phase:** 9 — Skill Inventory & Classification
**Status:** Complete
**Date:** 2026-06-15
**Owner:** L2 Systems / ATLAS
**Requirements covered:** SKILLS-01, SKILLS-02, SKILLS-03, SKILLS-04
**Governing decision:** D-008 (skills classified and polished before becoming ATLAS-grade)

> Safety note on vocabulary: this document uses the words `token`, `secret`, `private`,
> and `requires_secrets` as **metadata schema vocabulary** (field names and classification
> labels). It contains **no secret values, no API keys, and no absolute operator paths**.
> L2/private skills are referenced by name and generic source label only — never by their
> local install path — to satisfy success criterion 5 (no personal/private paths in a
> public-facing manifest).

---

## 1. Purpose

ATLAS is built by evolving a vendored Hermes foundation (D-001/D-018). Hermes ships a large
skill catalog, and the operator's local environment adds GSD workflow skills, design/meta
skills, and private L2 skills. Shipping that union undifferentiated would (a) leak private
L2 context, (b) ship offensive/jailbreak skills by default, and (c) bury the handful of
skills an operator cockpit actually needs under ~260 entries.

This inventory classifies every skill source so ATLAS can ship a **small curated default
pack** plus clearly-bounded opt-in packs, and so anything that cannot ship publicly is
identified with a reason and an action. It is a **manually curated classification document**,
not an auto-discovery service, skill UI, marketplace, or runtime registry (those are
explicitly out of scope per the Phase 9 CONTEXT.md "What NOT to Build").

---

## 2. Classification rules

### 2.1 Classes (taxonomy — fixed, no additions per CONTEXT.md)

| Class | Meaning for ATLAS |
|---|---|
| `core` | Ships in the ATLAS Core Pack by default. Public-safe, broadly useful to any operator, minimal/no secret requirements. |
| `operator` | Ships in the opt-in Developer Operator Pack. Public-safe, useful, but credential-bearing, higher-risk, or specialist. |
| `l2-internal` | L2 Systems operating doctrine/brand. Useful internally, depends on L2/Davi context. Never a public default. |
| `personal-private` | Encodes personal decision frameworks or private data assumptions. Never shipped, never path-referenced publicly. |
| `experimental` | Unstable, prototype, or unproven for ATLAS use. Candidate for a future pack after polish. |
| `deprecated` | Superseded, unsafe-by-default, or excluded from ATLAS distribution. |
| `external-reference` | Inherited from the Hermes foundation (or an external framework like GSD). Remains available via its upstream source but is **not** ATLAS-curated default content. ATLAS does not re-own or re-document it. |

### 2.2 Per-item fields (SKILLS-01)

`skill / family · source group · class · public-safe (yes/no/needs-redaction) · default-pack candidate (yes/no) · polish required (none/light/medium/heavy) · reason · recommended action`

### 2.3 Pack metadata schema (SKILLS-02/03)

Core and Operator pack members carry: `name · version · class · autonomy_level · risk ·
requires_tools · requires_secrets · verification · public_safe`.

- **autonomy_level**: `read-only` (no side effects) · `assisted` (proposes, operator applies) · `supervised-write` (writes/acts behind an approval) · `autonomous` (runs unattended within guardrails).
- **risk**: `low` (local, reversible) · `medium` (external calls / credentialed) · `high` (mutates remote state, infra, or money).
- **public_safe**: `true` only if the skill body and examples are free of private context and safe to publish; the operator's own credentials supplied at runtime do not make a skill private.

### 2.4 Granularity

Decision-relevant skills (Core Pack, Operator Pack, L2 Pack, security/quarantine items) are
classified **per skill**. The bulk Hermes catalog that maps to a single class is classified
at **family level** (CONTEXT.md and the phase prompt both permit "skill or skill family"),
because per-skill rows there add length without changing any packaging decision.

---

## 3. Source groups inspected

| # | Source group | Location (generic) | Count | Inspection depth |
|---|---|---|---|---|
| SG-1 | Hermes foundation — default skills | `foundation/atlas-hermes/skills/` (vendored, in-repo) | 90 | Full category map + frontmatter shortlist |
| SG-2 | Hermes foundation — optional skills | `foundation/atlas-hermes/optional-skills/` (vendored, in-repo) | 84 | Full category map + frontmatter shortlist |
| SG-3 | GSD workflow framework | OpenClaw import (operator install) | ~70 | Enumerated by name; classified as a framework group |
| SG-4 | OpenClaw design/meta skills | OpenClaw import (operator install) | 13 | Enumerated by name; classified per family |
| SG-5 | L2 loop-engineering pack | local L2 Hermes pack (operator-private install) | 6 | Frontmatter via L2 registry (source-inventory only) |
| SG-6 | L2 Systems brand/mind skills | operator Claude skills (private) | 3 | Names + purpose (source-inventory only) |
| SG-7 | Security / offensive (dual-use) | within SG-1/SG-2 (`red-teaming`, `security`, `research/osint`) | ~7 | Flagged individually |

Notes:
- The pinned clone at `_EXTERNAL_REPOS/hermes-agent/skills/` is byte-identical to SG-1/SG-2
  and is **not** a separate ship target; the vendored `foundation/atlas-hermes` tree is the
  canonical surface ATLAS distributes.
- The operator's full local Hermes install (195 skills) is largely a mirror of SG-1/SG-2
  plus SG-3/SG-4/SG-5; its mirrored Hermes categories are not double-counted here.
- SG-5/SG-6 were inspected as **source inventory only**. No content was copied into the repo,
  and no local install path is reproduced in this document (CONTEXT.md prohibition + crit. 5).

---

## 4. Proposed ATLAS Core Pack

The smallest pack that makes an AI operator cockpit immediately useful: a methodology spine
(plan → test → debug → review), code/document comprehension, and the ATLAS-native knowledge
wiki. Every member is **public_safe: true** and **requires_secrets: none**, so the Core Pack
loads on a clean public install with zero credential setup.

```yaml
# ATLAS Core Pack — v1.0.0
core_pack:
  - name: systematic-debugging
    version: 1.0.0
    class: core
    autonomy_level: assisted
    risk: low
    requires_tools: [shell, read, grep]
    requires_secrets: none
    verification: "Given a seeded failing test, skill drives root-cause hypothesis before any fix is proposed."
    public_safe: true
    source: SG-1 skills/software-development/systematic-debugging

  - name: test-driven-development
    version: 1.0.0
    class: core
    autonomy_level: assisted
    risk: low
    requires_tools: [shell, test-runner]
    requires_secrets: none
    verification: "RED-GREEN-REFACTOR order enforced: a failing test exists before implementation in the transcript."
    public_safe: true
    source: SG-1 skills/software-development/test-driven-development

  - name: writing-plans
    version: 1.0.0
    class: core
    autonomy_level: assisted
    risk: low
    requires_tools: [write]
    requires_secrets: none
    verification: "Produces a plan file with bite-sized tasks, target paths, and acceptance criteria."
    public_safe: true
    source: SG-1 skills/software-development/writing-plans

  - name: requesting-code-review
    version: 1.0.0
    class: core
    autonomy_level: assisted
    risk: low
    requires_tools: [git, shell]   # gh optional, falls back to local diff
    requires_secrets: none
    verification: "Runs a security + quality pass over the working diff and emits findings before commit."
    public_safe: true
    source: SG-1 skills/software-development/requesting-code-review

  - name: codebase-inspection
    version: 1.0.0
    class: core
    autonomy_level: read-only
    risk: low
    requires_tools: [pygount]
    requires_secrets: none
    verification: "Reports LOC, language breakdown, and code/comment ratio for a target repo."
    public_safe: true
    source: SG-1 skills/github/codebase-inspection

  - name: ocr-and-documents
    version: 1.0.0
    class: core
    autonomy_level: assisted
    risk: low
    requires_tools: [pymupdf]      # marker-pdf optional for higher fidelity
    requires_secrets: none
    verification: "Extracts text from a sample PDF/scan and returns structured content."
    public_safe: true
    source: SG-1 skills/productivity/ocr-and-documents

  - name: llm-wiki
    version: 1.0.0
    class: core
    autonomy_level: supervised-write
    risk: low
    requires_tools: [filesystem]
    requires_secrets: none
    verification: "Builds/queries an interlinked markdown KB; aligns with ATLAS native Wiki runtime (D-004)."
    public_safe: true
    source: SG-1 skills/research/llm-wiki
```

Rationale for inclusions and notable exclusions:
- **llm-wiki** is the one domain-specific inclusion: ATLAS already ships an LLM Wiki runtime
  (D-004, Phase 6), so this skill is directly on-mission rather than generic.
- **GitHub PR/issue/review skills are deliberately *not* Core** — they need `GITHUB_TOKEN`.
  They move to the Operator Pack so the Core Pack stays credential-free.
- **Design, finance, mlops, creative, blockchain** skills are excluded from Core — high
  surface area, narrow audience, or credential/heavy-dependency requirements.

---

## 5. Full inventory table

### 5.1 ATLAS Core Pack (SG-1) — per skill

| Skill | Source | Class | Public-safe | Default-pack | Polish | Reason | Action |
|---|---|---|---|---|---|---|---|
| systematic-debugging | SG-1 | core | yes | yes | light | Pure methodology, no secrets, universal. | Add ATLAS metadata header; ship in Core. |
| test-driven-development | SG-1 | core | yes | yes | light | Pure methodology, no secrets. | Add metadata header; ship in Core. |
| writing-plans | SG-1 | core | yes | yes | light | Planning spine, no secrets. | Add metadata header; ship in Core. |
| requesting-code-review | SG-1 | core | yes | yes | light | Pre-commit quality gate, gh optional. | Add metadata header; ship in Core. |
| codebase-inspection | SG-1 | core | yes | yes | none | Read-only metrics, no secrets. | Ship in Core as-is. |
| ocr-and-documents | SG-1 | core | yes | yes | light | Document comprehension, no secrets. | Pin pymupdf dep; ship in Core. |
| llm-wiki | SG-1 | core | yes | yes | medium | On-mission with ATLAS Wiki runtime; align contract. | Reconcile with native Wiki API; ship in Core. |

### 5.2 Developer Operator Pack (SG-1/SG-2) — per skill (public_safe: true, opt-in)

| Skill | Source | Class | Public-safe | Default-pack | Polish | Reason | Action |
|---|---|---|---|---|---|---|---|
| github-auth | SG-1 | operator | yes | no | light | Credential setup (PAT/SSH). | Operator Pack; document token scope. |
| github-pr-workflow | SG-1 | operator | yes | no | light | Needs GITHUB_TOKEN; supervised remote writes. | Operator Pack. |
| github-issues | SG-1 | operator | yes | no | light | Needs GITHUB_TOKEN. | Operator Pack. |
| github-code-review | SG-1 | operator | yes | no | light | Needs GITHUB_TOKEN. | Operator Pack. |
| github-repo-management | SG-1 | operator | yes | no | medium | High-risk remote ops (create/fork/release). | Operator Pack; gate destructive ops. |
| docker-management | SG-2 | operator | yes | no | light | Local infra mutation; needs docker. | Operator Pack. |
| watchers | SG-2 | operator | yes | no | light | Autonomous polling; GITHUB_TOKEN optional. | Operator Pack. |
| fastmcp | SG-2 | operator | yes | no | light | Build/deploy MCP servers. | Operator Pack (ATLAS is MCP-aware). |
| mcporter | SG-2 | operator | yes | no | light | Call/auth MCP servers. | Operator Pack. |
| jupyter-live-kernel | SG-1 | operator | yes | no | light | Iterative Python exec; useful for analysis runs. | Operator Pack. |
| nano-pdf | SG-1 | operator | yes | no | light | Needs an LLM API key (operator-supplied). | Operator Pack; document key requirement. |
| python-debugpy | SG-1 | operator | yes | no | none | Local debugging, no secrets. | Operator Pack. |
| node-inspect-debugger | SG-1 | operator | yes | no | none | Local debugging, no secrets. | Operator Pack. |
| rest-graphql-debug | SG-2 | operator | yes | no | light | API debugging; target auth operator-supplied. | Operator Pack. |
| code-wiki | SG-2 | operator | yes | no | light | Generates codebase docs + diagrams. | Operator Pack. |
| subagent-driven-development | SG-1 | operator | yes | no | medium | Delegation pattern; assumes Hermes delegate_task. | Operator Pack; verify ATLAS runtime parity. |
| spike | SG-1 | operator | yes | no | none | Throwaway experiments. | Operator Pack. |
| plan | SG-1 | operator | yes | no | none | Plan-mode authoring. | Operator Pack. |

### 5.3 Hermes foundation — remaining default skills (SG-1) — family level

| Family | Source | Class | Public-safe | Default-pack | Polish | Reason | Action |
|---|---|---|---|---|---|---|---|
| apple/* (notes, reminders, findmy, imessage, macos-computer-use) | SG-1 | external-reference | yes | no | n/a | macOS-only; ATLAS is Windows/local-first. | Keep upstream; not in any ATLAS pack. |
| creative/* (22 skills: design-md, p5js, manim, sketch, claude-design, baoyu-*, ascii-*, …) | SG-1 | external-reference | yes | no | n/a | Useful but out of operator-cockpit scope; heavy overlap with SG-4 design skills. | Keep upstream; see dedup §8. |
| autonomous-ai-agents/* (claude-code, codex, opencode, hermes-agent, kanban-*) | SG-1 | external-reference | yes | no | n/a | Delegation to external CLIs; ATLAS has its own runtime. | Keep upstream; evaluate for v1.1. |
| devops/* (kanban-orchestrator, kanban-worker, webhook-subscriptions) | SG-1 | external-reference | yes | no | n/a | Hermes Kanban-specific. | Keep upstream. |
| media/* (spotify, youtube-content, gif-search, heartmula, songsee) | SG-1 | external-reference | yes | no | n/a | Consumer media; off-mission. | Keep upstream. |
| productivity/* (google-workspace, notion, airtable, linear, maps, powerpoint, teams-pipeline) | SG-1 | external-reference | yes | no | n/a | Credentialed SaaS integrations; per-operator opt-in later. | Keep upstream; candidate v1.1 Integrations Pack. |
| evaluation/*, inference/*, mlops/*, models/* (ML infra) | SG-1 | external-reference | yes | no | n/a | ML-engineering audience, not operator cockpit. | Keep upstream. |
| email/himalaya, note-taking/obsidian, smart-home/openhue, social-media/xurl, gaming/*, yuanbao | SG-1 | external-reference | yes | no | n/a | Niche/personal integrations. | Keep upstream. |
| data-science/jupyter-live-kernel | SG-1 | operator | yes | no | light | (Promoted to Operator Pack — see §5.2.) | — |
| dogfood (exploratory web QA) | SG-1 | experimental | yes | no | medium | Strong fit for ATLAS UAT, but browser-harness dependent. | Re-evaluate for Operator Pack after a parity test. |
| inference/obliteratus (abliterate refusals) | SG-1 | deprecated | needs-redaction | no | heavy | Model-safety circumvention. | Exclude from ATLAS distribution (see §6 B4). |
| red-teaming/godmode (LLM jailbreak) | SG-1 | deprecated | no | no | heavy | Jailbreak skill in the **default** tree. | **Release blocker** — remove/quarantine (see §6 B1). |

### 5.4 Hermes foundation — optional skills (SG-2) — family level

| Family | Source | Class | Public-safe | Default-pack | Polish | Reason | Action |
|---|---|---|---|---|---|---|---|
| devops/* (cli, docker-management, watchers, pinggy-tunnel) | SG-2 | operator / external-reference | yes | no | light | docker-management + watchers promoted to Operator Pack; rest upstream. | See §5.2. |
| mcp/* (fastmcp, mcporter) | SG-2 | operator | yes | no | light | Promoted to Operator Pack. | See §5.2. |
| finance/* (dcf, lbo, merger, comps, 3-statement, excel-author, pptx-author, stocks) | SG-2 | external-reference | yes | no | n/a | Specialist analyst audience. | Keep opt-in; candidate "Analyst Pack" post-v1.0. |
| mlops/* (~28: training, vector DBs, fine-tuning, serving) | SG-2 | external-reference | yes | no | n/a | ML-engineering audience. | Keep opt-in. |
| creative/* (blender-mcp, concept-diagrams, hyperframes, meme-generation, kanban-video) | SG-2 | external-reference | yes | no | n/a | Off-mission; overlaps SG-4. | Keep opt-in; see dedup §8. |
| research/* (duckduckgo-search, searxng-search, scrapling, arxiv-adjacent, qmd, parallel-cli, bioinformatics, darwinian-evolver, gitnexus, drug-discovery) | SG-2 | external-reference | yes | no | n/a | Web-search trio is a strong future Core candidate; rest specialist. | Evaluate duckduckgo/searxng for Operator Pack v1.1. |
| research/osint-investigation, research/domain-intel | SG-2 | experimental | needs-redaction | no | heavy | Dual-use reconnaissance. | Opt-in only; add authorization gate (see §6 B2). |
| security/1password | SG-2 | operator | yes | no | light | Legit secret-manager integration. | Operator Pack candidate (v1.1). |
| security/web-pentest, security/sherlock, security/oss-forensics | SG-2 | experimental | needs-redaction | no | heavy | Offensive/dual-use. | Opt-in only; authorization gate (see §6 B2). |
| blockchain/* (evm, solana, hyperliquid) | SG-2 | external-reference | yes | no | n/a | Read-only chain queries; niche. | Keep opt-in. |
| productivity/* (shopify, canvas, siyuan, telephony, here-now, shop-app, memento) | SG-2 | external-reference | yes | no | n/a | Credentialed SaaS; niche. | Keep opt-in. |
| autonomous-ai-agents/* (blackbox, openhands, honcho), web-development/page-agent, communication/one-three-one-rule, health/*, migration/openclaw-migration, email/agentmail | SG-2 | external-reference / experimental | yes | no | n/a | Mixed niche; some metadata-only stubs. | Keep opt-in. |

### 5.5 GSD workflow framework (SG-3, ~70 skills) — framework group

| Group | Source | Class | Public-safe | Default-pack | Polish | Reason | Action |
|---|---|---|---|---|---|---|---|
| GSD core lifecycle (gsd-new-project, gsd-plan-phase, gsd-execute-phase, gsd-verify-work, gsd-discuss-phase, gsd-progress, …) | SG-3 | external-reference | yes | no | n/a | ATLAS is *built with* GSD but does not *ship* GSD as operator content (phase prompt: GSD is a separate framework group, not auto default-pack). | Keep as the project's own build framework; do not bundle into ATLAS packs. |
| GSD review/quality (gsd-code-review, gsd-ui-review, gsd-secure-phase, gsd-eval-review, gsd-audit-*) | SG-3 | external-reference | yes | no | n/a | Same as above. | Keep as build framework. |
| GSD namespace routers (gsd-ns-*) + utilities (gsd-stats, gsd-health, gsd-cleanup, gsd-config, …) | SG-3 | external-reference | yes | no | n/a | Internal tooling for this repo's workflow. | Keep as build framework. |

### 5.6 OpenClaw design/meta skills (SG-4, 13) — per family

| Skill | Source | Class | Public-safe | Default-pack | Polish | Reason | Action |
|---|---|---|---|---|---|---|---|
| brainstorming | SG-4 | external-reference | yes | no | n/a | Duplicate of Hermes creative ideation + a process skill. | Keep upstream; dedup §8. |
| pdf / docx / pptx | SG-4 | external-reference | yes | no | n/a | Overlaps Hermes ocr-and-documents / powerpoint / finance authors. | Prefer Hermes-native doc skills; dedup §8. |
| playwright | SG-4 | experimental | yes | no | medium | Browser automation; overlaps dogfood. | Evaluate vs dogfood for a single UAT skill. |
| frontend-design / ui-ux-pro-max / ultradesign | SG-4 | external-reference | yes | no | n/a | Design skills; overlap each other + Hermes creative + L2 design system. | Consolidate; dedup §8. |
| ultraplan | SG-4 | external-reference | yes | no | n/a | Overlaps writing-plans + gsd-plan-phase. | Prefer one planning skill; dedup §8. |
| ultrareview | SG-4 | external-reference | yes | no | n/a | Overlaps requesting-code-review + gsd-code-review + l2-extra-marathon-review. | Consolidate review skills; dedup §8. |
| vault-scan | SG-4 | experimental | needs-redaction | no | heavy | Scans secret vaults; security-sensitive. | Do not ship; internal-only, audit first. |
| l2-mind | SG-4/SG-6 | personal-private | no | no | n/a | Encodes Davi's personal decision framework. | Never ship publicly (see §6 B3). |
| l2-build-workflow | SG-4/SG-6 | l2-internal | no | no | n/a | L2 premium-build doctrine. | L2 Systems Pack only. |

### 5.7 L2 Systems Pack (SG-5/SG-6) — per skill (l2-internal / personal-private, public_safe: false)

```yaml
# L2 Systems Pack — NOT a public default. public_safe: false for all members.
l2_systems_pack:
  - name: l2-loop-engineering        # class: l2-internal — umbrella/router for L2 GSD loops
    autonomy_level: assisted
    risk: low
    requires_secrets: none
    public_safe: false
    reason: "L2 operating doctrine; assumes L2/Davi context and local install layout."
  - name: l2-agent-handoff           # class: l2-internal — writes HANDOFF.md state
    public_safe: false
  - name: l2-handoff-verifier        # class: l2-internal — audits continuation state
    public_safe: false
  - name: l2-entropy-reduction       # class: l2-internal — report-first cleanup loop
    public_safe: false
  - name: l2-extra-marathon-review   # class: l2-internal — high-rigor review gate
    public_safe: false
  - name: l2-idempotency-antifragility-review  # class: l2-internal — retry/replay audit
    public_safe: false
  - name: l2-mind                    # class: personal-private — Davi's decision engine
    public_safe: false
    reason: "Personal decision framework; exclude from all public output and manifests."
  - name: l2-build-workflow          # class: l2-internal — L2 premium build doctrine
    public_safe: false
  - name: L2-Systems-Design-System   # class: l2-internal — L2 brand tokens/assets
    public_safe: false
    reason: "Brand IP; internal use only."
```

| Skill | Source | Class | Public-safe | Default-pack | Polish | Reason | Action |
|---|---|---|---|---|---|---|---|
| l2-loop-engineering | SG-5 | l2-internal | no | no | medium | L2 doctrine, local-layout assumptions. | L2 Pack only; sanitize before any extraction. |
| l2-agent-handoff | SG-5 | l2-internal | no | no | medium | Same. | L2 Pack only. |
| l2-handoff-verifier | SG-5 | l2-internal | no | no | medium | Same. | L2 Pack only. |
| l2-entropy-reduction | SG-5 | l2-internal | no | no | medium | Same. | L2 Pack only. |
| l2-extra-marathon-review | SG-5 | l2-internal | no | no | medium | Same. | L2 Pack only. |
| l2-idempotency-antifragility-review | SG-5 | l2-internal | no | no | medium | Same. | L2 Pack only. |
| l2-mind | SG-6 | personal-private | no | no | heavy | Personal decision framework. | Never ship; exclude from public manifests. |
| l2-build-workflow | SG-6 | l2-internal | no | no | medium | L2 build doctrine. | L2 Pack only. |
| L2-Systems-Design-System | SG-6 | l2-internal | no | no | n/a | L2 brand IP. | L2 Pack only. |

---

## 6. Public release blockers

| ID | Blocker | Where | Severity | Why it blocks public release | Required action |
|---|---|---|---|---|---|
| B1 | `red-teaming/godmode` (LLM jailbreak) ships in the **default** skills tree | `foundation/atlas-hermes/skills/red-teaming/godmode` (20 KB SKILL.md, confirmed present) | High | An ATLAS public default that includes a jailbreak skill is a reputational and policy non-starter; it loads on any clean install of the vendored foundation. | Remove from the vendored default tree (or quarantine under an explicitly-gated `optional-skills/security/` path) and record the divergence in `foundation/atlas-hermes/DIVERGENCE_LOG.md`. Exclude from every ATLAS manifest. |
| B2 | Dual-use offensive skills | `optional-skills/security/{web-pentest,sherlock,oss-forensics}`, `optional-skills/research/{osint-investigation,domain-intel}` | Medium | Acceptable as *opt-in* with authorization, but must never reach a default pack and need an explicit authorization/consent gate. | Keep opt-in only; add an authorization-acknowledgement gate before load; never list in Core/Operator manifests. |
| B3 | Personal/private skills must not be path-referenced publicly | `l2-mind` (personal-private); all SG-5/SG-6 L2 skills | High | Success criterion 5: no personal/private skill paths in any public-facing manifest; `l2-mind` encodes a personal framework. | Reference L2 skills by name + generic source label only (done in this doc). Exclude `l2-mind` entirely from public output. Never emit absolute local paths. |
| B4 | `inference/obliteratus` (abliterate model refusals) | `foundation/atlas-hermes/skills/inference/obliteratus` | Medium | Model-safety circumvention; same family as B1. | Exclude from ATLAS distribution; document in DIVERGENCE_LOG. |
| B5 | `vault-scan` scans secret stores | SG-4 (OpenClaw import) | Medium | Security-sensitive; could surface secrets if shipped/auto-run. | Internal-only; do not bundle; security-audit before any reuse. |

> None of these block **Phase 9 itself** (a classification document). They are blockers for a
> future *public distribution* milestone, surfaced now so the curation decisions are on record.

---

## 7. Redaction / polish queue

| Item | Current state | Needed before public ship | Effort |
|---|---|---|---|
| Core Pack metadata headers | Hermes-native frontmatter only | Add ATLAS fields (version, class, autonomy_level, risk, verification, public_safe) | light ×7 |
| `llm-wiki` ↔ ATLAS Wiki runtime | Standalone skill | Reconcile with the native Wiki API contract (D-004) so the skill drives the real runtime | medium |
| L2 pack skills | Contain L2/client/TDS-specific examples (per L2 registry note) | Sanitize private/client details before any extraction; keep `public_safe: false` until then | medium ×6 |
| `l2-mind` | Personal decision framework | Keep excluded from all public output (no redaction makes it public-safe) | n/a (exclude) |
| `godmode`, `obliteratus`, `vault-scan` | Present in source trees | Remove/quarantine + DIVERGENCE_LOG entry | heavy ×3 |
| `dogfood` / `playwright` UAT skills | Two overlapping browser-harness skills | Pick one, verify against ATLAS browser harness, add metadata | medium |
| Offensive security skills (B2) | Opt-in, no gate | Add authorization-acknowledgement gate | medium |

---

## 8. Deduplication / consolidation notes

Significant overlap exists across the four "process" families. ATLAS should pick **one
canonical skill per function** and treat the rest as `external-reference`.

| Function | Competing skills | Canonical for ATLAS | Rationale |
|---|---|---|---|
| Planning | `writing-plans` (SG-1), `software-development/plan` (SG-1), `ultraplan` (SG-4), `gsd-plan-phase` (SG-3) | `writing-plans` (Core) | In the vendored foundation, no secrets, lightweight; GSD/ultraplan stay framework-level. |
| Code review | `requesting-code-review` (SG-1), `ultrareview` (SG-4), `gsd-code-review` (SG-3), `l2-extra-marathon-review` (SG-5) | `requesting-code-review` (Core) | Vendored, public-safe; l2-extra-marathon-review stays L2-internal; GSD stays framework. |
| Debugging | `systematic-debugging` (SG-1), `gsd-debug` (SG-3) | `systematic-debugging` (Core) | Vendored, no runtime coupling. |
| Documents | `ocr-and-documents` + `powerpoint` + `nano-pdf` (SG-1), `finance/{excel,pptx}-author` (SG-2), `pdf`/`docx`/`pptx` (SG-4) | `ocr-and-documents` (Core) + Hermes `powerpoint`/`nano-pdf` (Operator) | Prefer Hermes-native; drop the SG-4 duplicates. |
| Design | `creative/{design-md,claude-design,sketch,popular-web-designs}` (SG-1), `creative/concept-diagrams`/`hyperframes` (SG-2), `frontend-design`/`ui-ux-pro-max`/`ultradesign` (SG-4), `L2-Systems-Design-System` (SG-6) | None in Core; `L2-Systems-Design-System` canonical **internally** | Design is off-mission for the operator cockpit; consolidate later if a design pack is scoped. |
| Web QA / browser | `dogfood` (SG-1), `optional dogfood/adversarial-ux-test` (SG-2), `playwright` (SG-4) | TBD — single UAT skill | Resolve in the polish queue; one browser-harness skill, not three. |
| Web search | `research/{duckduckgo-search,searxng-search,scrapling,parallel-cli}` (SG-2) | `duckduckgo-search` or `searxng-search` (Operator v1.1) | Pick one keyless search skill; the rest stay opt-in. |
| Humanize text | `creative/humanizer` (SG-1), `humanizer` (Claude skills) | `creative/humanizer` (external-reference) | Same skill via two sources; reference the vendored one. |

---

## 9. Pack recommendations

| Pack | Class | Members | public_safe | Default-installed | Notes |
|---|---|---|---|---|---|
| **ATLAS Core Pack** | core | 7 (see §4) | true | yes | Credential-free; loads on clean public install. The v1.0 default. |
| **Developer Operator Pack** | operator | ~18 (see §5.2) | true | no (opt-in) | Credentialed dev/devops/MCP skills; one-step enable. |
| **L2 Systems Pack** | l2-internal / personal-private | 9 (see §5.7) | false | never public | Internal only; sanitize before any extraction; `l2-mind` excluded entirely. |
| **Analyst Pack** (proposed, post-v1.0) | external-reference | finance/* (SG-2) | true | no | Specialist; defer to a later milestone. |
| **Integrations Pack** (proposed, v1.1) | external-reference | productivity SaaS + web-search (SG-1/SG-2) | yes | no | Credentialed SaaS; aligns with the parked integrations branch — do not build now. |
| **Quarantine (not a pack)** | deprecated | godmode, obliteratus, vault-scan, offensive security | no / needs-redaction | never | Excluded from distribution; DIVERGENCE_LOG entries. |

GSD (SG-3) is intentionally **not** a shipped pack: it is ATLAS's own build framework, not
operator-facing content.

---

## 10. Next actions

1. **(Blocker B1/B4)** Quarantine `red-teaming/godmode` and `inference/obliteratus` out of the
   vendored default tree and add `DIVERGENCE_LOG.md` entries. Owner: a future *public-hardening*
   phase, not Phase 9.
2. **Author the Core Pack manifest** (machine-readable) from §4 when a skill-registry loader
   exists — deferred: building the loader/registry is explicitly out of Phase 9 scope.
3. **Reconcile `llm-wiki`** with the native ATLAS Wiki runtime contract (D-004) before
   promoting it from "classified" to "shipped."
4. **Sanitize the L2 pack** (remove client/TDS-specific examples) before any public extraction;
   keep `public_safe: false` until done.
5. **Resolve the web-QA dedup** (dogfood vs playwright vs adversarial-ux-test) into one UAT skill.
6. **Live load test (success criterion 6)** — verify Core + Operator pack members load on a
   clean Hermes install. Deferred to runtime work: requires a skill-registry loader, which
   does not exist yet. All pack members are confirmed to resolve to existing vendored
   `SKILL.md` files in `foundation/atlas-hermes/` (static verification — see VERIFICATION.md).

---

## Appendix A — Counts

| Source group | Skills | Classified as |
|---|---|---|
| SG-1 Hermes default | 90 | 7 core, 11 operator, 1 experimental, 2 deprecated, rest external-reference |
| SG-2 Hermes optional | 84 | 7 operator, ~5 experimental (dual-use), rest external-reference |
| SG-3 GSD framework | ~70 | external-reference (build framework, not shipped) |
| SG-4 OpenClaw design/meta | 13 | external-reference / experimental; 2 map to L2 |
| SG-5 L2 loop-engineering | 6 | l2-internal |
| SG-6 L2 brand/mind | 3 | l2-internal (2) + personal-private (1) |
| **Total inspected** | **~266** | 7 core · ~18 operator · 9 l2/private · ~10 experimental · 3 deprecated · rest external-reference |
