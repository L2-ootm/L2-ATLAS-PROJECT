# Installing ATLAS

Status: public npm research preview for Windows x64. The production platform package
and launcher are published and passed anonymous-registry isolated UAT. Independent
clean-Windows UAT remains recommended for release acceptance.

## Windows — one line (PowerShell)

```powershell
irm https://raw.githubusercontent.com/L2-ootm/L2-ATLAS-PROJECT/main/install/install.ps1 | iex
```

What it does:

1. Checks Node.js ≥ 20 and installs the current Node LTS with winget when needed.
2. Installs `@systemsl2/atlas@latest`, resolves the npm launcher by absolute
   path, and materializes the exact Windows x64 runtime.
3. Verifies the immutable installation and prints the next steps (`atlas up`,
   `atlas doctor`, `atlas`).

Parameters (call the script directly instead of `| iex` to pass them):
`-ReleaseManifest <url>` for an advanced manifest override. Developer source
mode is explicit with `-Source`; only that mode uses `-InstallDir`, `-Repo`,
or `-Claude` and requires Git/Python/build tools.

## npm — public release path

```powershell
npm install -g @systemsl2/atlas
atlas install
atlas up --services gateway,cockpit
atlas doctor
```

The main npm package declares an exact OS/CPU-specific optional package containing
the complete runtime. This avoids install scripts that current npm versions may
block. The first `atlas` command verifies and materializes that local payload.
`atlas update` checks the npm launcher and matching platform package;
`atlas rollback`, `atlas versions`, and `atlas uninstall` own the application
lifecycle. Normal commands are forwarded to the active runtime.

Application releases and operator state are intentionally separate:

| Data | Windows default | Update behavior |
|---|---|---|
| npm launcher | `%APPDATA%\npm` | Replaced by npm |
| application releases | `%LOCALAPPDATA%\atlas\versions` | Immutable/versioned |
| active pointer + install metadata | `%LOCALAPPDATA%\atlas` | Updated transactionally |
| operator state | `%USERPROFILE%\.atlas` (`ATLAS_HOME`) | Preserved |
| user/agent modules | `%USERPROFILE%\.atlas\modules` | Preserved |

`ATLAS_INSTALL_ROOT` overrides the application root. `ATLAS_HOME` overrides the
state root. Installing or updating through npm never edits a development checkout.

The platform package includes embedded Python and all pinned Python runtime
requirements, including the Claude Agent SDK. npm keeps its package copy and ATLAS
materializes a separately verified immutable release, so disk usage is approximately
twice the unpacked platform payload. Operator state grows independently under
`ATLAS_HOME`.

Maintainers can test a local artifact with `atlas install --manifest <file-or-url>`
or `atlas install --from <bundleDir> --version <version>`.

## macOS / Linux — one line

```
curl -fsSL https://raw.githubusercontent.com/L2-ootm/L2-ATLAS-PROJECT/main/install/install.sh | bash
```

What it does (mirrors `install.ps1`'s RELEASE mode):

1. Checks Node.js ≥ 20 and auto-installs a pinned LTS build from nodejs.org
   under `~/.atlas/node` when missing (no sudo, no system package manager).
2. Installs `@systemsl2/atlas@latest` and materializes the exact runtime for
   the detected platform: `linux-x64`, `darwin-x64`, or `darwin-arm64`.
   Linux `arm64` is not yet built (v2).
3. Verifies the installation with `atlas doctor --install-only` and prints
   next steps (`atlas up`, `atlas doctor`, `atlas`).

Pass `--force` to reinstall even when already on the latest version, or
`--node-version N` to pin a different Node.js major version for the
auto-install fallback (default 22).

Status: the Linux/macOS runtime bundles and this installer are new
(Phase 2 Track B1) and have not yet had a clean-machine UAT pass — see
`docs/runbooks/clean-machine-install.md`. Treat as research-preview quality
until that gate runs, same as the existing Windows x64 path.

### Building from source instead

```
git clone https://github.com/L2-ootm/L2-ATLAS-PROJECT.git ~/atlas
cd ~/atlas && ./scripts/setup.sh
```

This clones the full repo and requires the developer toolchain (Python,
Node, Rust, Go). Most users want the one-line installer above instead.

## After install

- `atlas up` — interactive service picker (gateway :8484, cockpit :5173,
  optional sidecars).
- `atlas doctor` — integrity plus live component health; run it after `atlas up`
  when you expect gateway/cockpit to be online.
- `atlas` — terminal UI. The WebUI cockpit is at http://localhost:5173.
- Claude Code execution support is included in the Windows npm runtime. Codex remains
  operator-provided (`npm i -g @openai/codex` + `codex login`).

## Update and rollback guarantees

`atlas update` downloads into a new version directory, validates the archive and
runtime entrypoint, and only then changes the active pointer. It does not delete or
rewrite `ATLAS_HOME`. The previous application version remains available:

```powershell
atlas update
atlas up --services gateway,cockpit
atlas doctor
atlas rollback
```

Direct edits inside an installed release are unsupported and appear as checksum
drift in `atlas doctor`. Self-created extensions belong in `ATLAS_HOME/modules`.
Core upgrades arrive as new immutable npm platform packages: `atlas update` upgrades
the launcher, hands control to the newly installed launcher, verifies/materializes the
matching runtime, and keeps the previous runtime available for rollback.

## Deferred (documented, not built)

- Desktop app + signed `.exe`/`.dmg` setup — after full stability; will wrap
  the same versioned bundles.
- macOS code-signing/notarization — unsigned binaries only for now.
- Publishing the multi-platform release matrix (`.github/workflows/
  release-runtime-matrix.yml`) to an actual GitHub Release — the build+merge
  steps and the publish step (GITHUB_TOKEN, same `v*` tag as `publish-npm.yml`,
  asset published as `atlas-release-index.json` for `/releases/latest/download/`
  resolution — see the workflow's `merge-index` job comment) are now wired
  up, but have not yet run on real CI. Needs a `v*` tag push or
  `workflow_dispatch` to confirm end-to-end before this is a trusted channel.
- Independent clean-machine cross-version update/rollback UAT for Linux and
  macOS (Windows x64 has passed this gate; the new platforms have not).
- Auditable self-upgrade overlays for changes beyond user modules.
