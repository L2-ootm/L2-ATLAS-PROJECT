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

## Operator-gated actions (performed only with explicit approval)

### Pre-flight (do before going public)
- [x] npm lifecycle launcher contract (2026-07-17): separated immutable install root
      from `ATLAS_HOME`, OS/CPU platform package, runtime forwarding, safe release
      entrypoint, launcher self-update, checksum verification, rollback, and module-
      preservation fixture. Package suite green; `npm pack --dry-run` clean.
- [x] Build and host the complete Windows x64 release bundle (2026-07-17): embedded
      Python 3.13.11, Rust gateway, compiled cockpit, Go TUI, runtime services, and
      bundled modules in `@systemsl2/atlas-win32-x64@0.1.0`.
- [x] Publish `@systemsl2/atlas@0.1.0` and its platform package publicly; anonymous
      registry install, materialization, 23 DB migrations, doctor, no-op update, module
      preservation, gateway execution, and cockpit HTTP 200 passed in isolation.
- [ ] Repeat cross-version update/rollback UAT when the next npm release exists.
- [x] Full-history secret scan and cleanup (2026-07-17): rewritten publishable history
      contains only `main`; local planning/scratch and private module history are excluded;
      personal absolute-path variants are absent; the reviewed Gitleaks policy reports
      0 findings across 488 commits. A recovery bundle remains private outside the repo.
- [x] Confirm npm authentication and ownership of `@systemsl2/atlas` and
      `@systemsl2/atlas-win32-x64`; both report public access and `latest: 0.1.0`.
- [x] `atlas doctor` — db/config/gateway ok, provider mock (2026-06-23). (Run again on a truly
      fresh clone before public; cockpit shows "down" only when its port differs from the probe.)
- [x] Full test suite green (2026-06-23): agent-runtime 369 pass / 1 skip / 1 known
      `claude_agent_sdk` env fail; golden + tool_service 19/19; cockpit `tsc`+`vite`+eslint green.
- [x] **Real-world E2E run (2026-06-23):** booted the release gateway (binary post-10.0.4, has
      `/v1/tools/*`) + React cockpit against the **live `~/.atlas/atlas.db`** (backed up first).
      Ran all 3 golden workflows via the real `atlas golden` CLI; Self-Review correctly stayed
      **PENDING** and only wrote after `atlas tools approve` (file landed, `ok:true`). Cockpit
      **Ledger** rendered the live golden audit trail (57 events), **Integrations** showed
      "5 tools registered · 2 write/shell gated · gateway ONLINE", zero console errors. Scoped
      `atlas golden reset --confirm` removed only golden rows; real data (10 missions/runs)
      intact. Screenshots: `output/playwright/live2-{audit,wiki,models,integrations,system}.png`.
      **Finding:** a bare gateway-binary launch 500s on dispatch endpoints unless `ATLAS_CLI`
      is set — `atlas up`/`gateway_control` inject it; document for fresh-machine operators.
- [ ] **Live demo capture for launch:** run `DEMO_SCRIPT.md` end-to-end and record a short
      video / final screenshots for the launch assets; host them; fill `<DEMO_URL>`. (The
      `live2-*.png` set already proves the surfaces render real data.)
- [ ] Confirm Docker Compose path (still untested — no container engine on the dev machine).
- [ ] Confirm 10.0.4 GitHub adapter vs a real repo (System POLICY panel render ✅ verified live).

### Private beta (SC3) — before the public flip
- [ ] Run a private beta with 20–50 targeted developer contacts (use the reviewer-outreach
      message in `LAUNCH_MESSAGE.md`).
- [ ] Log feedback (themes, bugs, asks) into the ship report's adoption section.

### Public flip (SC2)
- [x] Make the repo public (2026-07-17; verified through GitHub CLI).
- [x] Publish the repository-linked `@l2-ootm/atlas@0.1.0` GitHub Package
      (2026-07-17; public page and repository linkage verified anonymously).
- [x] Tag and publish `v0.1.0` as **ATLAS v0.1.0 — Open Research Preview**
      (2026-07-17), with exact npm registry tarballs and SHA-256 checksums.
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
