# ATLAS v0.1 Release Checklist — Operator Handoff

Phase 10.0.6 was run **drafts-only**. The build prepared all written artifacts; the actions
below are **operator-gated** — outward-facing, hard-to-reverse, or requiring credentials —
and were deliberately NOT performed autonomously. Work top to bottom.

## ✅ Prepared by the build (review these)

- [x] README final pass — "ATLAS v0.1 — Open Research Preview" label + accurate v0.1 scope + no overclaiming
- [x] Technical report — `docs/release/TECHNICAL_REPORT.md`
- [x] Public roadmap — `docs/release/PUBLIC_ROADMAP.md`
- [x] Demo script — `docs/release/DEMO_SCRIPT.md`
- [x] Launch message draft (+ reviewer outreach) — `docs/release/LAUNCH_MESSAGE.md`
- [x] Ship report draft (build metrics real; adoption metrics = placeholders) — `docs/release/ATLAS_30_DAY_SHIP_REPORT.md`
- [x] Known-failures list — `docs/known-failures.md`
- [x] Trust docs (Phase 10.0.1): LICENSE, SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, LIMITATIONS.md, ARCHITECTURE.md, ATTRIBUTION.md, issue templates

## ⛔ Operator-gated actions (NOT done autonomously)

### Pre-flight (do before going public)
- [ ] Re-run the secret scan over tracked history; confirm no `.env`/keys/tokens/db committed.
- [ ] `atlas doctor` clean on a fresh clone (clone → setup → `atlas up` → doctor).
- [ ] Full test suite green (agent-runtime + atlas-core + Rust + cockpit build); note the known
      optional `claude-agent-sdk` env skip.
- [ ] Run `DEMO_SCRIPT.md` live; **capture screenshots/short video** (closes the SC3 screenshot
      item that was deferred from automation) and host them; fill `<DEMO_URL>`.
- [ ] Confirm Docker Compose path (still untested — no container engine on the dev machine).
- [ ] Confirm 10.0.4 human-verify items (System POLICY panel renders; GitHub adapter vs a real repo).

### Private beta (SC3) — before the public flip
- [ ] Run a private beta with 20–50 targeted developer contacts (use the reviewer-outreach
      message in `LAUNCH_MESSAGE.md`).
- [ ] Log feedback (themes, bugs, asks) into the ship report's adoption section.

### Public flip (SC2)
- [ ] Make the repo public.
- [ ] Tag `v0.1.0-open-research-preview`.
- [ ] Open GitHub Discussions + seed roadmap issues from `PUBLIC_ROADMAP.md`.
- [ ] Fill `<REPO_URL>` / `<DEMO_URL>` / `<REPORT_URL>` in `LAUNCH_MESSAGE.md`.

### Launch wave (SC4)
- [ ] Send the launch message across the channels list in `LAUNCH_MESSAGE.md` (operator selects).
- [ ] Recognition submissions (Algoverse, hackathon w/ Brazil eligibility, Devpost page, 5
      mentor/reviewer emails, UFU professor) — see wedge plan Days 28–29.
- [ ] Finalize `ATLAS_30_DAY_SHIP_REPORT.md` adoption metrics after first reactions land.

## Why these are gated

Publishing a repo, tagging a release, opening discussions, contacting real people, and sending
launch messages are outward-facing and effectively irreversible once seen. Per the operator's
explicit decision for Phase 10.0.6, the build prepares the artifacts and stops at the gate.
