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

# Target a dedicated repo venv, never the ambient `python` on PATH — on a
# foundation-only machine that PATH python is the pip-less Hermes venv, which
# cannot pip-install. Create the venv if missing using the py launcher.
$venv   = Join-Path $root '.venv'
$venvPy = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating venv at $venv"
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv $venv }
    else { & python -m venv $venv }
}
& $venvPy -m pip install --upgrade pip | Out-Null
Write-Host "Repo:   $root"
Write-Host "Python: $venvPy"

# Editable installs (order matters: core is a dependency of the runtimes).
& $venvPy -m pip install -e "$root/packages/atlas-core"
$runtimeSpec = if ($Claude) { "$root/services/agent-runtime[claude]" } else { "$root/services/agent-runtime" }
& $venvPy -m pip install -e $runtimeSpec
& $venvPy -m pip install -e "$root/services/wiki-runtime"

# Regenerate the portable `atlas` shim at repo root, pointing at THIS repo's
# venv (so `.\atlas ...` works from the repo without touching PATH). The gateway
# self-resolves its own ATLAS_CLI from the venv interpreter (gateway_control).
$atlasExe = Join-Path $venv 'Scripts\atlas.exe'
$shim = "@echo off`r`n`"$venvPy`" -m atlas_runtime.cli.main %*`r`n"
Set-Content -Path (Join-Path $root 'atlas.cmd') -Value $shim -Encoding ascii -NoNewline

# Build the terminal UI bundle so `atlas tui` runs without a first-run build.
# Skipped gracefully when node/npm are absent (the launcher still builds on
# first run). dist/ and node_modules/ are gitignored, machine-local artifacts.
$tui = Join-Path $root 'foundation/atlas-hermes/ui-tui'
if ((Get-Command npm -ErrorAction SilentlyContinue) -and (Test-Path $tui)) {
    Write-Host "Building the terminal UI ($tui)"
    Push-Location $tui
    try { npm install --silent; npm run build } finally { Pop-Location }
} else {
    Write-Host "Skipping TUI build (npm not found); 'atlas tui' will build on first run."
}

# Build the Rust gateway binary (release). Skipped gracefully when cargo is
# absent — `atlas up` will report "gateway: down" via `atlas doctor` until a
# binary is built, but the rest of the install still completes.
if (Get-Command cargo -ErrorAction SilentlyContinue) {
    Write-Host "Building atlas-gateway (cargo build --release)"
    Push-Location (Join-Path $root 'native/atlas-core-rs')
    try { cargo build --release -p atlas-gateway } finally { Pop-Location }
} else {
    Write-Host "Skipping gateway build (cargo not found); install Rust or set up the gateway manually."
}

# Build the React cockpit (production bundle consumed by `npm run preview` /
# cockpit_control.start()). Skipped gracefully when npm is absent.
$cockpit = Join-Path $root 'services/web-ui-react'
if ((Get-Command npm -ErrorAction SilentlyContinue) -and (Test-Path $cockpit)) {
    Write-Host "Building the cockpit ($cockpit)"
    Push-Location $cockpit
    try { npm install --silent; npm run build } finally { Pop-Location }
} else {
    Write-Host "Skipping cockpit build (npm not found)."
}

# Bootstrap / migrate the DB (idempotent, non-destructive).
& $atlasExe db init

# Verify the console script resolved inside the venv.
& $atlasExe --help | Select-Object -First 1
Write-Host "`nDone. The 'atlas' console script lives at $atlasExe."
Write-Host "Use '.\atlas <cmd>' from the repo root, or add '$venv\Scripts' to PATH for a bare 'atlas'."
