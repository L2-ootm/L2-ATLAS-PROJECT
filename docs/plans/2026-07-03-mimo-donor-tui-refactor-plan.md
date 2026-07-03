# MiMo-Code Donor TUI Refactor — Architecture & Staged Plan

**Captured:** 2026-07-03
**Direction (operator):** copy MiMo-Code's MIT TUI entirely and start from there — the same
move MiMo-Code made on opencode — while reusing ATLAS logic. Mouse support, dialog system,
model selector, and transcript ergonomics come with the donor.

## Donor facts (verified against the pinned clone)

- Source: `_EXTERNAL_REPOS/mimo-code` — partial clone of
  `github.com/XiaomiMiMo/MiMo-Code` @ `86d95a79` (v0.1.2, MIT). Sparse checkout widened
  2026-07-03 to include the full `packages/opencode`, `packages/sdk`, `packages/plugin`,
  `packages/ui`, and `script/`.
- The TUI lives at `packages/opencode/src/cli/cmd/tui/` — ~180 files / ~28k LOC of
  SolidJS + OpenTUI (`@opentui/core` + `@opentui/solid` 0.1.101), Bun-only.
- Mouse support is OpenTUI-native (67 onMouseUp handlers, right-click copy, selection).
- The TUI's ONLY backend boundary is `context/sdk.tsx`:
  `createOpencodeClient({ baseUrl, fetch, ... })` from `@mimo-ai/sdk/v2`, plus SSE via
  `sdk.global.event(...)`. `thread.ts` already injects a custom `fetch`
  (`createWorkerFetch()`) — the client transport is designed to be swapped.

## Architecture decision — the fetch-adapter seam

Do NOT rewrite the donor UI's data layer (sdk.tsx / sync.tsx / event.ts). Instead:

1. Vendor the donor TUI tree verbatim (identity-scrub pass after copy).
2. Vendor the generated `@mimo-ai/sdk/v2` **types + client** (MIT, mechanical).
3. Implement `createAtlasFetch()` — an in-process request router that speaks the donor's
   HTTP+SSE surface on the front and calls the ATLAS Rust gateway on the back:
   - `session.create/list/messages/prompt` → `/v1/surface-sessions`, `/v1/missions`,
     `/v1/missions/{id}/run`, `/v1/runs/{id}/stream`
   - `permission.reply` → `/v1/tools/approvals` + owner-token claim
   - `provider.list / config.get` → `/v1/provider/*`, `/v1/config`, `/v1/models`
   - `global.event` SSE → bridge of ATLAS SurfaceEvents → donor event names
     (`message.part.updated`, `session.status`, `permission.asked`, ...)
4. MiMo's server/storage/provider/pty/share/auth code is never copied into ATLAS-shipped
   packages. ATLAS keeps runtime, provider mesh, config, audit, policy, session, and
   storage authority (same one-agent/many-surfaces law as v1.1).

This is exactly how the donor runs against a remote server (`attach.ts`) — we present
ATLAS as that "server" without running a second backend.

## Package layout

`services/atlas-terminal/` (Bun workspace, new):

- `src/adapter/` — `createAtlasFetch()` + SSE bridge + endpoint translators (STAGE 1,
  testable headless with a stubbed gateway).
- `src/sdk/` — vendored donor SDK v2 client/types (notice retained).
- `src/tui/` — vendored donor TUI tree (STAGE 2+; scrubbed identity).
- `src/main.tsx` — ATLAS entry: renderer boot, adapter injection, theme.
- The existing Go TUI (`services/atlas-tui`) STAYS the default `atlas` surface until the
  Phase-10.8-style parity/retirement gate passes for atlas-terminal.

## Stages

- **STAGE 0 (this session):** plan committed; donor source fully materialized; Bun package
  scaffold; adapter core (config/provider/models + session create + SSE bridge skeleton)
  with bun tests; minimal OpenTUI boot proving Solid+OpenTUI render under Windows Terminal.
- **STAGE 1:** full adapter surface for the donor chat loop (session prompt → mission/run →
  SSE parts; permission.asked/reply round trip; question dialogs mapped to approvals).
- **STAGE 2:** wholesale TUI tree copy + identity scrub (MIMOCODE_* env vars → ATLAS_*,
  `mimo` command → `atlas`, donor branding → ATLAS canon, keep MIT notices). Boundary
  scanner extended to atlas-terminal.
- **STAGE 3:** feature parity audit against the Go TUI (starfield, modes, workflows,
  /freellmapi, settings overlay) + operator UAT; then default-surface decision + Go TUI
  retirement gate (tested rollback, dated decision — mirrors 10.8 SC5).

## Non-goals / guardrails

- No MiMo server/runtime/storage as a second product backend.
- No donor identity in shipped code outside notices (existing 10.1 scanner law).
- Go TUI keeps shipping until parity is proven; no default flip in STAGE 0-2.

## Verification per stage

- STAGE 0: `bun install` clean; `bun test` green for adapter; `bunx tsc --noEmit` green;
  boot smoke (`bun run src/main.tsx --smoke`) exits 0 rendering one frame.
- STAGE 1+: adapter contract tests against a live gateway (env-gated, like
  `ATLAS_TUI_LIVE_GATEWAY`); SSE bridge replay fixtures shared with the Go TUI conformance
  fixtures.
