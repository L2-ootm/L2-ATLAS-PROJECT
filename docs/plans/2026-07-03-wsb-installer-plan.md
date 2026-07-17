# WS-B — Installation Package Plan (npm wrapper + platform artifacts)

**Status:** superseded in part on 2026-07-17 by
`docs/plans/2026-07-17-npm-lifecycle-and-safe-update-design.md`. The thin-launcher decision remains;
the install root no longer shares `ATLAS_HOME`, global npm install now bootstraps the
release, and the release index owns an explicit runtime entrypoint.
**Companion docs:** `2026-07-03-finish-mission-analysis-and-execution-order.md` (WS-B
summary + rationale for the recommended approach), `2026-07-03-sprint-to-2026-07-09-
milestone-finish.md` (sprint contract: install/update/uninstall-rollback/doctor/clean-
machine/versioned-artifact are all required deliverables).

## 1. Problem statement

Today `scripts/install-atlas-cli.ps1` (Windows) and `scripts/setup.sh` (POSIX) are
source-checkout installers: they assume the repo is already cloned, build each
component from source in place (`go build`, `cargo build --release`, `npm run build`,
`pip install -e`), and write a portable `atlas.cmd` shim at the repo root. There is:

- No versioned, distributable artifact — you cannot install ATLAS without cloning the
  monorepo and having Go/Rust/Node/Python toolchains present.
- No update path — re-running the script rebuilds from whatever the working tree
  currently contains, not from a released version.
- No uninstall/rollback.
- No `doctor`-style install-time health check distinct from the runtime `atlas doctor`.

Constraint that shapes every option below: the product spans five toolchains (Python
runtime, Rust gateway binary, Go TUI binary, Bun/atlas-terminal — pending STAGE 3 —,
Node for freellmapi/discord sidecars). A pure `npm i -g atlas` cannot itself *be* the
runtime; it can only be the **distribution and lifecycle mechanism** for prebuilt
artifacts. This mirrors how opencode/MiMo-Code (the TUI donor) ship: npm install pulls
down platform-specific prebuilt binaries, not source.

## 2. Decision: npm wrapper + platform release bundle

Rejected alternatives (kept from the WS-B inventory, restated with reasoning):

| Option | Verdict | Why |
|---|---|---|
| Per-OS scripts only (status quo + version pin) | Rejected as sole path | Cheapest, but no `npm i -g` story, no update mechanism, still requires all toolchains on the target machine. |
| Full single-binary compile (PyInstaller etc.) | Rejected | High risk against the vendored Hermes foundation (dynamic imports, `foundation/atlas-hermes` tree-walk in `tui.py`); would require re-validating every code path bundles cleanly. Not worth it this sprint. |
| **npm wrapper + versioned release bundle** | **Chosen** | Matches donor project precedent operators already trust; npm is a ubiquitous, low-friction install surface; keeps each component built in CI with its native toolchain (no bundling risk); update/uninstall/rollback become artifact operations, not rebuild operations. |

## 3. Architecture

```
npm i -g @systemsl2/atlas
        │
        ▼
  bin/atlas.js (thin Node launcher, ~200 LOC)
        │
        ├─ on first run / `atlas install`: resolve platform (win32/darwin/linux ×
        │  x64/arm64), fetch the matching release bundle for the pinned version,
        │  verify checksum, unpack into ~/.atlas/versions/<version>/
        │
        ├─ maintains ~/.atlas/current -> versions/<version>  (symlink on POSIX,
        │  junction or a pointer file on Windows since junctions need elevation
        │  for some ops)
        │
        └─ every invocation execs the resolved platform binary/entrypoint for the
           subcommand (gateway, tui, cockpit-serve, python CLI) — the npm layer
           never re-implements ATLAS logic, it only locates and launches it.
```

The npm package itself ships **no heavy binaries** — it's a launcher plus a manifest of
download URLs per version/platform, matching the recommended approach's "thin launcher"
design. Release bundles are built and published separately (CI artifact, not npm
tarball) to keep the npm package small and avoid re-publishing multi-hundred-MB
platform binaries as npm tarballs (registry hygiene + install speed).

### 3.1 `~/.atlas` layout (extends the existing convention)

`ATLAS_HOME` (already read in `go_tui.py` and elsewhere; defaults to `~/.atlas`) becomes
the install root, not just the runtime state root:

