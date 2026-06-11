# L2 ATLAS — Full Project Audit & 30-Day Stabilization Plan

Date: 2026-06-10
Inputs: .planning/{PROJECT,STATE,ROADMAP,RISKS}.md, Phase 4.5 summary, 15 strategy/decision docs, full code-reality survey.

> **Amendment (2026-06-10, D-022):** Phase 7 references to FastAPI below are
> superseded — the gateway is a Rust binary (axum + rusqlite) per D-022.
> Week-1 scope is otherwise unchanged; budget the extra gateway effort against
> the Week-3 slack.

---

## 1. Where the project actually is

**Planning state:** Milestone v1.0 (Operator Cockpit MVP), 6/10 phases verified complete (62%). D-001 through D-020 locked. Next per roadmap: Phase 7 (API Gateway).

**Code reality (verified, not from docs):**

| Component | State |
|---|---|
| `packages/atlas-core` | Real. 7 frozen Pydantic v2 models + MemoryProvenance, 33 tests |
| `services/agent-runtime` | Real. mission/run/audit/policy/subagent services + `atlas` CLI + Hermes audit plugin, 44 tests |
| `services/wiki-runtime` | Real. ingest/update/search/lint + provenance + CLI, 31 tests, 87.5% coverage |
| `infra/migrations` | Real. 0001_core.sql (7 tables, FTS5, WAL) + 0002_wiki_provenance.sql |
| `apps/api` | **Empty** |
| `apps/web` | **Empty** |
| `services/{integration,pulse,worker}` | **Empty** |
| Rust / Tauri / SvelteKit code | **None anywhere** |
| docker-compose, Twenty deployment, FreeLLMAPI vendoring | **None** (FreeLLMAPI is an external install in Temp/, exercised by 5 smoke/benchmark scripts) |
| `wiki/` content | ~800 bytes total; the compounding-knowledge differentiator is unexercised |
| Hermes | Pinned MIT clone in `_EXTERNAL_REPOS/` (cli.py is 701 KB). agent-runtime has **no Hermes dependency** — `atlas_audit` reimplements the Hermes plugin hook protocol against pinned internals |

**End-to-end architecture as designed:**

```
Operator
  │
  ├─ Native cockpit (Tauri+SvelteKit) ── Phase 8 ──────────── [nothing built]
  │        │ REST + SSE + Tauri IPC
  ├─ API Gateway (FastAPI) ───────────── Phase 7 ──────────── [nothing built]
  │        │
  ├─ ATLAS Runtime (Python) ─────────── Phases 4–6 ────────── [REAL, tested]
  │    ├ mission/run state machine, policy engine, subagent budgets
  │    ├ transactional audit event bus → SQLite
  │    ├ LLM Wiki + provenance + FTS5 (+ optional sqlite-vec)
  │    └ atlas_audit plugin ──→ Hermes foundation (evolved per D-018)
  │
  ├─ Sidecars (pinned upstream, never forked)
  │    ├ FreeLLMAPI — OpenAI-compatible loopback gateway      [smoke-tested only]
  │    └ Twenty CRM — Docker Compose, API/MCP/webhooks (AGPL) [decision only]
  │
  └─ Reference pillars (patterns only, no code): Terax (Tauri/PTY/keychain),
     Odysseus (threat model, IPC token, untrusted-context wrapper)
```

---

## 2. Strengths (genuine, keep doing)

1. **Decision discipline.** 20 ADRs with pinned SHAs, license verdicts (Hermes MIT, Terax Apache-2.0, Odysseus MIT, FreeLLMAPI MIT, Twenty AGPL), explicit rejected alternatives. Almost no project at this stage has this.
2. **Audit-first core actually built.** Transactional event bus, provenance schema, policy engine with workspace boundaries — the differentiator claims are backed by tested code, not slides.
3. **Sidecar-first integration doctrine.** D-015/D-020's "pin, don't fork" pattern is the single best protection against the failure mode this project is most exposed to (fork-maintenance treadmill).
4. **Real test gates.** 80%+ coverage enforced per phase, 108 tests green across packages. Verification documents per phase.
5. **Scope dams held so far.** No CRM, no voice, no overlay before the runtime loop — D-007/D-009 have actually been honored.
6. **Memory framework design** (6 governed layers, policy-routed, provenance-mandatory) is a defensible differentiator vs. every mainstream harness — and Layer 2/3/5 already exist in code.

## 3. Weaknesses

