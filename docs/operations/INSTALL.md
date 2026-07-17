# Installing ATLAS

Status: public npm research preview for Windows x64. The production platform package
and launcher are published and passed anonymous-registry isolated UAT. Independent
clean-Windows UAT remains recommended for release acceptance.

## Windows — one line (PowerShell)

```powershell
irm https://raw.githubusercontent.com/L2-ootm/L2-ATLAS-PROJECT/main/install/install.ps1 | iex
```

What it does:

1. Checks git / Node.js ≥ 20 / Python ≥ 3.11 and offers winget installs for
   anything missing.
2. Clones (or fast-forwards) the repo into `~\atlas` and runs
   `scripts/install-atlas-cli.ps1`: dedicated venv, editable installs, DB
   migrations, `atlas` on PATH.
3. Prints the next steps (`atlas doctor`, `atlas up`, `atlas`).

Parameters (call the script directly instead of `| iex` to pass them):
`-InstallDir`, `-Repo`, `-Claude` (adds the Claude Code runtime extra),
`-ReleaseManifest <url>` (switches to release mode below).

## npm — public release path

```powershell
npm install -g @systemsl2/atlas
atlas doctor
atlas up
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

The first download is approximately 51 MB compressed and 138 MB unpacked. During the
preview, expect roughly 275 MB of application disk use because npm keeps its package
copy and ATLAS materializes a separately verified immutable release. Operator state
grows independently under `ATLAS_HOME`.

Maintainers can test a local artifact with `atlas install --manifest <file-or-url>`
or `atlas install --from <bundleDir> --version <version>`.

## POSIX (macOS / Linux)

```
git clone https://github.com/L2-ootm/L2-ATLAS-PROJECT.git ~/atlas
cd ~/atlas && ./scripts/setup.sh
```

A curl-able `install.sh` mirroring `install.ps1` is planned alongside the
first public release.

## After install

- `atlas doctor` — environment/component health.
- `atlas up` — interactive service picker (gateway :8484, cockpit :5173,
  optional sidecars).
- `atlas` — terminal UI. The WebUI cockpit is at http://localhost:5173.
- Optional runtimes: Claude Code (`pip install -e services/agent-runtime[claude]`
  or `-Claude` at install), Codex (`npm i -g @openai/codex` + `codex login`).

## Update and rollback guarantees

`atlas update` downloads into a new version directory, validates the archive and
runtime entrypoint, and only then changes the active pointer. It does not delete or
rewrite `ATLAS_HOME`. The previous application version remains available:

```powershell
atlas update
atlas doctor
atlas rollback
```

Direct edits inside an installed release are unsupported and appear as checksum
drift in `atlas doctor`. Self-created extensions belong in `ATLAS_HOME/modules`.
Core upgrades arrive as new immutable npm platform packages: `atlas update` upgrades
the launcher, hands control to the newly installed launcher, verifies/materializes the
matching runtime, and keeps the previous runtime available for rollback.

## Deferred (documented, not built)

- Desktop app + signed `.exe` setup — after full stability; will wrap the
  same versioned bundles.
- Automated multi-platform release CI beyond the current Windows x64 builder.
- Independent clean-Windows cross-version update/rollback UAT.
- Auditable self-upgrade overlays for changes beyond user modules.
