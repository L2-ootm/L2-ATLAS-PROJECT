# RISKS — L2 ATLAS

## v1.1 risks (2026-07-10)

1. **Donor provenance compliance** — atlas-terminal vendors MiMoCode/opencode MIT
   presentation code. Residual donor identity or missing notices is a license/brand
   exposure. Mitigation: `scripts/scan-atlas-terminal-boundary.ps1` forbidden-terms
   scanner in every verification pass; attribution retained in
   `docs/third-party/ATLAS_TUI_UPSTREAM_NOTICE.md`.
2. **Surface protocol instability** — three surfaces (cockpit, Go TUI, atlas-terminal)
   consume the same gateway contracts; a route shape change breaks surfaces silently
   (see the 2026-07-04 `provider.list` `{providers}` vs `{all, connected}` split).
   Mitigation: Phase 10.8 shared conformance suite.
3. **Tri-runtime complexity** — Go (TUI) + Python (runtime) + Rust (gateway) + Bun/TS
   (atlas-terminal) means four toolchains, four test suites, and staleness hazards
   (prebuilt gateway binary drifting behind sources). Mitigation: `atlas doctor`
   staleness checks; single `atlas up`/`atlas down` topology.
4. **Permission broker correctness** — surface-scoped permission queues gate agent
   side effects; a broker bug either blocks all runs or silently approves them.
   Mitigation: PERM requirements covered by tests; adversarial cases in Phase 10.8.
5. **TUI retirement gate** — switching default `atlas` from Go TUI to atlas-terminal
   before the session-creation defect is root-caused would ship a broken default.
   Mitigation: retirement is an explicit operator decision gated on Phase 10.8 UAT.
6. **Windows compatibility** — primary operator machine is Windows; system `tar`
   breaks on `C:\` paths (atlas-cli release path), and TTY behavior differs from
   POSIX. Mitigation: run full test matrices on Windows, not just CI Linux.
7. **Session creation reliability** — the interactive atlas-terminal "Creating a
   session failed" toast reproduces against the live gateway but not in isolation;
   until root-caused it undermines trust in the primary interactive flow.
   Mitigation: diagnostic instrumentation landed (`ATLAS_SESSION_CREATE_ERROR`);
   blocking the retirement gate until fixed.

## P0 risks (v1.0, historical)

1. Scope explosion: CRM + WhatsApp + dashboard + wiki + self-improvement all at once.
2. Forking Hermes too early.
3. Copying old code without license/security review.
4. Building UI before runtime loop works.
5. Mixing personal/private KB material into product repo.

## Mitigation

- Ship Operator Cockpit MVP first.
- Classify all source repos before importing.
- Preserve old repos; extract modules deliberately.
- Keep Personal Data KB separate.
