# Sprint Prompt — atlas-terminal TUI: STAGE 3 Interactive UAT & Wiring Hardening

**Date:** 2026-07-04
**Operator focus:** Make the TUI work fine, connect to the gateway easily, run tasks, dynamically import auth (Codex OAuth from the local machine, just like Hermes does it).
**Deadline:** part of the 2026-07-09 milestone finish sprint.

---

## Context you must read before starting

1. `docs/plans/2026-07-03-mimo-donor-tui-refactor-plan.md` — the staged refactor plan. STAGE 0–2 are DONE. You are executing STAGE 3.
2. `.planning/STATE.md` (top section) — current position: STAGE 2 complete, STAGE 3 is next.
3. `services/atlas-terminal/src/adapter/atlasFetch.ts` — the fetch-adapter seam (376 lines). This is the single backend boundary.
4. `services/atlas-terminal/src/adapter/chat.ts` — ChatAdapter (423 lines). Maps donor sessions → ATLAS mission/run.
5. `services/atlas-terminal/src/adapter/gateway.ts` — typed GatewayClient (177 lines).
6. `services/atlas-terminal/src/main.tsx` — TUI entry point (49 lines).
7. `services/atlas-terminal/src/tui/app.tsx` — full SolidJS TUI app (1152 lines).
8. `services/atlas-tui/internal/tui/` — Go TUI source (the feature parity benchmark).
9. `docs/plans/2026-07-03-finish-mission-analysis-and-execution-order.md` — WS-A workstream inventory.

---

## GOAL 1: Fix the bash-interactive endpoint gap

The TUI's interactive bash handler (`app.tsx:1071-1094`) calls `POST /bash-interactive/{id}/reply` but the adapter has no route for it — it will 501 at runtime.

**Acceptance:**
- Add a `/bash-interactive/{id}/reply` route to `atlasFetch.ts` that accepts `{ output, exitCode }` and either:
  - Forwards to the ATLAS gateway if such an endpoint exists, or
  - Returns a valid stub response so the TUI doesn't hang.
- The TUI must not hang forever when an interactive bash tool is invoked.
- Write a bun test that verifies the route returns 200 with a valid body.

---

## GOAL 2: Wire Codex OAuth auto-detection into the TUI

The gateway already supports `POST /v1/auth/codex/import` (reads `~/.codex` and imports the session). The adapter already routes `POST /atlas/auth/codex/import` → gateway. But the TUI never triggers this automatically.

Hermes reads `~/.codex` on startup and imports the session. The TUI should do the same.

**Acceptance:**
- On TUI boot (in `main.tsx` or the adapter init), probe `GET /atlas/provider/status`.
- If the response shows `auth_mode` is not `oauth_import` and `~/.codex` exists on the local machine, automatically call `POST /atlas/auth/codex/import`.
- Surface a toast/notification in the TUI: "Codex OAuth imported from ~/.codex" or "Codex auth not found — configure a provider".
- If import fails, surface the error but don't block boot.
- Write a bun test that mocks the provider status response and verifies the import is triggered when `~/.codex` exists.

---

## GOAL 3: Interactive UAT — prove the TUI works in Windows Terminal

The TUI has never been operator-tested interactively. STAGE 3 requires this.

**Acceptance:**
- Run `cd services/atlas-terminal && bun run dev` in Windows Terminal.
- Verify: the TUI boots, renders the home screen with starry background and logo, the prompt is functional.
- Type a message, verify it creates a session, starts a mission/run, streams SSE parts, and renders the transcript.
- Verify: `/settings` dialog opens, shows provider status, allows model selection.
- Verify: `/freellmapi-status`, `/freellmapi-start`, `/freellmapi-stop` slash commands work.
- Verify: permission approval dialog appears when a tool requires approval, approve/reject works.
- Verify: Ctrl-C cancels gracefully, `/new` resets the session.
- Document any failures in `.planning/reports/atlas-terminal-stage3-uat-YYYY-MM-DD.md`.

---

## GOAL 4: Feature parity audit vs Go TUI

