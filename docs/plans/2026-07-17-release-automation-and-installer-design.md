# ATLAS release automation and installer design

## Decision

ATLAS has one canonical public distribution path: the small
`@systemsl2/atlas` lifecycle launcher plus an exact OS/CPU runtime package. The
Windows runtime is self-contained. Only Node.js 20+ and npm exist outside the
payload; Python, Python requirements, the Claude Agent SDK, the Rust gateway,
the Go terminal UI, the compiled cockpit, and runtime sources are versioned
inside the platform package.

The PowerShell bootstrap is release-first. It installs Node LTS through winget
when necessary, installs the canonical npm launcher, invokes that launcher by
absolute path, materializes the runtime, and repairs only legacy ATLAS-owned
shims. Git/Python/build toolchains are required only by explicit source mode.

## Release flow

`scripts/release/npm-release.ps1` is the internal release authority:

1. `Prepare` sets the launcher and platform dependency to one exact version,
   runs lifecycle/config/doctor tests, builds the runtime, produces both
   tarballs, and checks the embedded Python dependency closure.
2. The operator reviews and commits the versioned source and waits for public CI.
3. `Publish` requires a clean tree, authenticated npm identity, and an unused
   version. It publishes the platform package first and the launcher second so
   users never resolve a launcher whose runtime is missing.
4. `Verify` confirms both exact versions through the public registry.

Publishing is deliberately not hidden behind a postinstall hook or automatic
background task. Every outward mutation remains explicit, reviewable, and
auditable.

## Update flow

`atlas update` checks npm for a newer launcher, globally installs it, hands
control to the new code, materializes its exact platform package into
`%LOCALAPPDATA%\atlas\versions\<version>`, and switches the current pointer only
after validation. `ATLAS_HOME`, the database, credentials, wiki, logs, and user
modules are outside immutable application versions and are preserved.

## Failure behavior

- Missing/outdated Node: PowerShell bootstrap installs current Node LTS.
- Missing Python or native toolchain: irrelevant for Windows release installs.
- Failed package build/test/auth: publication stops before registry mutation.
- Platform publication failure: launcher is not published.
- Runtime validation failure: current version is not switched.
- Old source shim shadows npm: bootstrap rewrites the ATLAS-owned compatibility
  shim to the absolute npm launcher.
