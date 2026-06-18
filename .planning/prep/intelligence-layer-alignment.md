# Intelligence-Layer Alignment — Michaud "Obsidian-as-OS" → ATLAS

Status: design note (prep) · 2026-06-18 · feeds the Command Center milestone
Intent: **polish toward state-of-the-art, not a direction change.** The operator
surfaced Eric Michaud's Obsidian system (PKM-as-operating-system: Intelligence
Layer, IDE paradigm, systems-not-workflows, daily focus dashboard, daily agent
commands). This note extracts what aligns with ATLAS's goals/constraints and is
genuinely implementable, and folds it into the already-planned Command Center.

## The through-line

Michaud's insight: **passive stored data has zero value; knowledge must be in an
active, operational state, and the AI must live *inside* the environment where
that knowledge already is** (no blank-slate re-briefing every session).

ATLAS already embodies the *operational* half — missions/runs/audit are
executable, not a "graveyard." What it has not yet built is the **Intelligence
Layer**: ATLAS as the persistent, audited context an agent inherits automatically.
P4 (modular agents) just made the agent pluggable; this note is what we feed it.

The one hard divergence (a constraint, not a gap): ATLAS's substrate is the
**native cockpit + audited spine**, NOT Obsidian. We adopt the *philosophy* and
re-implement it inside ATLAS's one trust boundary. We do **not** adopt Obsidian.

## Alignment map (principle → ATLAS today → concrete implementable)

Tiers: **[A]** Command Center must-have · **[B]** high-value next · **[C]** later
fan-out · **[D]** explicitly not adopting.

| Michaud principle | ATLAS today | Concrete, implementable in ATLAS | Tier |
|---|---|---|---|
| **Intelligence Layer / AI memory** — agent inherits live context, no re-briefing | ClaudeCodeAgent starts blank; wiki (`wiki_pages`+FTS), audit, missions exist but aren't fed to the agent | **Context-assembly step** before a `claude_code` run: materialize the relevant ATLAS state — active Focus + framework, the run's Project, recent runs/audit summary, linked wiki pages — into the agent's working context (seed files in the project cwd / a generated `CLAUDE.md`, or SDK `options`). Solves the blank-slate problem natively. | **[A]** |
| **Escape the knowledge graveyard** — info exists to be executed | missions/runs are active; wiki can still rot | Command Center **Focus** entity + priorities (info that exists *to be worked*); wiki pages become agent context, not passive notes (read by the assembly step above) | **[A]** |
| **Daily Focus Dashboard** — one command center, execution-first | none yet (cockpit is mission/run views) | Command Center **CC-1** core loop (already planned): Current Focus, framework, priorities, drivers, quick-capture, live activity | **[A]** |
| **Daily Agent Commands** — one-trigger named automations | CLI `atlas mission run --agent`; no recurring/named commands | **Named operations**: saved (focus + agent + prompt) presets the operator triggers from the dashboard (e.g. "morning brief", "metrics review") that spawn a mission+run. Risk-gated. | **[B]** |
| **IDE paradigm** — CLIs/integrations in-environment, output→input, no alt-tab | gateway dispatch; Projects (P3) = working dirs; MCP proven via P4 spike | **CC-2 flagship integration** (GitHub/Workspace via MCP): agent reads a plan in ATLAS, executes, pushes from ATLAS — the run's artifacts feed the next focus/wiki. | **[B]** |
| **Systems, not workflows** — interconnected, compounding | audited spine already links mission→run→audit→artifact | Make outputs feed inputs: a run's summary/artifacts **auto-update** the Focus context + wiki, so the next agent run inherits them. The compounding loop. | **[B]** |
| **Metrics next to the AI** (CFO-style analysis on live data) | none (Metrics strip is planned UI only) | **CC-3**: metrics ingested into ATLAS entities; the agent reads live metrics from the spine for analysis missions | **[C]** |
| Obsidian/Markdown vault as substrate | — | Native cockpit + SQLite spine is the substrate; **not adopting Obsidian** | **[D]** |

## Trust deltas — where ATLAS must diverge from the naive copy

Michaud's system trusts a single operator and gives the AI broad native access.
ATLAS is audit-first and policy-gated; the Intelligence Layer must inherit that:

- **Context assembly must redact secrets.** Run `SECRET_PATTERNS` (already in
  `atlas_core.schemas.core`) over any wiki/audit/metric content before it enters
  an agent's context. The Intelligence Layer is a *trusted* channel — never let a
  credential leak into a prompt or the audit payload.
- **Every agent write stays audited + risk-gated.** "Agent native access" routes
  through the same AuditEvent bus + policy/approval gates (the risk-gated-hybrid
  decision). Reversible/internal = autonomous; outward-facing = approval card.
- **Credentials live in the auth store (paused phase 10.1), not the vault/notes.**
  Michaud keeps tokens loosely; ATLAS keeps them in the ATLAS-owned auth store —
  a hard prerequisite for CC-2 integrations.
- **Provenance.** Context fed to an agent should carry provenance (which source/
  run/wiki page), reusing `MemoryProvenance` — so an agent decision is traceable
  to the exact knowledge it inherited.

## How it folds into the existing roadmap (no new direction)

- **CC-1 (core loop)** gains the **Intelligence-Layer context-assembly step [A]** —
  the highest-leverage addition: ATLAS feeds the P4 agent its live state.
- **CC-1/CC-2** gain **Named Operations [B]** (daily agent commands) and the
  **output→input compounding loop [B]**.
- **CC-2/CC-3** already cover the IDE-paradigm integrations and metrics; this note
  just names the philosophy they serve.
- Prerequisites unchanged and reinforced: the **migration runner** (P4 finding),
  the **async run executor** (gateway can't drive long runs yet), and the
  **auth store (10.1)** for secure integrations.

## Constraints honored

- Native cockpit, one trust boundary (no Obsidian). · D-001 (no `foundation/`
  edits) · D-022 (SDK/MCP confined to Python agent-runtime; Rust = gateway) ·
  D-012/13 (schema is source of truth; any new entity is a frozen Pydantic model
  + additive migration via the runner). · YAGNI: 3D knowledge graph and broad
  integrations stay deferred until the core loop + flagship contract are proven.

## Next concrete artifacts (when Command Center starts)

1. `context_service` (or assembly step in the run path) that builds the
   secret-redacted, provenance-tagged agent context from Focus/Project/audit/wiki.
2. `Focus` entity + `focus_service` + gateway CRUD (CC-1).
3. Named-operation preset entity (CC-1/B).
4. Wire run outcomes → Focus/wiki update (compounding loop, CC-1/B).
