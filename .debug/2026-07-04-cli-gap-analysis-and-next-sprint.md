# 2026-07-04 — CLI Gap Analysis & Next Sprint

## Current CLI command surface

### Top-level commands
| Command | Exists | --json | Notes |
|---------|--------|--------|-------|
| `atlas` (bare) | YES | — | Launches Go TUI |
| `atlas up` | YES | NO | Boots gateway + cockpit + freellmapi |
| `atlas doctor` | YES | YES | 8 health checks |
| `atlas version` | YES | YES | |
| `atlas setup` | YES | NO | First-run wizard |
| `atlas tui` | YES | — | Explicit TUI launch |

### Missing commands
| Command | What it does | Priority |
|---------|-------------|----------|
| `atlas down` | Reverse of `atlas up` — stop sidecars → cockpit → gateway. Idempotent. | HIGH |
| `atlas help` | Alias for `atlas --help` | LOW |
| Wiki stub | Surface "wiki not installed" instead of silent ImportError pass | LOW |

### Subcommand groups
| Group | Commands | --json |
|-------|----------|--------|
| `atlas mission` | create, run, cancel, status, retry, purge-archived | partial |
| `atlas project` | list, register, remove | NO |
| `atlas db` | init, status | NO |
| `atlas gateway` | start, status, stop | NO |
| `atlas module` | list, activate, deactivate | NO |
| `atlas cashflow` | start, status, stop | NO |
| `atlas freellmapi` | start, status, stop | YES |
| `atlas graph` | build | YES |
| `atlas config` | get, set, patch, show, export, import | partial |
| `atlas auth` | status, add, remove, codex-status, import-codex, json | partial |
| `atlas models` | list, refresh, status | YES |
| `atlas provider` | status, modes, test | YES |
| `atlas channels` | status, json | partial |
| `atlas discord` | start, status, stop, propose, approvals, approve, reject | YES |
| `atlas tools` | list, status | YES |
| `atlas surface` | list, close | YES |
| `atlas terminal` | status | YES |

## What needs to be built

### 1. `atlas down` — unified shutdown
Reverse of `atlas up`. Stop sidecars first (freellmapi, cashflow, discord), then cockpit, then gateway last. Idempotent, --json flag.

### 2. Full npm package installer
Like MiMoCode/Hermes: `npm i -g @l2/atlas` installs everything. Needs:
- Release bundle hosting (GitHub Releases)
- `atlas install` — first-run: fetch bundle, verify checksum, unpack to `~/.atlas/versions/<v>/`
- `atlas update` — fetch newer bundle, flip `current` pointer
- `atlas rollback` — revert to prior version
- `atlas uninstall` — remove versions + optionally config
- `atlas doctor` extension — checksum-vs-manifest verification
- CI publishing pipeline

### 3. Deep vendor/donor cleanup
Current state: boundary scanner passes for forbidden terms. Remaining:
- `src/vendor/opencode/` — ~60 files of vendored utilities (MIT, but audit for donor product refs)
- `src/tui/i18n/` — check for `mimo_login`/`mimo_free` keys
- `src/tui/config/` — check for donor-specific config keys
- `src/tui/context/flag/` — check for donor-specific flags
- `parsers-config.ts` — check for donor-specific parsers

### 4. CLI standardization
- `--json` convention: some groups use `--json`, some use `json` subcommand. Standardize on `--json`.
- Error contract: newer commands return `{error:{code,message,remediation}}`, older echo raw strings.
- `atlas help` alias for `atlas --help`.
- Wiki group: surface explanatory stub when `atlas_wiki` missing.

## Architecture decisions needed

### D-NEXT-01: npm package name
- `@l2/atlas` (clean, user expectation) vs `@l2/atlas-cli` (avoids PATH conflict)
- Recommendation: `@l2/atlas` — no conflict on clean machine

### D-NEXT-02: Release bundle host
- GitHub Releases (zero infra cost) vs dedicated artifact host
- Recommendation: GitHub Releases

### D-NEXT-03: TUI binary in bundle
Deferred until retirement gate (Go TUI vs atlas-terminal).

## Execution order
1. `atlas down` + `atlas help` + wiki stub (quick wins)
2. npm package rename + real release fetch (main deliverable)
3. Vendor cleanup sweep
4. CLI standardization (if time permits before 2026-07-09)
