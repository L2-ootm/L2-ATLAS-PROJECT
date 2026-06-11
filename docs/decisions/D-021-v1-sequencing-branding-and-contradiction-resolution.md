# D-021 — v1.0 Sequencing, Two-Layer Branding Policy, and Cross-Doc Contradiction Resolution

**Date:** 2026-06-10
**Status:** Accepted
**Supersedes:** conflicting phase/scope statements in D-020 Phase Impact, `TWENTY_CRM_INTAKE_2026-06-08.md`, `.planning/phases/08-cockpit/CONTEXT.md` (native-only framing), and the 7-layer count in `DIVERSE_AGENT_MEMORY_FRAMEWORK.md`.

---

## Context

The 2026-06-10 full project audit (`docs/plans/2026-06-10_L2_FULL_AUDIT_30DAY_STABILIZATION_PLAN.md`) found the strategy docs internally contradictory on five points and found the v1.0 schedule blocked by an over-scoped Phase 8. This record resolves all of them in one place. Where this record conflicts with an earlier document, this record wins; earlier documents are annotated, not rewritten.

---

## Decisions

### 1. Phase 8 is web-first; the native shell becomes Phase 10 (v1.1)

- **Phase 8 — Operator Cockpit (web-first, native-portable):** SvelteKit/Svelte 5 with adapter-static (D-006), delivered in the browser against the Phase 7 API (REST + SSE) on `127.0.0.1`. Built under native-portability constraints so it ports into the Tauri webview unchanged: static adapter only, no SSR runtime, no browser-only APIs unsupported by WebView2, all OS-privileged features excluded.
- Phase 8 surfaces (4): mission list/detail/create; run timeline + live audit stream (SSE); wiki browser + FTS search; provider/model settings (read-only registry view + health). Memory inspection is satisfied in v1.0 by the wiki browser + provenance view; the full Surface 7 spec moves to Phase 10.
- **Phase 10 — Native Cockpit Shell (v1.1):** Tauri 2 + Rust shell wrapping the Phase 8 app. Owns: PTY/terminal pane (ConPTY), OS keychain, native approval popups, Tauri IPC capability model, CSP/threat model gate. `NATIVE_COCKPIT_STRATEGY.md` remains the definitive spec **for this phase**; D-005 (no Electron) and D-016 (Terax reference pillar) are unchanged.
- Rationale: COCKPIT-01..06 success criteria were already written for browsers ("renders in Chrome and Firefox", `npm run dev`). The native-only reframing of Phase 4.5 contradicted the requirements it claimed to deliver. Web-first resolves it without discarding the native strategy — it sequences it.

### 2. Canonical phase numbering

| Phase | Name | Milestone |
|---|---|---|
| 7 | API Gateway (+ SSE stream endpoint) | v1.0 |
| 8 | Operator Cockpit (web-first, native-portable) | v1.0 |
| 9 | Skill Inventory & Classification | v1.0 |
| 10 | Native Cockpit Shell (Tauri/Rust; absorbs old "Phase 12 Rust sidecar spike") | v1.1 |
| 11 | CRM via Twenty (sidecar wiring, custom objects, webhook flows, **CRM cockpit panel**) | v2.0 |
| 12 | Pulse Monitor | v2.0 |
| 13 | STT/TTS Voice | v2.0 |
| 14 | Floating Overlay / HUD | v2.0 |

- The CRM cockpit panel lands in **Phase 11**, not Phase 8. D-020's "Phase 8: CRM panel" line is superseded.
- "Phase 9" refers exclusively to Skill Inventory. The CRM phase is Phase 11.

### 3. Memory framework: six layers, one canonical document

- Canonical spec: `docs/architecture/AGENT_MEMORY_FRAMEWORK_STRATEGY.md` — **6 layers** (1 Hermes profile/session governance, 2 LLM Wiki, 3 semantic retrieval, 4 graph memory, 5 audit/event, 6 skill/procedure).
- `DIVERSE_AGENT_MEMORY_FRAMEWORK.md` is a conceptual input document; its 7-item candidate list (OpenGraph and Graphify counted separately) is consolidated into Layer 4.

