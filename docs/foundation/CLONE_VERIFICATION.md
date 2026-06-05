---
phase: 01-hermes-foundation-audit
task: 01-01
created: 2026-06-05
---

# Hermes Clone Verification

## Clone Details

| Field | Value |
|-------|-------|
| Source | https://github.com/NousResearch/hermes-agent.git |
| Pinned SHA | `e8b9369a9d2df36139a5055cae3ed3c15691e03e` |
| Commit date | 2026-05-28 08:52:19 -0700 |
| Commit message | feat(openrouter): pass session_id in extra_body for sticky routing |
| Clone path | `_EXTERNAL_REPOS/hermes-agent/` (gitignored) |
| License | MIT |
| Version tag | v0.14.0 |

## SHA Verification

```
$ git -C _EXTERNAL_REPOS/hermes-agent rev-parse HEAD
e8b9369a9d2df36139a5055cae3ed3c15691e03e
```

Result: **VERIFIED** — HEAD matches pinned SHA exactly.

## Secret-Scan Gate

Scan scope: all files tracked or staged in L2-ATLAS-PROJECT (excludes `_EXTERNAL_REPOS/` which is gitignored).

Checks performed:
- No `.env`, `auth.json`, `*.db`, `*.key`, or `*.pem` files in tracked paths
- `_EXTERNAL_REPOS/` confirmed ignored by `.gitignore` rule (line 2)
- `git status --short` from project root shows only `.gitignore` as staged — no Hermes files entered git history

Result: **CLEAN** — no secret-bearing files in tracked paths.

## Gitignore Verification

```
$ git check-ignore -v _EXTERNAL_REPOS/
.gitignore:2:_EXTERNAL_REPOS/    _EXTERNAL_REPOS/
```

`_EXTERNAL_REPOS/` is excluded from git tracking by `.gitignore` line 2.

## Post-Clone Git Status

```
$ git status --short (from L2-ATLAS-PROJECT root)
A  .gitignore
```

No `_EXTERNAL_REPOS/` files appear as tracked. Gitignore rule is effective.

## Hard Constraints Honored

- [x] Cloned from upstream `https://github.com/NousResearch/hermes-agent.git` (NOT from `<USER_HOME>/AppData/Local/hermes/`)
- [x] `_EXTERNAL_REPOS/` gitignored before clone
- [x] Secret-scan CLEAN before `git add` of any audit artifacts
- [x] No Hermes state files (auth.json, .env, state.db, sessions/) in tracked paths
- [x] Working audit copy only — vendoring method deferred (D-011 LOCKED)
