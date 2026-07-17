# Installing ATLAS

Status: pre-release. The one-line bootstrap and the npm lifecycle launcher
both work today against a source checkout; versioned prebuilt release
bundles (the final npm story) ship when the repo goes public — the plumbing
already exists (`packages/atlas-cli`, design:
`docs/plans/2026-07-03-wsb-installer-plan.md`).

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

## npm — lifecycle launcher

```
npm install -g @l2/atlas
atlas install --manifest <release-manifest-url>   # versioned bundle install
atlas update | rollback | uninstall | doctor | versions
```

`@l2/atlas` is a thin launcher that installs/updates/rolls back **versioned
release bundles** under `~/.atlas/versions` with an atomic `current` pointer
— it never builds from source. Until public release bundles are published,
use the one-line bootstrap (source mode) above; `atlas install --from
<bundleDir>` also works against a locally built bundle.

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

## Deferred (documented, not built)

- Desktop app + signed `.exe` setup — after full stability; will wrap the
  same versioned bundles.
- Public release bundle CI (per-platform archives + manifest index) — the
  generator exists (`packages/atlas-cli/src/buildReleaseIndex.js`); needs a
  public artifact host and a release workflow.