### 4. Twenty vs. Graph Memory (Layer 4) boundary

- **Twenty is the system of record for external relationship data** (people, organizations, opportunities, interactions). ATLAS reads/writes it via API/MCP/webhooks only.
- **Layer 4 graph memory (v2.0) is a local derived knowledge graph over ATLAS-native entities** (missions, runs, sources, wiki pages, skills). It may reference Twenty records by stable ID; it never duplicates or re-stores Twenty's data.

### 5. Terax pattern reuse scope

Terax reuse is **architecture-level only**: Tauri 2 shell structure, `portable-pty` management, typed IPC boundary, keychain pattern, SSRF guard. **Zero UI-layer reuse** — Terax is React 19/Zustand; ATLAS is SvelteKit (D-006 locked). Any Phase 10 code copying requires Apache-2.0 NOTICE preservation and a fresh re-audit (per TERAX_DEEP_AUDIT).

### 6. Odysseus status

`docs/research/ODYSSEUS_AUDIT.md` (source-inspected at pinned SHA `8449bae`, MIT) is the authoritative record. Any earlier "concept-only / clone pending" phrasing is superseded.

### 7. FreeLLMAPI fork/vendor trigger criteria (closes the open-ended "fork last" clause)

Fork or vendor FreeLLMAPI **only if at least two** of the following hold; otherwise it stays a pinned, supervised sidecar:

1. Upstream unmaintained > 90 days while provider routes are rotting (breaking ATLAS task classes).
2. A production-relevant security advisory remains unpatched upstream > 30 days.
3. ATLAS requires a routing/gateway feature upstream has explicitly rejected.
4. An ATLAS distribution must bundle the gateway (no external-install option viable).

### 8. Two-layer branding policy (the "rebrand to L2/ATLAS" doctrine)

- **Layer 1 — Experience layer: fully L2/ATLAS-branded.** Cockpit UI, CLI (`atlas`), API, docs, packaging, and the **vendored Hermes-derived foundation** (MIT — rename permitted with license/attribution preserved). The operator only ever sees ATLAS.
- **Layer 2 — Infrastructure sidecars: pinned upstream, never rebranded.** FreeLLMAPI (MIT) and Twenty (AGPL-3.0) run as pinned upstream services behind ATLAS-branded adapters.
  - Twenty must never be forked/rebranded/embedded: AGPL network-service source obligations plus trademarked branding (reaffirms D-020 sidecar-only).
  - Rebranding a sidecar creates a fork-maintenance burden with no operator-visible benefit; the adapter already provides the ATLAS-branded surface.
- Terax and Odysseus remain pattern donors — no code import in v1.0.

### 9. Foundation vendoring (D-018 implementation start)

The pinned Hermes clone (SHA `e8b9369a9…`, MIT) is vendored into the repo at `foundation/atlas-hermes/` so foundation evolution is version-controlled in this repo (the `_EXTERNAL_REPOS/` clone is gitignored and cannot carry divergences):

- Vendored **unmodified at the pinned SHA** (minus `.git`), with upstream `LICENSE` preserved, plus `ATTRIBUTION.md` and `DIVERGENCE_LOG.md` at the vendor root.
- Every subsequent change to `foundation/atlas-hermes/` requires a `DIVERGENCE_LOG.md` entry (what/why/upstream-candidacy), per D-018's non-negotiable.
- `services/agent-runtime` gains the foundation as a path dependency; the `atlas_audit` plugin registers into it; an end-to-end boot smoke test becomes the standing merge gate.
- Namespace rebrand (`hermes` → ATLAS-native naming) is **staged, not big-bang**: operator-facing surfaces first (CLI entry point, banners, config dir), internal module renames only with the upstream test suite green, each step logged as a divergence.

---

## Consequences

- ROADMAP.md, PROJECT.md, STATE.md, 08-cockpit/CONTEXT.md updated to match (this date).
- `NATIVE_COCKPIT_STRATEGY.md` gains a sequencing-update note; its content is otherwise unchanged and governs Phase 10.
- D-020 Phase Impact annotated to point here.
- The v1.0 critical path shortens to: Phase 7 → Phase 8 (web) → stabilization — compatible with the 30-day plan.
