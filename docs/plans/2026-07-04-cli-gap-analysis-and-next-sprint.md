# CLI Gap Analysis & Next Sprint — Full Atlas Command Surface + npm Package

**Date:** 2026-07-04
**Author:** MiMoCode Compose Agent (analysis), operator-directed
**Companion docs:**
- `2026-07-03-wsb-installer-plan.md` (npm wrapper architecture — already drafted)
- `2026-07-04-cli-audit-and-npm-package-status.md` (prior audit)
- `2026-07-03-finish-mission-analysis-and-execution-order.md` (WS-A..WS-G workstreams)
- `HANDOFF.md` (current continuation state)

---

## 1. Current CLI command surface (what exists)

### Top-level commands

| Command | Exists | Has --json | Notes |
|---------|--------|-----------|-------|
| `atlas` (bare) | YES | — | Launches Go TUI workbench |
| `atlas up` | YES | NO | Boots gateway + cockpit + freellmapi (sidecar) |
| `atlas doctor` | YES | YES | 8 checks: db, config, gateway, cockpit, 3 sidecars, model_registry, provider, claude_code |
| `atlas version` | YES | YES | Prints version |
| `atlas setup` | YES | NO | First-run config wizard |
| `atlas tui` | YES | — | Launches Go TUI explicitly |
| `atlas help` | NO | — | Missing alias; `atlas --help` works but no explicit `help` command |

### Subcommand groups

| Group | Commands | --json | Status |
|-------|----------|--------|--------|
| `atlas mission` | create, run, cancel, status, retry, purge-archived | partial | Functional |
| `atlas project` | list, register, remove | NO | Functional |
| `atlas db` | init, status | NO | Functional |
| `atlas gateway` | start, status, stop | NO | Functional |
| `atlas module` | list, activate, deactivate | NO | Functional |
| `atlas cashflow` | start, status, stop | NO | Functional |
| `atlas freellmapi` | start, status, stop | YES | Functional |
| `atlas graph` | build | YES (always JSON) | Functional |
| `atlas run` | (background executor) | — | Internal |
| `atlas focus` | set, show, clear | NO | Command Center |
| `atlas goal` | create, list, update, complete | NO | Command Center |
| `atlas task` | create, list, update, complete | NO | Command Center |
| `atlas observe` | add, list | NO | Command Center |
| `atlas operation` | run | NO | Command Center |
| `atlas golden` | (workflows) | partial | Golden workflows |
| `atlas runtime` | (daemon) | — | Internal |
| `atlas wiki` | (optional) | — | Conditional import |
| `atlas foundation` | (legacy) | — | D-001 boundary |
| `atlas config` | get, set, patch, show, export, import | partial | Control plane |
| `atlas auth` | status, add, remove, codex-status, import-codex, json | partial | Provider auth |
| `atlas models` | list, refresh, status | YES | Model registry |
| `atlas provider` | status, modes, test | YES | Provider mesh |
| `atlas channels` | status, json | partial | Messaging gateway |
| `atlas discord` | start, status, stop, propose, approvals, approve, reject | YES | Discord sidecar |
| `atlas tools` | list, status | YES | Tool manifest |
| `atlas surface` | list, close | YES | Surface sessions |
| `atlas terminal` | status | YES | atlas-terminal build check |

---

## 2. Gap inventory — what's missing

### GAP 1: No `atlas down` (unified shutdown)

`atlas up` boots gateway + cockpit + freellmapi. There is NO symmetric `atlas down`. Each component has its own `stop` subcommand, but no operator-facing single command to shut everything down cleanly.

**What `atlas down` should do (reverse of `atlas up`):**
1. Stop freellmapi sidecar (if running)
2. Stop cashflow module (if running)
3. Stop discord sidecar (if running)
4. Stop cockpit (if running)
5. Stop gateway (last — everything depends on it)
6. Report what was stopped

**Design:** Idempotent, `--json` flag, ordered shutdown (sidecars first, gateway last). Same pattern as `atlas up` but reversed. Should handle "already stopped" gracefully (no error, just report).

### GAP 2: `atlas freellmapi` is already `start/status/stop` — operator said "up/down"

