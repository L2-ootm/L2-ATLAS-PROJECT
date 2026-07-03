# ULTRAREVIEW — provider mesh / TUI / web settings (2026-07-02)

Scope: pre-merge forensic pass over this branch's session slices.

## Surfaces traced

1. **Reasoning-effort chain** — `provider.reasoning_effort` (control_plane
   schema) → `config_service.resolve_provider` → `native.py` execute
   (`_resolve_reasoning_effort`, native.py:280) → `_default_factory`
   `reasoning_config={"effort": ...}` (native.py:99-101) → foundation
   `AIAgent`. Empty string omits the kwarg (provider default). VERIFIED:
   unit tests + live PATCH round-trip (revision 1→6, 409 on stale, status
   endpoint reflects effort, reverted).
2. **Function routing** — `function_router.resolve_bindings` /
   `apply_autoconfig`; gateway `functions.*` PATCH keys verified live.
3. **TUI** — starfield/composeRow exclusion, mode wrapper leak-prevention,
   workflow dispatch: covered by 93 Go tests; no findings.
4. **Web settings** — save flow (secret via POST /v1/auth/providers, rest via
   one optimistic PATCH), 409 reload, freellmapi base-URL guard, offline
   banner: 6 vitest cases + Playwright live drive (saved effort=high on the
   real gateway, banner + revision advance observed, reverted).

## Finding 1 (fixed): unstamped-but-matching aux slots stranded

**Failure point:** `function_router.apply_autoconfig` ownership guard
(previously `if existing and not _atlas_owned(existing): skip`).

**Chain:** operator's real `%LOCALAPPDATA%\hermes\config.yaml` had
`auxiliary.curator` / `auxiliary.compression` already set to
`openai-codex/gpt-5.4-mini` but without `managed_by: atlas`. The guard
classified them operator-owned → autoconfig would never retarget them after
a provider switch, silently defeating "auxiliary follows the mesh".

**Fix:** adopt a slot whose provider+model exactly equal the desired binding
(merge adds the stamp; adjacent keys like `timeout` survive). Any slot with
a *different* target remains operator-owned and untouched (D-001).
Covered by `test_apply_adopts_unstamped_slot_matching_desired_binding`;
verified live (curator/compression now `updated`, second run `current`).

## Finding 2 (verified non-issue): /v1/config vs /v1/provider/status disagree

`/v1/config` shows `provider.name=openrouter` while status shows
`openai-codex/gpt-5.5`. Traced: `auth_mode=oauth_import` makes
`resolve_provider` delegate to the codex identity regardless of the raw
`provider.name`. Raw config is the editable intent; status is the resolved
truth. The settings UI shows both panels, so no action.

## Residual risk

- `_LIGHT_MODEL_BY_PROVIDER` is a curated table; unknown api_key providers
  intentionally get no binding (foundation "auto" chain remains in charge).
- Adoption rule could claim a slot an operator hand-set to the exact same
  value; consequence is only that a later provider switch retargets it —
  judged acceptable and documented here.