```
~/.atlas/
  atlas.db                    # existing — untouched by install/update
  bin/                        # existing convention (go_tui.py already writes atlas-tui.exe here)
    atlas-tui.exe / atlas-tui
    atlas-gateway.exe / atlas-gateway
    atlas-terminal(.exe)      # ONLY once STAGE 3 promotes atlas-terminal to a shipped surface
  versions/
    0.2.0/
      bin/                    # versioned copies; `current` points here
      python/                 # pinned venv bootstrap or wheel cache
      cockpit/                # built cockpit static bundle
      manifest.json           # component versions + checksums for this release
    0.1.0/                    # prior version, retained until pruned — enables rollback
  current -> versions/0.2.0   # active version pointer
  install.json                 # { installedVersion, installMethod, lastUpdateCheck }
```

Rollback is then just "flip `current` back to `versions/<prior>` and re-run `atlas
doctor`" — no rebuild, no reinstall.

### 3.2 Release bundle contents (per platform × arch)

Built by CI (GitHub Actions / equivalent), one job per component reusing exactly what
`install-atlas-cli.ps1` / `setup.sh` already do today, but publishing the output instead
of leaving it in a working tree:

- `atlas-gateway` — `cargo build --release -p atlas-gateway` (native/atlas-core-rs).
- `atlas-tui` — `go build -trimpath -ldflags "-s -w"` (services/atlas-tui). **This
  entry becomes contested once STAGE 3 lands** — see §6.
- Python runtime — not a single binary; ship a pinned `requirements.lock`-driven venv
  bootstrap (`packages/atlas-core`, `services/agent-runtime[claude]`,
  `services/wiki-runtime` editable-equivalent, installed non-editable from a wheel
  cache) so `atlas install` doesn't require internet access to PyPI at install time
  beyond the first fetch, and is pinned per release rather than "whatever's on PyPI
  today."
- Cockpit — `npm run build` output (services/web-ui-react), static bundle, served by
  the gateway/cockpit control the same way it is now.
- `manifest.json` — version, per-component checksum (sha256), build commit SHA, build
  date. `atlas doctor` reads this to detect drift between what's installed and what's
  running (closes the "stale gateway binary" gap called out in WS-D).

## 4. CLI surface (npm launcher + `atlas` subcommands)

| Command | Behavior |
|---|---|
| `npm i -g @systemsl2/atlas` | Installs the thin launcher only. Prints next step. |
| `atlas install [--version X] [--channel stable\|nightly]` | First-run bootstrap: fetch bundle, verify checksums, unpack, set `current`, run `atlas db init`. |
| `atlas update [--version X]` | Fetch newer bundle into a new `versions/<n>` dir, run any migration hooks (DB migrations already idempotent per `db init`), flip `current`, keep the previous version on disk. |
| `atlas rollback [--to X]` | Flip `current` to a prior retained version; default = previous. Re-verify via `doctor`. |
| `atlas uninstall [--purge]` | Remove `versions/*` and `bin/`; `--purge` additionally removes `atlas.db` and config (explicit, confirmation-gated — destructive). Always leaves the npm package itself to `npm uninstall`. |
| `atlas doctor` | Extends the existing doctor (db/config/gateway/cockpit/provider) with: installed-vs-running binary checksum match (per manifest), sidecar reachability (freellmapi/cashflow/discord — currently missing per WS-D), disk space for `~/.atlas`, retained-version list + prune suggestion. |
| `atlas versions` | List installed versions, mark `current`, show channel/date. |

This is additive to the existing `atlas up` / `atlas gateway` / `atlas tui` command
tree — the npm layer owns *lifecycle* (install/update/rollback/uninstall), the existing
Typer CLI keeps owning *runtime* (start/stop/status/config).

## 5. Clean-machine verification path (sprint deliverable)

A documented, scripted check (`docs/runbooks/clean-machine-install.md` +
`scripts/ci/verify-clean-install.*`) that on a machine with **only** Node/npm present
(no Go, no Rust, no Python pre-installed beyond what the bundle brings):

1. `npm i -g @systemsl2/atlas`
2. `atlas install`
3. `atlas doctor` → all green
4. `atlas up` → gateway healthy, cockpit reachable
5. `atlas tui` → boots
6. `atlas update --version <next>` → succeeds, doctor green
7. `atlas rollback` → reverts cleanly, doctor green
8. `atlas uninstall --purge` → machine returns to pre-install state (verify no orphan
   processes, no leftover `~/.atlas`)

This becomes the acceptance test gate for "installer done," matching the sprint
contract's "clean-machine instructions" line item, and should run in CI on a fresh
container/VM per platform, not just documented for a human to run manually.

## 6. Open dependency on WS-A (STAGE 3) — do not lock yet

The bundle's TUI entry is undecided until the parity audit + retirement gate closes:

- **If Go TUI wins / stays default:** bundle ships `atlas-tui` only, as today. Simplest,
  no Bun runtime dependency added to the release bundle.
- **If atlas-terminal (donor-based) replaces it:** the bundle must also embed a Bun
  runtime or a `bun build --compile` standalone binary of `services/atlas-terminal`
  (Bun supports single-executable compilation) — adds a build job and a new binary
  entry, but keeps the same manifest/versions/current mechanism.
- **If both coexist for a transition window** (plausible given STAGE 3 explicitly
  frames this as a gated *decision*, not a foregone conclusion): bundle ships both,
  `atlas tui` keeps launching Go TUI, a new `atlas tui --next` or similar flag opts into
  atlas-terminal until the retirement gate flips the default.

Recommendation: build out §§1-5 (launcher, versions/current/rollback mechanism, doctor
extension, clean-machine script) now — none of it depends on which TUI ships. Defer only
the "which binaries go in the manifest" question and the Bun-compile CI job until STAGE
3 reports back, per the existing execution order (WS-B after WS-A outcome).

## 7. Sequencing / next steps

1. **DONE (2026-07-03)** — `packages/atlas-cli/` stands up the launcher mechanics against
   a manually staged local bundle (no CI/publishing yet): `bin/atlas.js` +
   `src/{paths,manifest,installState,commands}.js` implement `install --from <dir>
   --version X`, `update`, `rollback [--to X]`, `uninstall [--purge]`, `doctor`,
   `versions` against `~/.atlas/versions/<v>/` + a plain-text `current` pointer file
   (chosen over a symlink/junction — junctions need elevation for some operations on
   Windows, and a pointer file makes rollback a single atomic write on every platform).
   7 unit tests (`node --test test/commands.test.js`) plus a manual end-to-end run
   (install → doctor → update → doctor → rollback → doctor → uninstall → doctor) all
   pass. The package has since been promoted to the public contract name
   `@systemsl2/atlas` with bin `atlas`; local source-checkout shims remain a developer
   coexistence concern, not the published package name.
   **Not yet built**: the real release-fetch path (download + checksum-verify a
   published bundle for `--version X --channel stable`) — `install`/`update` currently
   only accept `--from <local dir>`, exactly matching this step's own scope ("prove the
   mechanics... without blocking on release infrastructure").
2. Wire `atlas doctor` checksum/manifest checks. **DONE** — `manifest.js`'s
   `buildManifest`/`verifyManifest`; covered by the checksum-drift test case.
3. **PARTIAL (2026-07-07)** — clean-machine runbook + verification script added:
   `docs/runbooks/clean-machine-install.md` and `scripts/ci/verify-clean-install.js`.
   The script runs install → doctor → update → doctor → rollback → doctor → uninstall
   → doctor against release-manifest artifacts. Local dry-run passed against generated
   `file://` release indexes and tarballs. Still missing: the same gate on actual clean
   VMs using real hosted artifacts.
4. Once STAGE 3 (WS-A) reports its TUI decision, finalize the manifest's binary list and
   add the corresponding CI build job(s).
5. **PARTIAL (2026-07-07)** — release-manifest fetch/extract path exists in
   `packages/atlas-cli`: `install --manifest <url> [--channel stable] [--version X]
   [--platform os-arch]` and `update --manifest ...` can read a release index from
   `file://`, `http://`, or `https://`, select the version/platform artifact, download
   the `.tar/.tar.gz` bundle, verify its sha256, extract it with system `tar`, write
   `manifest.json`, and flip the `current` pointer. This keeps the npm wrapper thin
   and dependency-free. Covered by `node --test test/commands.test.js` with a real tarball
   fixture and checksum-mismatch regression.

   Expected release index shape:

   ```json
   {
     "channels": { "stable": "0.1.0" },
     "releases": {
       "0.1.0": {
         "platforms": {
           "win32-x64": {
             "url": "https://.../atlas-0.1.0-win32-x64.tar.gz",
             "sha256": "<archive sha256>"
           }
         }
       }
     }
   }
   ```

   **LOCAL BUILDER DONE (2026-07-07)** — `packages/atlas-cli/src/buildReleaseIndex.js`
   and `scripts/ci/build-release-index.js` now package a staged bundle into
   `atlas-<version>-<platform>.tar.gz`, compute sha256, and write a release index.
   The builder output was verified by feeding two generated indexes into
   `scripts/ci/verify-clean-install.js`; all 8 lifecycle steps passed. Still missing
   before calling WS-B done: real GitHub Release upload/publishing, real published
   release-index URL, and clean-machine verification against hosted artifacts.
6. Stand up real CI publishing (GitHub Releases or equivalent artifact host) + npm
   package publish for `@systemsl2/atlas`.
7. Run the clean-machine gate for real, on actual clean VMs per platform, before calling
   WS-B done.
