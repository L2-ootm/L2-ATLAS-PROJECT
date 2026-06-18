# Install the ATLAS `atlas` CLI onto PATH (editable) and bootstrap the DB.
#
# After this runs:
#   - `atlas` is a console script on PATH (created by the editable install of
#     services/agent-runtime), so the gateway/cockpit can dispatch writes and
#     `atlas db init` / `atlas gateway start` work from any terminal.
#   - ~/.atlas/atlas.db has every migration applied (idempotent, non-destructive).
#
# Usage (from repo root):  ./scripts/install-atlas-cli.ps1
# Optional Claude runtime: pass -Claude to also install the claude_code extra.

[CmdletBinding()]
param([switch]$Claude)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$py = (Get-Command python).Source
Write-Host "Repo:   $root"
Write-Host "Python: $py"

# Editable installs (order matters: core is a dependency of the runtimes).
& $py -m pip install -e "$root/packages/atlas-core"
$runtimeSpec = if ($Claude) { "$root/services/agent-runtime[claude]" } else { "$root/services/agent-runtime" }
& $py -m pip install -e $runtimeSpec
& $py -m pip install -e "$root/services/wiki-runtime"

# Bootstrap / migrate the DB (idempotent, non-destructive).
& atlas db init

# Verify the console script resolved on PATH.
& atlas --help | Select-Object -First 1
Write-Host "`nDone. 'atlas' is on PATH and the DB is bootstrapped. Restart open shells if needed."
