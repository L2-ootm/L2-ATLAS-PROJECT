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

# Regenerate the portable repo shim without embedding a developer's absolute
# path. Runtime commands use this checkout; lifecycle commands always reach the
# npm launcher so `atlas update` never mutates or mistakes the source tree.
$shim = @'
@echo off
setlocal
if /I "%~1"=="install" goto lifecycle
if /I "%~1"=="update" goto lifecycle
if /I "%~1"=="rollback" goto lifecycle
if /I "%~1"=="uninstall" goto lifecycle
if /I "%~1"=="versions" goto lifecycle
set "ATLAS_REPO=%~dp0"
"%ATLAS_REPO%.venv\Scripts\python.exe" -m atlas_runtime.cli.main %*
exit /b %errorlevel%
:lifecycle
for /f "delims=" %%I in ('npm.cmd prefix --global 2^>nul') do set "ATLAS_NPM_PREFIX=%%I"
if not defined ATLAS_NPM_PREFIX exit /b 1
if not exist "%ATLAS_NPM_PREFIX%\atlas.cmd" exit /b 1
call "%ATLAS_NPM_PREFIX%\atlas.cmd" %*
exit /b %errorlevel%
'@
Set-Content -Path (Join-Path $root 'atlas.cmd') -Value $shim -Encoding ascii -NoNewline

# ---------------------------------------------------------------------------
# Core install completes BEFORE any optional sidecar is built.
#
# `atlas db init` used to run last, after the go/cargo/npm/bun builds. With
# $ErrorActionPreference = 'Stop', one failing optional build — a TypeScript
# error in the donor atlas-terminal was the common case — aborted the script
# and left the database uninitialized, so a machine that had *more* toolchains
# installed ended up with a *more* broken install. Ordering the critical path
# first means an optional build can only cost you that optional component.
# ---------------------------------------------------------------------------

# Resolve the console script installed by the editable pip install.
$atlasExe = Join-Path $venv 'Scripts\atlas.exe'

# Bootstrap / migrate the DB (idempotent, non-destructive).
& $atlasExe db init

# Verify the console script resolved inside the venv.
& $atlasExe --help | Select-Object -First 1
Write-Host 'Core install complete (CLI + database).'

# ---------------------------------------------------------------------------
# Optional sidecars — every failure here is a warning, never fatal.
# ---------------------------------------------------------------------------
$script:OptionalWarnings = @()

function Invoke-OptionalStep {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][scriptblock]$Body
    )
    Write-Host $Name
    Push-Location $WorkingDirectory
    try {
        & $Body
    } catch {
        $detail = "$Name failed (non-fatal): $($_.Exception.Message)"
        Write-Host "  [WARN] $detail" -ForegroundColor Yellow
        $script:OptionalWarnings += $detail
    } finally {
        Pop-Location
    }
}

# Build the Go/BubbleTea sidecar into the ATLAS-owned binary directory used by
# the Python launcher. No shell or foundation npm bundle participates in P8.
$atlasHome = if ($env:ATLAS_HOME) { $env:ATLAS_HOME } else { Join-Path $HOME '.atlas' }
$tui = Join-Path $root 'services/atlas-tui'
$tuiBinDir = Join-Path $atlasHome 'bin'
$tuiBinary = Join-Path $tuiBinDir 'atlas-tui.exe'
if (Get-Command go -ErrorAction SilentlyContinue) {
    New-Item -ItemType Directory -Force -Path $tuiBinDir | Out-Null
    Invoke-OptionalStep "Building atlas-tui -> $tuiBinary" $tui {
        & go build -trimpath -ldflags "-s -w" -o $tuiBinary .
        if ($LASTEXITCODE -ne 0) { throw "go build (atlas-tui) exit $LASTEXITCODE" }
    }
} else {
    Write-Host "Skipping atlas-tui build: Go not found. Install Go 1.26+ and rerun, or set ATLAS_TUI_BIN to a prebuilt binary."
}

# Build the Rust gateway binary (release). Skipped gracefully when cargo is
# absent — `atlas up` will report "gateway: down" via `atlas doctor` until a
# binary is built, but the rest of the install still completes.
if (Get-Command cargo -ErrorAction SilentlyContinue) {
    Invoke-OptionalStep 'Building atlas-gateway (cargo build --release)' (Join-Path $root 'native/atlas-core-rs') {
        cargo build --release -p atlas-gateway
        if ($LASTEXITCODE -ne 0) { throw "cargo build exit $LASTEXITCODE" }
    }
} else {
    Write-Host "Skipping gateway build (cargo not found); install Rust or set up the gateway manually."
}

# Build the React cockpit (production bundle consumed by `npm run preview` /
# cockpit_control.start()). Skipped gracefully when npm is absent.
$cockpit = Join-Path $root 'services/web-ui-react'
if ((Get-Command npm -ErrorAction SilentlyContinue) -and (Test-Path $cockpit)) {
    Invoke-OptionalStep "Building the cockpit ($cockpit)" $cockpit {
        npm install --silent
        if ($LASTEXITCODE -ne 0) { throw "npm install (cockpit) exit $LASTEXITCODE" }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build (cockpit) exit $LASTEXITCODE" }
    }
} else {
    Write-Host "Skipping cockpit build (npm not found)."
}

# Install + typecheck atlas-terminal (donor-based TUI surface, not yet the
# default `atlas tui` entry — see STAGE 3 retirement gate). Skipped gracefully
# when bun is absent, and a typecheck failure now only disables this surface.
$atlasTerminal = Join-Path $root 'services/atlas-terminal'
if ((Get-Command bun -ErrorAction SilentlyContinue) -and (Test-Path $atlasTerminal)) {
    Invoke-OptionalStep "Installing + typechecking atlas-terminal ($atlasTerminal)" $atlasTerminal {
        bun install --silent
        if ($LASTEXITCODE -ne 0) { throw "bun install (atlas-terminal) exit $LASTEXITCODE" }
        bun run typecheck
        if ($LASTEXITCODE -ne 0) { throw "bun run typecheck (atlas-terminal) exit $LASTEXITCODE" }
    }
} else {
    Write-Host "Skipping atlas-terminal build (bun not found)."
}

Write-Host "`nDone. The 'atlas' console script lives at $atlasExe."
Write-Host "Use '.\atlas <cmd>' from the repo root, or add '$venv\Scripts' to PATH for a bare 'atlas'."
if ($script:OptionalWarnings.Count -gt 0) {
    Write-Host "`n$($script:OptionalWarnings.Count) optional component(s) did not build:" -ForegroundColor Yellow
    foreach ($warning in $script:OptionalWarnings) {
        Write-Host "  - $warning" -ForegroundColor Yellow
    }
    Write-Host "Run 'atlas doctor' to see which surfaces are affected." -ForegroundColor Yellow
}

# Exit explicitly: a soft-failed optional build leaves its non-zero exit code in
# $LASTEXITCODE, which would otherwise become this script's exit status and tell
# every caller the install failed. Reaching here means the core install worked.
exit 0
