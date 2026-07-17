# npm lifecycle and safe-update design

**Status:** accepted implementation contract  
**Date:** 2026-07-17

## Outcome

`npm install --global @systemsl2/atlas` installs a small lifecycle launcher plus an exact
OS/CPU-specific optional npm package containing the complete ATLAS runtime. This
avoids npm install scripts, which current npm versions may block unless explicitly
allow-listed. On first invocation, the launcher verifies and materializes the
platform payload, then delegates normal commands to the active runtime.

The development checkout is never an installation target. Immutable application
versions and mutable operator state have separate ownership:

| Owner | Windows default | Update behavior |
|---|---|---|
| npm launcher/platform package | `%APPDATA%\npm` | Replaced by npm |
| immutable ATLAS releases | `%LOCALAPPDATA%\atlas\versions\<version>` | Versioned and retained |
| lifecycle metadata | `%LOCALAPPDATA%\atlas` | Updated only after verification |
| operator state | `%USERPROFILE%\.atlas` (`ATLAS_HOME`) | Preserved |
| user/agent modules | `%USERPROFILE%\.atlas\modules` | Preserved |

`ATLAS_INSTALL_ROOT` overrides the application root. `ATLAS_HOME` continues to mean
runtime state only.

## Platform-package contract

Each `@systemsl2/atlas-<os>-<arch>` package is restricted by npm `os` and `cpu` metadata and
contains an `atlasPlatform` object with its version, runtime directory, and safe
relative entrypoint (for example `bin/atlas.exe`). The payload must contain the full
runtime; clean-machine acceptance may assume Node/npm but not Go, Rust, Python, Bun,
Git, or a source checkout.

## Update transaction

1. Check the npm registry for a newer `@systemsl2/atlas` version.
2. Run `npm install --global @systemsl2/atlas@<version>` when newer; npm resolves the exact
   matching platform package.
3. Validate the platform contract and ensure the entrypoint cannot escape the payload.
4. Copy into a new immutable version directory and create its per-file manifest.
5. Change `current` only after verification succeeds.
6. Retain the prior version for `atlas rollback`.

Update and rollback never write to `ATLAS_HOME`. Direct edits inside an installed
release are unsupported checksum drift. Future ATLAS self-upgrades must use versioned,
auditable overlays outside the release tree; ATLAS does not yet safely rewrite its
own core.

## Acceptance gates

- clean Windows VM installation from the public-style npm command;
- `atlas doctor`, `atlas up`, WebUI, and terminal startup;
- update and rollback with the previous runtime retained;
- byte-identical user module and persistent state across update/rollback;
- corrupted payload rejection without a `current` pointer change;
- npm scope ownership, platform package, and launcher published first as a private
  prerelease;
- full-history secret/privacy scan and public-repository cleanup complete.
