# ODYSSEUS-PAGE-BASELINE — reference page set + ATLAS gap analysis

Captured from the Odysseus reference pillar (`github.com/pewdiepie-archdaemon/odysseus`), one of
ATLAS's confirmed native-cockpit references (see `docs/architecture/
ATLAS_NATIVE_COCKPIT_PILLARS_TERAX_ODYSSEUS.md`, D-016). Operator note: *"what it has is the bare
minimum we need."* This doc enumerates Odysseus's surfaces and maps each to the ATLAS IA so we know
the **capability floor** to reach (and the surfaces we consciously exclude).

> ✅ **Direction reference — explicitly allowed.** We use Odysseus as a **UX / feature / direction
> reference**: which surfaces exist, what capabilities the floor includes, how flows are framed.
> Ideas, page sets, and feature inventories are not copyrightable — referencing them is unblocked and
> encouraged. ATLAS reimplements everything natively in its own celestial-heraldic system.
>
> ⚠️ **Direct code/asset reuse — gated.** The repo page shows **AGPL-3.0**; D-016's license census
> recorded **MIT**. These conflict, and AGPL is copyleft. So do **not** copy Odysseus source, CSS, or
> assets until the license is confirmed. The line: **borrow the direction, write our own code.**

## What Odysseus is

A self-hosted **personal AI workspace** — *"chat, agents, research, documents, email, notes, calendar,
and local model workflows."* Python backend + JS frontend, Docker at `:7000`. Chat-led, productivity-
oriented. ATLAS is a different animal — an **operator control center** for autonomous missions with
an audit thesis — so we adopt Odysseus's *capability floor*, not its IA.

## Odysseus surface enumeration (the baseline)

| # | Surface | Purpose / key content |
|---|---|---|
| 1 | **Chat + Agents** | Conversational interface over local/API models; tool integration; memory management |
| 2 | **Cookbook** | Model recommendations, downloads, and serving configuration (the model-ops surface) |
| 3 | **Deep Research** | Multi-step web research: source reading → report generation |
| 4 | **Compare** | Side-by-side model testing (A/B prompt across models) |
| 5 | **Documents** | Writing editor with AI suggestions; Markdown / HTML / CSV |
| 6 | **Email** | IMAP/SMTP inbox with triage, tags, summaries |
| 7 | **Notes, Tasks + Calendar** | Task management, reminders, CalDAV sync |
| 8 | **Extras** | Image gallery/editor, themes, web search, session management |

## Mapping to the ATLAS IA (gap analysis)

Legend: **HAVE** (live/planned in our IA) · **PARTIAL** (related surface exists, needs extension) ·
**GAP** (bare-minimum capability we lack) · **OUT** (out of operator-cockpit scope — conscious exclusion).

| Odysseus | ATLAS status | Where it lands / what's missing |
|---|---|---|
| Chat + Agents | **GAP** (biggest) | ATLAS leads with Missions/Runs, not direct conversation. We lack a **Console/Chat** surface for talking to the agent directly. Strong candidate to ADD: `/console` — conversational, tool-aware, memory-backed, with every turn audited. |
| Cookbook (model serving) | **PARTIAL** | We have **Models** (registry: provider/health/routing). We lack **serving/download/config** of local models. Extend Models → a "Cookbook" tab: recommend, pull, serve, configure. |
| Deep Research | **GAP / mission-type** | No research surface. Either a dedicated `/research` (multi-step web research → report) or a **mission template** "deep-research" that runs through the existing mission/run machinery. Prefer the mission-template route (reuses audit). |
| Compare | **GAP** | No model A/B. Add as a **Models** sub-view: same prompt across N models, side-by-side, with cost/latency. Operator-useful for routing decisions (D-017). |
| Documents (AI editor) | **PARTIAL** | **Codex** (`/wiki`) reads + edits markdown with provenance. A full **AI-assisted document editor** (suggestions, HTML/CSV) is richer. Extend Codex with an authoring mode, or a dedicated `/documents`. |
| Email | **OUT** | Personal productivity, not operator/audit. Excluded from the cockpit. (Could be a future sidecar, not core.) |
| Notes / Tasks / Calendar | **OUT** | Missions *are* the operator's tasks; audit is the record. Personal PIM is out of scope. |
| Extras: themes / sessions | **PARTIAL** | Folds into **System** (`/system`): theme (dark-only for now), session/auth state, mock-mode. |
| Extras: web search | **PARTIAL** | Belongs to the agent's tool layer (surfaced in run audit), and to Deep Research; not its own page. |
| Extras: image gallery/editor | **OUT** | Out of scope for the operator cockpit. |

## The "bare minimum" delta — capabilities ATLAS should ADD

Ordered by operator value, to reach the Odysseus floor *in the ATLAS register* (mission/audit-first):

1. **Console / Chat** (`/console`) — **NEW, high priority.** Direct conversational interaction with
   the agent: prompt, tool calls, streamed response, memory context. Every turn is an audited event
   (feeds the Ledger). This is the single biggest gap; Odysseus leads with it. Fits our SSE +
   audit infrastructure cleanly.
2. **Model Cookbook** — extend **Models** with serving/download/config of local models + recommendations.
3. **Compare** — model A/B sub-view under Models; informs task-class routing.
4. **Deep Research** — implement as a **mission template** first (reuses mission→run→audit), graduate
   to a dedicated surface only if it earns one.
5. **Documents authoring** — extend **Codex** with an AI-assisted editing mode (suggestions, export).

**Conscious exclusions (ATLAS is a cockpit, not a workspace):** Email, Calendar, Notes/Tasks, image
gallery. Document the *why* so the exclusion is a decision, not an oversight: these are personal-PIM
surfaces; ATLAS's job is autonomous operations + audit, not personal productivity.

## Net effect on our IA

The current planned IA (Observatory · Mission · Audit · Structure · System) already covers Odysseus
surfaces 2/5/8 partially and is stronger on audit. The **additions** to reach the floor:
- **`/console`** under a new top item or the MISSION pillar (conversational front door).
- **Models → Cookbook + Compare** (STRUCTURE pillar extension).
- **Deep-research mission template** (no new route initially).
- **Codex authoring mode** (STRUCTURE extension).

These fold into the existing `PAGES-SPEC.md` as additions; no IA teardown. Next session: decide whether
**Console** is a peer of Observatory (a primary front door) or sits under MISSION, then spec it against
the SSE/audit wiring (`HARNESS-WIRING.md`) — it reuses the same stream + ledger plumbing.

## Open items
- [ ] Resolve the **license** conflict (AGPL-3.0 on repo vs MIT in D-016) before reusing any code/assets.
- [ ] Decide **Console** placement (primary front door vs MISSION pillar).
- [ ] Confirm **Deep Research** as mission-template vs dedicated surface.
- [ ] Inspect Odysseus's actual screens (clone/run) to refine — this baseline is from the README; a
      live pass would sharpen the per-screen component lists.
