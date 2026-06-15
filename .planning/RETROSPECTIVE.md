# Retrospective — L2 ATLAS

## Milestone: v1.0 — Operator Cockpit MVP

**Shipped:** 2026-06-15
**Phases:** 10 (1–9.5, incl. decimals 4.5 / 8.5 / 9.5) | **Plans:** 32 | **Requirements:** 34/34

### What Was Built
The first closed operator loop: create mission → run through the ATLAS runtime (built on
a vendored, audited Hermes foundation) → emit a structured audit trail → file artifacts
to the LLM Wiki → monitor live in a SvelteKit web cockpit over a Rust loopback gateway.
Plus a classified skill inventory (~266 skills) and a public-release hardening gate.

### What Worked
- **Foundation-first sequencing.** Auditing Hermes extension surfaces (Phase 1) before
  building meant the audit bus attached via plugin/hook with no in-core edits to
  `cli.py`/`run_agent.py` — the integration contract held all the way to v1.0.
- **Pydantic v2 as the single data contract.** Column-name-1:1 DDL and emitted JSON
  Schema kept Python, SQLite, and the Rust gateway from drifting.
- **Audit-first as a discipline, not a feature.** Because every transition emits an
  AuditEvent in the same locked critical section, the idempotency/antifragility review
  found the state machine already TOCTOU-safe.
- **Decimal micro-phases (4.5 / 8.5 / 9.5)** absorbed spikes, cleanup, and the hardening
  gate without polluting the main build track.

### What Was Inefficient
- **A stale prebuilt gateway binary** (06-11, pre-CORS) was trusted by the runbook; the
  cockpit showed "GATEWAY OFFLINE" until rebuilt. Automated tests run against source, so
  they never caught that the on-disk artifact was stale (UAT F3).
- **The remote-fonts regression (F1)** shipped through every automated gate because no
  test loaded the real browser network. Only the manual UAT caught a non-negotiable
  (loopback-only) violation.
- **Requirements traceability drifted** — 7 delivered REQ-IDs still read "Pending" at
  close and had to be reconciled. `/gsd-progress` updates didn't keep the table current.

### Patterns Established
- Vendored-foundation hygiene: `ATTRIBUTION.md` + `DIVERGENCE_LOG.md` + `quarantined-skills/`
  (non-load-path) for anything unsafe in the upstream default tree.
- Loopback-only as an enforced contract: self-host fonts/assets; the cockpit talks only
  to `127.0.0.1:8484`.
- Assisted manual UAT: drive the live cockpit via Playwright, assert at the API layer,
  capture screenshots, record results + findings in a phase `*-UAT-RESULTS.md`.

### Key Lessons
- **Manual UAT earns its keep.** The user's insistence on UAT-before-archive caught two
  real issues (F1 remote fonts, F3 stale binary) that 157 automated tests missed. Keep a
  browser-in-the-loop gate before any "done."
- **Rebuild, don't trust artifacts.** Runbooks should say "build from source," not "use
  the existing binary."
- **Reconcile the traceability table at every phase close,** not at milestone close.

### Cost Observations
- Model mix: predominantly Opus (single operator session, judgment-heavy archive + UAT).
- Sessions: v1.0 spanned ~2 weeks of phase work; this close + UAT was one session.
- Notable: the expensive parts were environment plumbing (wrong venv on PATH, no `atlas`
  console script, stale binary), not the product work.

---

## Cross-Milestone Trends

_First milestone — trends accrue from v1.1 onward._

| Milestone | Phases | Plans | Reqs | Shipped | Headline finding |
|---|---|---|---|---|---|
| v1.0 Operator Cockpit MVP | 10 | 32 | 34/34 | 2026-06-15 | Manual UAT caught a loopback-only violation automated tests missed |
