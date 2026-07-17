# ATLAS one-line bootstrap for Windows (PowerShell).
#
#   irm https://raw.githubusercontent.com/L2-ootm/L2-ATLAS-PROJECT/main/install/install.ps1 | iex
#
# What it does:
#   1. Verifies prerequisites (git, Node.js >= 20, Python >= 3.11) and offers
#      winget installs for anything missing.
#   2. RELEASE mode (when a release manifest URL is provided/published):
#      npm install -g @l2/atlas, then `atlas install --manifest <url>` —
#      versioned prebuilt bundles, update/rollback/uninstall included.
#   3. SOURCE mode (default while ATLAS is pre-release): clones the repo and
#      runs scripts/install-atlas-cli.ps1 (editable install + DB bootstrap).
#
# Idempotent: re-running updates an existing source checkout in place.
# Design: docs/plans/2026-07-03-wsb-installer-plan.md (npm wrapper + bundles).

[CmdletBinding()]
param(
    # Where the source checkout lands in SOURCE mode.
    [string]$InstallDir = "$env:USERPROFILE\atlas",
    # Repo to clone in SOURCE mode.
    [string]$Repo = 'https://github.com/L2-ootm/L2-ATLAS-PROJECT.git',
    # Release manifest URL — switches to RELEASE mode (npm lifecycle launcher).
    [string]$ReleaseManifest = $env:ATLAS_RELEASE_MANIFEST,
    # Also install the optional Claude Code runtime extra (SOURCE mode).
    [switch]$Claude
)

$ErrorActionPreference = 'Stop'

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Test-Command([string]$name) {
    return $null -ne (Get-Command $name -ErrorAction SilentlyContinue)
}

function Ensure-Tool {
    param(
        [string]$Command,
        [string]$Display,
        [string]$WingetId
    )
    if (Test-Command $Command) { return $true }
    Write-Host "$Display is required but was not found." -ForegroundColor Yellow
    if (Test-Command 'winget') {
        $answer = Read-Host "Install $Display via winget now? [Y/n]"
        if ($answer -eq '' -or $answer -match '^[Yy]') {
            winget install --id $WingetId --accept-source-agreements --accept-package-agreements
            # refresh PATH for this session
            $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                        [Environment]::GetEnvironmentVariable('Path', 'User')
            if (Test-Command $Command) { return $true }
        }
    }
    Write-Host "Install $Display manually, then re-run this script." -ForegroundColor Red
    return $false
}

function Assert-NodeVersion {
    $raw = (node --version) -replace '^v', ''
    $major = [int]($raw.Split('.')[0])
    if ($major -lt 20) {
        throw @"
Node.js 20 or newer is required, but v$raw was detected.

Update Node.js (winget install OpenJS.NodeJS.LTS), reopen PowerShell, and rerun:
irm https://raw.githubusercontent.com/L2-ootm/L2-ATLAS-PROJECT/main/install/install.ps1 | iex
"@
    }
}

