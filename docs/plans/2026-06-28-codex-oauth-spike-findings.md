# P2 Spike Findings — Codex ChatGPT OAuth Import

**Date:** 2026-06-28 · **Scope:** validate whether ATLAS can run agents on the operator's
existing Codex (ChatGPT Plus) OAuth login. Read-only on `~/.codex/auth.json`, single probe.

## What was verified

- `~/.codex/auth.json` = `{auth_mode:"chatgpt", OPENAI_API_KEY:null, tokens:{id_token,
  access_token, refresh_token, account_id}, last_refresh}`. Plan: `plus`.
- Backend contract **holds**: `POST https://chatgpt.com/backend-api/codex/responses` with
  `Authorization: Bearer <access_token>` + `chatgpt-account-id: <account_id>` +
  `OpenAI-Beta: responses=experimental` returned a **structured** `401`
  (`code:"token_invalidated"`), not a 404/shape error. The endpoint, headers, and Responses-API
  body shape are accepted. Request model probed: `gpt-5`.
- The stored `access_token` is **not expired** (173h of lifetime left) but is **invalidated
  server-side** — Codex had rotated it since auth.json was last written. Scopes include
  `offline_access` (refresh is supported).

## The blocker: refresh-token rotation entanglement

A working session **requires a token refresh** (`grant_type=refresh_token` against
`https://auth.openai.com/oauth/token`, `client_id=app_EMoamEEZ73f0CkXaXp7hrann`). OAuth refresh
**rotates the refresh token**. Therefore:

- If ATLAS refreshes and does **not** write the new refresh token back to `~/.codex/auth.json`,
  the **Codex CLI breaks** on its next refresh (stale token).
- If ATLAS **does** write back, it is **mutating the operator's Codex install** — outside the
  "read-only, never write to ~/.codex" guarantee.

The spike **did not perform a refresh** (it would rotate the live Codex token). Verdict:
**Codex OAuth import is technically viable; the open decision is the refresh-ownership model.**

## Design options (operator decision)

1. **Read-through, no-refresh (strictly read-only).** ATLAS uses the on-disk `access_token`
   only when currently valid; if invalidated/expired it **fails closed** with remediation
   ("run `codex` to refresh, then retry"). Codex CLI remains the sole owner of token lifecycle.
   *Safest; never touches ~/.codex; brittle because Codex's on-disk token is often stale.*

2. **Managed refresh with write-back (opt-in).** ATLAS refreshes via the refresh token and
   **writes the rotated tokens back to `~/.codex/auth.json`** (atomic, preserving Codex's
   format), keeping both tools working. Explicit operator consent + audited. *Most usable;
   ATLAS co-owns the Codex token file — must match Codex's write semantics exactly.*

3. **ATLAS-owned copy (fork the login).** Copy the refresh token into ATLAS's own auth store and
   refresh independently. *Decouples from Codex but two stores diverge → double-rotation
   invalidation; not recommended.*

4. **Drop Codex-OAuth; api-key-only for OpenAI.** Skip the ChatGPT-subscription path entirely.
   *The documented fallback if the operator does not want token entanglement.*

**Recommendation:** Option 1 as the default (zero risk to Codex), with Option 2 available as an
explicit, audited opt-in for operators who accept ATLAS co-managing the Codex token file.