The operator said "freellmapi (up/down) to start atlas native clone of freellmapi." The existing commands are `atlas freellmapi start/status/stop`. Two possibilities:
- **Option A:** Add `atlas freellmapi up` and `atlas freellmapi down` as aliases for `start`/`stop` (consistent with `atlas up`/`atlas down`)
- **Option B:** Keep `start/stop` as-is, add `atlas down` as the top-level unified shutdown

**Recommendation:** Option B — `start/stop` are fine per-component. The real gap is the unified `atlas down`. Add `up`/`down` aliases only at the top level.

### GAP 3: Full npm package installer (`npm i -g @systemsl2/atlas`)

The user wants MiMoCode/Hermes-style install: `npm i -g @systemsl2/atlas` installs everything. Currently:
- `packages/atlas-cli/` exists with launcher mechanics (install/update/rollback/uninstall/doctor/versions)
- But it only accepts `--from <local dir>`, not a real remote fetch
- No CI publishing, no release bundle, no checksum verification against a remote host
- Bin name is now `atlas` for the npm package; source-checkout Python `atlas` remains a developer PATH coexistence concern.

**What needs to happen:**
1. **npm package naming:** Decide `@systemsl2/atlas` vs `@systemsl2/atlas-cli` — the user said `npm install` should "install the entire thing," so `@systemsl2/atlas` is the target name
2. **Release bundle hosting:** GitHub Releases or a dedicated artifact host. Each release = platform-specific tarball containing:
   - `atlas-gateway` binary (Rust, cross-compiled)
   - `atlas-tui` binary (Go, cross-compiled) — or atlas-terminal if retirement gate passes
   - Python venv bootstrap (pinned deps, non-editable install)
   - Cockpit static bundle (built `services/web-ui-react`)
   - `manifest.json` (versions + checksums)
3. **`atlas install`** = first-run: resolve platform, fetch bundle, verify checksum, unpack to `~/.atlas/versions/<v>/`, set `current` pointer, run `atlas db init`
4. **`atlas update`** = fetch newer bundle, unpack, flip `current`, keep previous for rollback
5. **`atlas doctor`** extension = checksum-vs-manifest verification
6. **CI publishing** = GitHub Actions: build each component, package into tarballs, publish to GitHub Releases, publish npm package

### GAP 4: `atlas update` (pull new version)

Currently `atlas update` only accepts `--from <local dir>`. The real flow:
1. Check latest version from release channel (GitHub Releases API or a manifest endpoint)
2. Compare with installed version
3. If newer: fetch bundle, verify checksum, unpack, flip `current`
4. Run any migration hooks (DB migrations are already idempotent)
5. Report what changed

### GAP 5: Full vendor/donor cleanup

The boundary scanner passes clean for the forbidden terms list, but the operator wants a deeper cleanup to "maintain our branding intact." This means:
1. **Theme JSON `$schema`** — already fixed (no more opencode.ai)
2. **`dialog-go-upsell.tsx`** — already removed
3. **`/share` command** — already removed
4. **`tui-migrate.ts`** — already fixed
5. **Remaining vendor surface to audit:**
   - `src/vendor/opencode/` — ~60 files of vendored utility code. These are MIT-licensed utilities, not branding. But any references to donor product names, URLs, or behavior should be scrubbed
   - `src/vendor/plugin/tui.ts` — plugin system shim. References to donor plugin APIs need ATLAS equivalents or explicit "not implemented" stubs
   - `src/vendor/shared/` — filesystem, glob, hash utilities. Should be clean but need a sweep
   - `src/tui/i18n/` — 7 locale files. Check for donor-specific translation keys (like `mimo_login`, `mimo_free` mentioned in STAGE 2c notes)
   - `src/tui/config/tui.ts` — TUI config schema. Check for donor-specific config keys
   - `src/tui/context/flag/flag.ts` — feature flags. Check for donor-specific flags like `ATLAS_TUI_EXPERIMENTAL_WORKFLOW_TOOL`
   - `parsers-config.ts` — tree-sitter parser config. Check for donor-specific parsers

### GAP 6: CLI polish items from prior audit

From the 2026-07-04 CLI audit:
- **`--json` convention mixed:** some groups use `--json` flag, some use dedicated `json` subcommand. Not blocking but should be standardized
- **Error contract inconsistent:** newer commands return `{error:{code,message,remediation}}`, older ones echo raw strings
- **`atlas help` missing:** should be an alias for `atlas --help`
- **Wiki group silent disappearance:** `atlas_wiki` ImportError → pass should surface an explanatory stub

