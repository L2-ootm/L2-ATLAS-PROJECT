# Pre-public security gate — 2026-07-17

Scope: make the repository safe to flip public. The flip itself was NOT
performed (operator decision, per instruction).

## 1. What was scanned

- **Tracked tree** — `git grep` for API-key prefixes (sk-, sk-ant-, ghp_,
  github_pat_, xox[baprs]-, AIza, AKIA) and private-key blocks.
- **Full history, filenames** — every file ever added (`git log --all
  --diff-filter=A --name-only`, via `rtk proxy` because the RTK hook
  truncates piped git output) matched against sensitive-name patterns
  (.env, .pem, .key, auth.json, state/config JSON, secrets/credential).
- **Full history, content** — `git log --all -p` (775 commits) grepped for
  real key material patterns.
- **Tracked env/db/private files** — `git ls-files` name check.

## 2. Findings

| # | Finding | Verdict |
|---|---|---|
| 1 | Tree key-pattern hits are all prefix-handling/redaction source in the vendored foundation (`anthropic_adapter.py`, `redact.py`, …) | Not secrets — PASS |
| 2 | History content hits are all test fixtures/canaries (`AKIAIOSFODNN7EXAMPLE`, `sk-ant-super-secret-do-not-leak`, `sk-canary-…`) | Not secrets — PASS |
| 3 | No `.env`, `.pem`, `.key`, `auth.json`, DB, or sidecar state file was ever committed (filename history scan) | PASS |
| 4 | `foundation/atlas-hermes/.envrc` is tracked — direnv/nix watch file, no values | PASS |
| 5 | `.env.example` (root + foundation) are templates with an explicit no-secrets policy | PASS |
| 6 | Untracked local state (`.mimocode/`, `.ops/freellmapi-backup/` — the backup JSONs can embed keys, `.planning/ultra/_*.py` scratch, `*.backup`) | Now gitignored (this commit) — cannot be committed accidentally |
| 7 | 25 occurrences of `C:\Users\Davi` machine paths across 18 tracked files (mostly `.planning/`, HANDOFF.md) | **Flagged, accepted-risk**: personal username/paths, not secrets. Publicizing `.planning/` is currently intended (README links STATE.md). Operator may prune before flipping public. |
| 8 | Git author identity (name/email) will become public with the history | Normal for public repos — operator awareness |

## 3. Result

**PASS** — no secret material in the tracked tree or in any reachable
history. Remaining exposure is limited to personal machine paths and
authorship metadata (finding 7/8), which are privacy preferences, not
security defects.

## 4. Before flipping public (operator checklist)

1. Decide on finding 7 (keep `.planning/` public as-is, or prune paths).
2. Push `main` (currently many commits ahead of origin) and merge/land
   `codex/chat-actor-workspace`.
3. Re-run this gate's tree scan on the final HEAD if more sessions land
   between now and the flip.
