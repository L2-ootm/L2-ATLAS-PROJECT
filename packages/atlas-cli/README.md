# @l2/atlas

Lifecycle launcher for [ATLAS](https://github.com/L2-ootm/L2-ATLAS-PROJECT) —
an AI cockpit for agentic coding.

This package is a thin, dependency-free launcher that installs, updates,
rolls back, and uninstalls **versioned ATLAS release bundles** under
`~/.atlas/versions` with an atomic `current` pointer. It never builds from
source.

## Install

```powershell
npm install --global @l2/atlas
atlas install --manifest <release-manifest-url>
```

While ATLAS is pre-release (no published bundles yet), use the one-line
source bootstrap instead:

```powershell
irm https://raw.githubusercontent.com/L2-ootm/L2-ATLAS-PROJECT/main/install/install.ps1 | iex
```

## Commands

```
atlas install   --manifest <url> | --from <bundleDir>
atlas update    --manifest <url>
atlas rollback  [--to <version>]
atlas uninstall [--purge]
atlas doctor
atlas versions
```

All commands support `--json` for script-safe output.

Requires Node.js 20 or newer. MIT licensed. Issues:
<https://github.com/L2-ootm/L2-ATLAS-PROJECT/issues>.