Compare the atlas-terminal TUI against the Go TUI (`services/atlas-tui/`) feature by feature.

**Acceptance:**
- Create a feature matrix table covering:
  - Starfield/idle animation
  - Agent modes (Build/Plan/Compose) cycling
  - Slash commands (/dream, /distill, /deep-research, /review, /freellmapi-*)
  - Settings overlay (provider/model/auth/base-URL/reasoning-effort)
  - Permission approval UX (4-option: once/session/always/deny)
  - Transcript rendering (markdown-lite, code blocks, tool cards)
  - Session management (new, list, resume, /new reset)
  - Keyboard shortcuts and focus model
  - ASCII/Unicode safety and Windows Terminal compatibility
- For each feature: EXISTS (in atlas-terminal), MISSING, PARTIAL, or EXCEEDS.
- Save the matrix to `docs/reports/atlas-terminal-parity-audit.md`.
- For each MISSING or PARTIAL feature, create a focused fix task.

---

## GOAL 5: Harden the adapter for robustness

The adapter is functional but brittle in several areas.

**Acceptance:**
- **Reconnection:** If the SSE stream to `/v1/runs/{id}/stream` drops, the adapter should attempt one reconnect (resume from last event ID if the gateway supports it, otherwise restart the stream).
- **Timeout:** If a mission/run doesn't produce any events within 60 seconds, surface a timeout error to the TUI (don't let it hang silently).
- **Provider offline:** If the gateway returns a provider-status indicating no live provider, the TUI should show a clear "no provider configured — use /settings to set one" message instead of silently failing on the first prompt.
- **Error surfacing:** Every adapter error should produce a user-visible toast or transcript error, never a silent swallow.
- Write bun tests for: reconnect attempt, timeout detection, offline provider message.

---

## GOAL 6: Boundary scanner extension

The identity scrub in STAGE 2 is complete but the boundary scanner (`scripts/tui-boundary-check.ps1`) hasn't been extended to cover `services/atlas-terminal/`.

**Acceptance:**
- Extend the boundary scanner to scan `services/atlas-terminal/src/` for:
  - Donor product names (mimo, mimocode, opencode, mimo-ai, MiMo)
  - Donor env vars (MIMOCODE_*)
  - Donor URLs, endpoints, analytics, telemetry
- The scanner must pass clean on the current codebase.
- Add the scanner to CI or a pre-commit check if feasible.

---

## GOAL 7: Update STATE.md and documentation

After completing GOALs 1–6, update the project state.

**Acceptance:**
- Update `.planning/STATE.md` top section to reflect STAGE 3 progress.
- If the parity audit reveals no blocking gaps, document the Go TUI retirement gate decision (keep both, or begin deprecation).
- Update `docs/plans/2026-07-03-mimo-donor-tui-refactor-plan.md` STAGE 3 status.

---

## Execution order

1. GOAL 1 (bash-interactive) — quick fix, unblocks interactive bash tools
2. GOAL 2 (Codex OAuth auto-detect) — core operator requirement
3. GOAL 5 (robustness) — reconnection, timeout, provider-offline, error surfacing
4. GOAL 3 (interactive UAT) — prove it works end-to-end
5. GOAL 4 (parity audit) — know exactly what's missing
6. GOAL 6 (boundary scanner) — identity compliance
7. GOAL 7 (docs) — close the loop

## Verification gates

After each GOAL:
- `cd services/atlas-terminal && bun test` — all tests pass
- `cd services/atlas-terminal && bunx tsc --noEmit` — typecheck clean
- After GOAL 3: live UAT evidence (screenshots or transcript log)
- After GOAL 4: parity matrix saved
- After GOAL 6: boundary scanner passes clean
- After GOAL 7: STATE.md updated

## Non-goals (this sprint)

- Go TUI retirement (decision documented, not executed)
- New TUI features beyond parity (modes, workflows, starfield — port from Go TUI only if MISSING per parity audit)
- Donor backend/runtime import (D-001 / 10.1 rejection boundary)
- Package/installer work (WS-B, separate workstream)