1. **Doc-to-code ratio is inverted and worsening.** Phase 4.5 produced 10 documents and zero code. There are now ~60 strategy docs against ~50 KB of service code. Planning velocity is outrunning shipping velocity; the docs are now generating contradictions faster than code resolves them.
2. **The riskiest integration is the least tested.** No end-to-end run exists where a real mission executes through real Hermes with a real model and produces an audit trail + wiki artifact. Everything green so far is unit/service-level. The product thesis lives or dies on that one path.
3. **Hermes coupling is brittle by construction.** `atlas_audit` reimplements Hermes's hook protocol against internals of a pinned SHA whose main file is 701 KB. Meanwhile D-018 declares "evolve the foundation in-process" — but no Hermes code has been evolved. Doctrine and implementation currently describe two different architectures.
4. **Cross-doc contradictions are accumulating** (found by systematic comparison):
   - D-020 puts a CRM panel in Phase 8; NATIVE_COCKPIT_STRATEGY.md explicitly bans CRM from Phase 8.
   - Two features compete for the "Phase 9" slot (skill memory vs. CRM/Pulse).
   - Memory framework docs disagree on 6 vs. 7 layers.
   - Twenty-as-relationship-substrate overlaps undelineated with planned Graph Memory Layer 4.
   - Reference pillar (Terax: React 19/Zustand) vs. locked stack (SvelteKit) — pattern reuse path unaddressed.
5. **Phase 8 as specified is a schedule bomb.** Rust/Tauri shell + SvelteKit UI + SSE + PTY + OS keychain + CSP/threat model + 6–7 surfaces, with Tauri never built on this machine and ConPTY unvalidated, is 6–10 weeks of work labeled as one phase.
6. **Empty directories encode future sprawl** (`pulse-runtime`, `integration-runtime`, `worker`, `atlas-sdk`, `atlas-ui`): five more services planned before one user-facing surface exists.
7. **No CI, no packaging, no one-command startup.** "90% stable" is unmeasurable without a harness that runs the loop repeatedly.

## 4. Things that WILL fail if continued as-is

