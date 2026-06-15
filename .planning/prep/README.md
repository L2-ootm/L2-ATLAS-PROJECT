# v1.1 Preparation Index

Preparation documents created after v1.0 archive and Davi's CLI/TUI/auth critique.

## Why this exists

The v1.0 archive is valid as **Operator Cockpit MVP**, but the post-archive inspection showed a larger next-milestone gap than initially documented:

- ATLAS does not yet have a real Hermes-class TUI.
- ATLAS does not yet have its own auth store/flows.
- ATLAS should not depend on or mutate Codex auth files.
- ATLAS does not yet have real provider/model/runtime discovery.
- ATLAS does not yet expose a complete agentic chat harness.
- A native shell alone would hide the missing runtime instead of solving it.

Therefore v1.1 preparation now targets:

> **v1.1 — ATLAS Agent Harness & Native Operator Shell**

## Documents

| File | Purpose |
|---|---|
| `.planning/reports/v1-cli-agentic-gap-2026-06-15.md` | Original post-v1.0 CLI gap report. |
| `.planning/prep/v1.1-extra-marathon-scope.md` | Expanded scope: real ATLAS harness, TUI, owned auth, models, native shell. |
| `.planning/prep/v1.1-tui-agent-ux-spec.md` | TUI/agent UX spec based on Hermes TUI architecture. |
| `.planning/prep/v1.1-owned-auth-architecture.md` | ATLAS-owned auth architecture; Codex-inspired but no Codex mutation. |
| `.planning/prep/v1.1-provider-model-registry-spec.md` | Provider/model/runtime/route registry specification seed. |
| `.planning/prep/v1.1-agentic-cli-prep.md` | Earlier full preparation brief; still useful, now superseded/expanded by extra-marathon docs. |
| `.planning/prep/v1.1-requirements-seed.md` | Requirement seed for `/gsd-new-milestone`; must be expanded with TUI/AUTH/PROVIDERS/MODELS/AGENT/NATIVE categories. |
| `.planning/prep/phase-10-seed-plan.md` | Candidate Phase 10 execution split. |
| `.planning/prep/v1.1-exhaustive-backlog.md` | Exhaustive candidate backlog for pruning during milestone planning. |
| `.planning/prep/v1.1-planning-exhaustion-checklist.md` | Checklist showing major planning axes covered and remaining unknowns. |

## Recommended next command

When ready to formally start the next milestone:

```txt
/gsd-new-milestone v1.1 — ATLAS Agent Harness & Native Operator Shell
```

Use the prep docs above as input. Do not let the workflow scope v1.1 as only "Native Cockpit Shell" unless Davi explicitly overrides the TUI/auth/harness gap.

## Short milestone thesis

> v1.1 makes ATLAS credible as a local AI operator harness: Hermes-class ATLAS TUI, ATLAS-owned authentication, Codex read-only detection without mutation, real provider/model discovery, agentic chat, and then Tauri/native shell + PTY around the cockpit and harness.

## Hard acceptance gates

1. `atlas` or `atlas tui` opens an ATLAS-branded TUI.
2. `atlas chat -q "ping"` works or gives precise auth remediation.
3. `atlas auth status` uses ATLAS-owned auth state and detects Codex read-only without mutating `~/.codex`.
4. `atlas models list --all` shows source/status/auth/runtime metadata, not only seeded rows.
5. Provider/model status appears consistently in CLI/TUI/cockpit/native shell.
6. Native shell hosts cockpit + PTY/terminal pane.
7. No secrets leak in CLI output, logs, cockpit, screenshots, JSON exports, or docs.
8. Manual UAT covers terminal TUI, one-shot chat, auth, model discovery, cockpit, and native shell.

## Remaining unknowns to resolve during `/gsd-new-milestone`

1. Whether OpenAI/Codex OAuth endpoints may be used directly by ATLAS or only detected externally.
2. Whether `atlas` should default to TUI in v1.1.
3. Whether to fork Hermes TUI into ATLAS namespace or skin/extend vendored Hermes TUI first.
4. Which first real provider should be the canonical v1.1 live-response lane.
5. Whether v1.1 requires OS keychain integration or file-store is acceptable for the first ATLAS-owned auth implementation.