function Assert-PythonVersion {
    # Prefer the py launcher (the source installer uses it too).
    $probe = if (Test-Command 'py') { 'py -3' } elseif (Test-Command 'python') { 'python' } else { $null }
    if (-not $probe) { throw 'Python 3.11+ required. Install it (winget install Python.Python.3.12) and re-run.' }
    $version = Invoke-Expression "$probe -c `"import sys; print('.'.join(map(str, sys.version_info[:2])))`""
    if ([version]$version -lt [version]'3.11') {
        throw @"
Python 3.11 or newer is required, but $version was detected.

Install a current Python (winget install Python.Python.3.12), reopen
PowerShell, and rerun this installer.
"@
    }
}

# Optional-but-recommended toolchains. Missing ones don't abort the install —
# the repo installer skips those builds gracefully — but each absence disables
# a concrete surface, so say exactly which one.
function Ensure-OptionalTool {
    param(
        [string]$Command,
        [string]$Display,
        [string]$WingetId,
        [string]$Consequence
    )
    if (Test-Command $Command) { return }
    Write-Host "$Display was not found. $Consequence" -ForegroundColor Yellow
    if (Test-Command 'winget') {
        $answer = Read-Host "Install $Display via winget now? [Y/n]"
        if ($answer -eq '' -or $answer -match '^[Yy]') {
            winget install --id $WingetId --accept-source-agreements --accept-package-agreements
            $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                        [Environment]::GetEnvironmentVariable('Path', 'User')
        }
    }
    if (-not (Test-Command $Command)) {
        Write-Host "Continuing without $Display — rerun this installer after installing it to enable the missing surface." -ForegroundColor Yellow
    }
}

# Add a directory to the current session PATH and the persistent user PATH
# (no duplicates), so `atlas` resolves in this shell and every new one.
function Add-ToPath {
    param([string]$Directory)
    if ([string]::IsNullOrWhiteSpace($Directory) -or -not (Test-Path $Directory)) { return }
    $normalized = $Directory.Trim().TrimEnd('\')
    $sessionParts = @($env:Path -split ';' | ForEach-Object { $_.Trim().TrimEnd('\') } | Where-Object { $_ })
    if ($sessionParts -notcontains $normalized) { $env:Path = "$env:Path;$Directory" }
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $userParts = @($userPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $userNormalized = @($userParts | ForEach-Object { $_.Trim().TrimEnd('\') })
    if ($userNormalized -notcontains $normalized) {
        [Environment]::SetEnvironmentVariable('Path', ((@($userParts) + $Directory) -join ';'), 'User')
    }
}

Write-Host ''
Write-Host '  A T L A S  —  operator install' -ForegroundColor White
Write-Host '  L2 Systems' -ForegroundColor DarkGray
Write-Host ''

# ── Prerequisites ────────────────────────────────────────────────────────────
Write-Step 'Checking prerequisites'
if (-not (Ensure-Tool -Command 'git'  -Display 'Git'     -WingetId 'Git.Git')) { exit 1 }
if (-not (Ensure-Tool -Command 'node' -Display 'Node.js' -WingetId 'OpenJS.NodeJS.LTS')) { exit 1 }
if (-not (Test-Command 'py') -and -not (Test-Command 'python')) {
    if (-not (Ensure-Tool -Command 'python' -Display 'Python 3.12' -WingetId 'Python.Python.3.12')) { exit 1 }
}
Assert-NodeVersion
Assert-PythonVersion
Write-Host '    git / node / python OK'

# Recommended toolchains — each missing one disables a named surface.
Ensure-OptionalTool -Command 'cargo' -Display 'Rust (cargo)' -WingetId 'Rustlang.Rustup' `
    -Consequence 'Without it the gateway binary is not built, so `atlas up` cannot start the gateway or cockpit.'
Ensure-OptionalTool -Command 'bun' -Display 'Bun' -WingetId 'Oven-sh.Bun' `
    -Consequence 'Without it the terminal UI is not installed, so the bare `atlas` command has no interactive surface.'

# ── RELEASE mode ─────────────────────────────────────────────────────────────
if ($ReleaseManifest) {
    Write-Step "Installing the @l2/atlas lifecycle launcher (release mode)"
    npm install -g @l2/atlas
    if ($LASTEXITCODE -ne 0) { throw 'npm install -g @l2/atlas failed' }
    Write-Step "Installing ATLAS from release manifest"
    atlas install --manifest $ReleaseManifest
    if ($LASTEXITCODE -ne 0) { throw 'atlas install failed' }
    Write-Step 'Done — try: atlas doctor, then atlas up'
    exit 0
}

# ── SOURCE mode (default while pre-release) ──────────────────────────────────
Write-Step "Source install into $InstallDir"
if (Test-Path (Join-Path $InstallDir '.git')) {
    Write-Host '    existing checkout found — updating'
    git -C $InstallDir pull --ff-only
    if ($LASTEXITCODE -ne 0) { throw 'git pull failed (local changes?). Resolve and re-run.' }
} else {
    git clone $Repo $InstallDir
    if ($LASTEXITCODE -ne 0) { throw 'git clone failed' }
}

Write-Step 'Running the repo installer (venv + editable install + DB migrations)'
$installer = Join-Path $InstallDir 'scripts\install-atlas-cli.ps1'
if (-not (Test-Path $installer)) { throw "installer not found: $installer" }
if ($Claude) { & $installer -Claude } else { & $installer }

# ── PATH + validation ────────────────────────────────────────────────────────
# The editable install put the `atlas` console script in the repo venv; expose
# it on PATH (session + user) so a bare `atlas` works in this and future shells.
Write-Step 'Validating the install'
$venvScripts = Join-Path $InstallDir '.venv\Scripts'
Add-ToPath -Directory $venvScripts
$atlasExe = Join-Path $venvScripts 'atlas.exe'
if (-not (Test-Path $atlasExe)) {
    throw @"
The install completed but the atlas CLI was not found at:
$atlasExe

Rerun this installer, or run scripts\install-atlas-cli.ps1 from $InstallDir
and check its output for the failing step.
"@
}
& $atlasExe --help | Select-Object -First 1 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "'atlas --help' failed with exit code $LASTEXITCODE." }
Write-Host "    atlas resolved: $atlasExe"

Write-Host ''
Write-Step 'Done'
Write-Host '    atlas doctor   # verify the install'
Write-Host '    atlas up       # start gateway + cockpit (+ sidecars)'
Write-Host '    atlas          # launch the terminal UI'
Write-Host ''
Write-Host '    (PATH was updated — new terminals pick it up automatically;'
Write-Host '     this session already has it.)'
Write-Host ''