1. **"Rebrand everything to L2" fails legally on Twenty.** Twenty is AGPL-3.0. A rebranded/modified Twenty offered over a network triggers source-disclosure obligations for your modifications, and Twenty's name/logo are trademarked. Your own D-020 already chose correctly: sidecar-only, no embedding. Rebranding Twenty would reverse your own locked decision. Hermes (MIT), Odysseus (MIT), FreeLLMAPI (MIT) can be rebranded freely with attribution; Terax (Apache-2.0) requires NOTICE preservation if code is copied.
2. **"Rebrand everything" fails operationally everywhere else.** Every rebranded fork = a permanent divergence you maintain alone, losing upstream fixes (FreeLLMAPI's free-route churn alone would consume you). The viable version of the vision: **rebrand the experience layer, pin the infrastructure layer.** L2 branding lives in the cockpit, CLI, docs, and the one fork you already committed to owning (Hermes → L2/ATLAS harness). Everything else stays an unbranded pinned sidecar behind an L2-branded adapter.
3. **30 days with current full scope fails arithmetically.** Phase 7 + native Phase 8 + Twenty wiring + browser harness + skill classification + stabilization is ~3–4 months of solo work. Something must be cut, and the only cut that doesn't damage the thesis is the **native shell** (Tauri), not the web cockpit.
4. **The Hermes plugin will break silently** the first time you actually start "evolving the foundation" (renaming, restructuring per D-018) — the plugin's hook assumptions are documented against fixed line numbers in the pinned clone. Without an integration test that boots real Hermes and asserts events flow, you won't know until a demo.
5. **Wiki compounding never materializes** if v1.0 ships with an empty wiki. A knowledge layer with no knowledge is a demo liability, not a differentiator.
6. **Browser harness is net-new unscoped scope.** It appears in no decision record. Adopting another OSS browser-agent project now would add a sixth integration track at the worst moment.

## 5. The 30-day plan — v1.0 "L2 ATLAS" at 90% stability

**Definition of 90% stable:** the closed loop (create mission → execute through the L2/Hermes runtime via routed model → audit trail → wiki artifact → visible in cockpit) succeeds ≥ 9 of 10 consecutive scripted runs, survives sidecar death mid-run, and starts with one command on a clean machine.

**Strategic reframe:** Ship the **web** cockpit in 30 days; the Tauri native shell becomes v1.1 (the SvelteKit app ports into the Tauri webview unchanged later — this is exactly why D-006 chose adapter-static). Sidecars get wired and supervised, not forked. Branding effort goes where it compounds: cockpit UI (the L2 design system already exists), CLI, docs, and the Hermes-derived harness identity.

### Week 1 (Days 1–7): Truth and plumbing
- **Day 1–2: Real end-to-end smoke test.** Boot actual Hermes from the pinned clone with the atlas_audit plugin, run a real mission through FreeLLMAPI (Kilo keyless route already validated), assert: Run row, ordered AuditEvents, wiki artifact. This is the highest-information artifact in the entire plan; everything else adjusts to what it reveals.
- **Day 2–5: Phase 7 API Gateway** exactly as already specified (FastAPI, 8 endpoints, OpenAPI from Pydantic) **plus one SSE endpoint** (`GET /runs/{id}/events/stream`) — Phase 8's realtime requirement depends on it and it's cheap now.
- **Day 5–6: CI + compose.** GitHub Actions running all three test suites + the e2e smoke (mock-provider mode). `infra/compose/docker-compose.yml`: FreeLLMAPI sidecar + (profile-gated) Twenty + its postgres image. One `atlas up` command.
- **Day 7: Resolve the doc contradictions in one sitting** (30-minute decisions, not new research): CRM panel out of Phase 8 → Phase 10; skill memory keeps Phase 9; memory layers = 6, canonical doc = AGENT_MEMORY_FRAMEWORK_STRATEGY.md; Twenty = relationship store of record, Graph Memory Layer 4 = derived index over it (v2.0).

### Week 2 (Days 8–14): The L2-branded cockpit (web)
- SvelteKit + adapter-static, L2 Systems design system (Topographic/Dark Prism), four surfaces only:
  1. Mission list + create
  2. Run detail with live audit stream (SSE)
  3. Wiki browser + FTS search
  4. Model/provider panel (read-only registry view + health)
- Deferred from the 6-surface list: PTY/terminal surface and keychain settings (both are native-shell concerns).
- This is where "rebrand to L2" is real and cheap: the operator never sees Hermes, FreeLLMAPI, or Twenty — they see L2 ATLAS.

### Week 3 (Days 15–21): Wire the sidecars properly
- **Model registry + router** (`atlas_core.model_registry`, `model_router` per D-017): startup discovery from FreeLLMAPI `/v1/models`, task-class routing table, health tracking, CONFIG fallback when sidecar is down. Supervised sidecar lifecycle (start/health/restart) inside `atlas up`.
- **Twenty, sidecar-only:** compose profile up; Metadata API provisioning script for `AgentInteraction`/`MissionContext` custom objects; `/webhooks/twenty` receiver (HMAC-verified, **idempotent by event ID** — their retry behavior is undocumented); one read-only agent tool (contact lookup via MCP/REST). No CRM UI this month.
- **Browser harness, smallest viable:** do NOT adopt a new OSS project. Wire Playwright as an ATLAS toolset for the runtime (policy-gated, audit-emitting, screenshots filed as wiki artifacts). This satisfies "works in any software" for web targets; native-app automation waits for the Tauri/PTY era.
- **Idempotency/antifragility pass:** idempotency keys on mission/run creation endpoints, webhook dedupe, crash-resume for in-flight runs (mark orphaned runs `failed` with preserved partial trails on startup — the state machine already supports this).

### Week 4 (Days 22–30): Stabilize, dogfood, brand, tag
- **Days 22–25: Chaos + soak.** Scripted: 10 consecutive e2e missions nightly; kill FreeLLMAPI mid-run (expect CONFIG fallback, not failure); kill Twenty (expect graceful CRM degradation per D-020); network-off run. Fix everything found. The 90% bar is measured here.
- **Days 26–27: Dogfood for real.** Run 5–10 genuine L2 missions through the cockpit; let the wiki accumulate actual pages — this seeds the compounding layer and produces the demo.
- **Days 28–29: Branding + packaging close-out.** Attribution file (Hermes MIT, FreeLLMAPI MIT notices), divergence log for the harness per D-018's own non-negotiable, README, quickstart, `atlas up` on a clean machine.
- **Day 30: Tag v1.0.** Write v1.1 roadmap: Tauri shell (port the same SvelteKit app), PTY surface, keychain, CRM panel, then Pulse.

### Explicitly deferred beyond 30 days
Tauri/Rust native shell · graph memory (Layer 4) · STT/TTS/overlay · pulse-runtime · CRM cockpit panel · FreeLLMAPI fork/vendor · full skill classification (ship a ~10-skill curated pack instead) · Odysseus multi-user patterns · native-app (non-web) automation.

### Risk table for the 30 days

| Risk | Impact | Mitigation |
|---|---|---|
| E2e smoke reveals plugin/Hermes breakage | High | Scheduled Day 1 precisely so the rest of the month absorbs it |
| Free-tier route instability (Kilo et al.) | Medium | Router CONFIG fallback is a Week-3 deliverable, tested by chaos day |
| SvelteKit greenfield slower than estimated | Medium | 4 surfaces, design system pre-exists, no native shell |
| Twenty compose friction (pg_graphql #8032) | Low | Official `twentycrm/twenty-postgres` image only; profile-gated so it can't block the loop |
| Solo-operator bandwidth | High | Anything not on the critical loop path is deferred; no new OSS adoptions this month |

---

## 6. Standing recommendations

1. **Institute a doc freeze:** no new architecture documents until Phase 7 + cockpit ship. New ideas go to DEEP_RESEARCH_BACKLOG.md as one-liners.
2. **Adopt the two-layer branding policy permanently:** L2 brand = experience layer + the Hermes-derived harness; infrastructure = pinned, attributed, unbranded sidecars. Update PROJECT.md non-negotiables with it.
3. **Make the e2e smoke the merge gate** from now on — unit coverage already proved it can't catch the risk that matters.
4. **Delete or `.gitkeep`-annotate the empty service/package dirs** with a one-line "reserved for vX.Y" note so the tree reflects reality.
