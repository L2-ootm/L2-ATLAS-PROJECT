# Plan 01-01 Summary — Clone Hermes at Pinned SHA

**Phase:** 01 — Hermes Foundation Clone & Extension Audit
**Plan:** 01-01 (Wave 1)
**Status:** Complete
**Commit:** 380ee6f
**REQ-ID:** FOUND-01

## Deliverables

| File | Action |
|------|--------|
| `.gitignore` | Updated — `_EXTERNAL_REPOS/` rule added before clone |
| `_EXTERNAL_REPOS/hermes-agent/` | Fresh clone from upstream at SHA `e8b9369a9d2df36139a5055cae3ed3c15691e03e` (gitignored) |
| `docs/foundation/CLONE_VERIFICATION.md` | Created — SHA verification + secret-scan CLEAN result recorded |

## Verification

- `git -C _EXTERNAL_REPOS/hermes-agent rev-parse HEAD` = `e8b9369a9d2df36139a5055cae3ed3c15691e03e` ✅
- `.gitignore` contains `_EXTERNAL_REPOS/` ✅
- No `_EXTERNAL_REPOS/` files tracked in ATLAS repo ✅
- Secret-scan gate: CLEAN — no `.env`, `auth.json`, `*.db`, `sessions/`, or token patterns tracked ✅
- `docs/foundation/CLONE_VERIFICATION.md` exists and contains pinned SHA + CLEAN result ✅

## Notes

- Clone was made from upstream GitHub (NOT from AppData runtime install)
- `--config core.autocrlf=false` applied to prevent CRLF corruption of Python source
- Clone is a working audit copy; vendoring method deferred per D-011