---

## 3. Recommended next sprint scope

### Phase 1: `atlas down` + CLI completion (small, high-value)

| Task | Scope | Est. |
|------|-------|------|
| `atlas down` | Reverse of `atlas up`: stop sidecars → cockpit → gateway. Idempotent, `--json`. | 30 min |
| `atlas help` | Alias for `atlas --help`. Add `no_args_is_help=True` per group. | 10 min |
| Wiki stub | When `atlas_wiki` missing, surface "wiki not installed" instead of silent pass. | 10 min |

### Phase 2: npm package — real install path (medium, high-value)

| Task | Scope | Est. |
|------|-------|------|
| Rename `@systemsl2/atlas-cli` → `@systemsl2/atlas` | DONE 2026-07-07: package name is `@systemsl2/atlas`, bin is `atlas`, metadata contract is test-covered. | Done |
| Real release fetch | `atlas install` / `atlas update` fetch from GitHub Releases (platform detection, checksum verify) | 2-3 hours |
| `atlas doctor` manifest check | Compare running binaries vs manifest checksums | 1 hour |
| `atlas versions` | List installed versions, mark current | 30 min |
| `atlas rollback` | Flip `current` pointer, re-verify | 30 min |
| `atlas uninstall` | Remove versions + optionally config | 30 min |
| Clean-machine runbook | `docs/runbooks/clean-machine-install.md` | 1 hour |

### Phase 3: Vendor/donor deep cleanup (medium, low-risk)

| Task | Scope | Est. |
|------|-------|------|
| Sweep `src/vendor/opencode/` | Remove or rename any donor product references | 1 hour |
| Sweep `src/tui/i18n/` | Remove `mimo_login`/`mimo_free` keys, donor-specific strings | 30 min |
| Sweep `src/tui/config/` | Remove donor-specific config keys | 30 min |
| Sweep `src/tui/context/flag/` | Remove or rename donor-specific flags | 15 min |
| Update forbidden-terms list | Add any newly found terms | 15 min |
| Re-run boundary scanner | Confirm clean | 5 min |

### Phase 4: CLI `--json` standardization (larger, lower priority)

| Task | Scope | Est. |
|------|-------|------|
| Standardize all read commands to `--json` | Fold `auth json`/`channels json`/`config json` into `--json` flags | 2-3 hours |
| Standardize error contract | All commands return `{error:{code,message,remediation}}` on failure | 2-3 hours |

---

## 4. Architecture decisions needed

### D-NEXT-01: npm package name

**Resolved 2026-07-07:** use `@systemsl2/atlas` with bin `atlas`. The Python `atlas` on PATH is the source-checkout shim (`atlas.cmd` at repo root). The npm package's `atlas` binary lives in a different prefix (`$(npm prefix)/bin/`). On a clean machine, there is no conflict. On a dev machine, PATH order decides which development entrypoint is used.

### D-NEXT-02: Release bundle host
- **Option A:** GitHub Releases (free, familiar, API available)
- **Option B:** Dedicated artifact host (S3/R2 + CloudFront)

**Recommendation:** GitHub Releases — zero infrastructure cost, `gh release` API for version checking, download URLs are stable. Migrate to a dedicated host only if bandwidth或reliability demands it.

### D-NEXT-03: TUI binary in bundle
Deferred until retirement gate (Go TUI vs atlas-terminal). The bundle manifest should be designed to accommodate either or both, but the actual decision waits for operator UAT.

---

## 5. Execution order

1. `atlas down` + `atlas help` + wiki stub (Phase 1) — quick wins, ship today
2. npm package rename + real release fetch (Phase 2 core) — the main deliverable
3. Vendor cleanup sweep (Phase 3) — while the npm package is being tested
4. CLI standardization (Phase 4) — only if time permits before 2026-07-09 deadline

Each phase: verify → commit → update HANDOFF.md + STATE.md.

---

## 6. Execution update — 2026-07-07

### Completed in this pass

