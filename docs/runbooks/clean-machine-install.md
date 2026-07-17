# ATLAS Clean-Machine Install Verification

This runbook verifies the npm lifecycle wrapper against release-manifest artifacts.
It is the WS-B gate before calling installer work complete.

## Prerequisites

- Node.js 20+ and npm.
- A published release index URL for the install version.
- A published release index URL for the update version.
- A clean `ATLAS_HOME` directory, or no existing `~/.atlas`.

No Go, Rust, Python, Bun, system `tar`, or source checkout may be required by the
final gate. Archive extraction is implemented in the dependency-free npm launcher.

## Release Index Shape

```json
{
  "channels": { "stable": "0.1.0" },
  "releases": {
    "0.1.0": {
      "platforms": {
        "win32-x64": {
          "url": "https://.../atlas-0.1.0-win32-x64.tar.gz",
          "sha256": "<archive sha256>",
          "entrypoint": "bin/atlas.exe"
        }
      }
    }
  }
}
```

## Local Dry Run

Use local `file://` release indexes while CI publishing is not live yet.
First build release artifacts from staged bundle directories:

```powershell
node scripts/ci/build-release-index.js `
  --bundle C:\path\to\bundle-v1 `
  --out-dir C:\path\to\release-v1 `
  --version 0.1.0 `
  --platform win32-x64 `
  --entrypoint bin/atlas.exe

node scripts/ci/build-release-index.js `
  --bundle C:\path\to\bundle-v2 `
  --out-dir C:\path\to\release-v2 `
  --version 0.2.0 `
  --platform win32-x64 `
  --entrypoint bin/atlas.exe
```

Then verify the lifecycle against those generated indexes:

```powershell
node scripts/ci/verify-clean-install.js `
  --manifest file:///C:/path/to/release-v1/index.json `
  --update-manifest file:///C:/path/to/release-v2/index.json `
  --platform win32-x64
```

## Real Gate

After release artifacts are published:

```powershell
npm i -g @systemsl2/atlas
atlas doctor
atlas up
atlas update
atlas doctor
atlas rollback
atlas doctor
```

The verifier performs:

1. `install --manifest`
2. `doctor`
3. `update --manifest`
4. `doctor`
5. `rollback`
6. `doctor`
7. `uninstall`
8. `doctor` expecting no installed version

## Pass Criteria

- Every verifier step prints `OK`.
- The install and update artifacts pass sha256 verification before extraction.
- Normal commands are dispatched through the release index's safe relative
  `entrypoint`; no command resolves back into a source checkout.
- `doctor` is healthy after install, update, and rollback.
- `doctor` is unhealthy after uninstall because no version remains installed.
- The test is run on clean Windows, macOS, and Linux machines for each published platform artifact.
- A module created under `ATLAS_HOME/modules` before update remains byte-identical
  and loadable after update and rollback.
- The database, config, credentials, wiki, and logs under `ATLAS_HOME` remain present.