| Item | Result | Verification |
|------|--------|--------------|
| `atlas down` | Added top-level shutdown command. Stops FreeLLMAPI, Cashflow, Discord, Cockpit, then Gateway. Includes `--json`. Treats already-stopped/not-managed component messages as idempotent success at the top-level command. | `pytest services/agent-runtime/tests/test_cli_up.py services/agent-runtime/tests/test_cli.py -q` → 24 passed |
| `atlas help` | Added explicit root help alias for operators who type `atlas help` instead of `atlas --help`. | Same focused CLI suite |
| `atlas wiki` discoverability | The wiki group now prints command help when invoked without a subcommand. If the optional wiki runtime is absent, root CLI now registers an explanatory stub instead of silently hiding the group. | Same focused CLI suite |
| Native harness context handoff | Existing worktree changes were verified: `NativeAtlasAgent` passes the persisted run contract/operator context into the harness `system_message`; contract replay includes `context_markdown`. | `pytest services/agent-runtime/tests/test_agent_contract_service.py services/agent-runtime/tests/test_agents.py -q` → 22 passed |

### Completed in continuation — 2026-07-07

| Item | Result | Verification |
|------|--------|--------------|
| atlas-terminal session-create diagnostics | Added dependency-free structured formatting for session-create SDK errors and wired the interactive prompt failure branch to emit `ATLAS_SESSION_CREATE_ERROR` via `console.error`. This captures the actual error on the next real Windows Terminal reproduction; it does not claim the root cause is fixed. | `bun test test/sessionError.test.ts` → 2 passed; `bun test` → 28 passed; `bunx tsc --noEmit` → clean |
| atlas-terminal donor residue cleanup | Removed remaining user-facing donor strings from sidebar footer, crash issue URL, status command identity, MCP auth hint, GitHub trigger tips, and Docker tips. Extended the boundary scanner with exact regressions (`/opencode`, `github.com/anomalyco/opencode`, `ghcr.io/anomalyco/opencode`, `opencode mcp auth`, `<b>MiMo</b>`). | `pwsh ... scan-atlas-terminal-boundary.ps1` → passed; `bun test` → 28 passed; `bunx tsc --noEmit` → clean; smoke → gateway offline |
| atlas-terminal fallback/temp-name cleanup | Added exact scanner rules first, observed a failing boundary scan, then removed donor fallback text (`opencode does not support MCP authentication yet`, `mimo models`), MiMo-style custom-provider examples, the `opencode-go` marketing blurb, and donor-named temp files. | `pwsh ... scan-atlas-terminal-boundary.ps1` → passed; `bun test` → 28 passed; `bunx tsc --noEmit` → clean; smoke → gateway offline; exact `rg` returned no matches |
| npm wrapper JSON polish | Added `--json` to the npm wrapper entrypoint for lifecycle results, `doctor`, `versions`, and structured command errors while preserving human output by default. | Added failing entrypoint tests first; `cd packages/atlas-cli && npm test` → 15 passed |
| local release artifact builder | Added a dependency-free builder module and CI wrapper that packages staged bundles into platform tarballs plus release indexes consumable by `install --manifest`. | Added failing builder test first; `cd packages/atlas-cli && npm test` → 16 passed; builder output fed into `verify-clean-install` → all 8 steps OK |

### Still open

| Priority | Gap | Next action |
|----------|-----|-------------|
| P0 | `atlas-terminal` interactive "Creating a session failed" toast | Reproduce in real Windows Terminal and capture the emitted `ATLAS_SESSION_CREATE_ERROR` line before changing session logic. |
| P1 | npm package real install/update path | Remote release manifest fetch, checksum verification, local installed-version registry, rollback, runbook, script-safe wrapper JSON, and local artifact/index building are implemented locally; publish real artifacts/index and run clean-machine gates. |
| P1 | Vendor/donor deep cleanup | Current presentation-layer and fallback/temp-name sweeps are complete for confirmed user-facing/observable donor strings; keep generated SDK/internal provider IDs under review, and extend scanner only for concrete user-facing leaks. |
| P2 | CLI `--json` convention | Standardize toward `--json` flags after the installer path is stable. |
| P2 | Error contract consistency | Normalize older CLI errors into `{error:{code,message,remediation}}` where JSON mode exists. |

### Anti-bloat notes

- No dependency additions.
- `atlas down` uses existing lifecycle control modules only.
- No new service, daemon, state store, or background process was introduced.
- The only normalization added is top-level idempotence for shutdown messages; component subcommands retain their existing semantics.
