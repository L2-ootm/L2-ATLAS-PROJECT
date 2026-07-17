# ATLAS one-line bootstrap for Windows (PowerShell).
#
#   irm https://raw.githubusercontent.com/L2-ootm/L2-ATLAS-PROJECT/main/install/install.ps1 | iex
#
# What it does:
#   1. RELEASE mode (default): ensures Node.js >= 20, installs the public npm
#      launcher, and materializes the self-contained Windows runtime. Python,
#      Rust, Go, Git, and build tools are not required.
#   2. SOURCE mode (-Source): verifies the developer toolchain, clones the repo,
#      and runs scripts/install-atlas-cli.ps1.
#
# Idempotent: re-running updates an existing source checkout in place.
# Design: docs/plans/2026-07-03-wsb-installer-plan.md (npm wrapper + bundles).

[CmdletBinding()]
param(
    # Explicitly choose the developer/source workflow. Release mode is default.
    [switch]$Source,
    # Where the source checkout lands in SOURCE mode.
    [string]$InstallDir = "$env:USERPROFILE\atlas",
    # Repo to clone in SOURCE mode.
    [string]$Repo = 'https://github.com/L2-ootm/L2-ATLAS-PROJECT.git',
    # Optional advanced release manifest override.
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
        throw "Node.js >= 20 required (found v$raw). Update Node and re-run."
    }
}

function Resolve-NpmCommand {
    $command = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
    if (-not $command) { $command = Get-Command 'npm' -ErrorAction SilentlyContinue }
    if (-not $command) { throw 'npm is unavailable after installing Node.js.' }
    return $command.Source
}

function Ensure-ReleaseNode {
    $needsInstall = -not (Test-Command 'node')
    if (-not $needsInstall) {
        $major = [int](((node --version) -replace '^v', '').Split('.')[0])
        $needsInstall = $major -lt 20
    }
    if ($needsInstall) {
        if (-not (Test-Command 'winget')) {
            throw 'Node.js 20+ is required. Install the current Node.js LTS release and re-run.'
        }
        Write-Step 'Installing current Node.js LTS (includes npm)'
        winget install --id OpenJS.NodeJS.LTS --source winget --silent `
            --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -ne 0) {
            winget upgrade --id OpenJS.NodeJS.LTS --source winget --silent `
                --accept-source-agreements --accept-package-agreements
        }
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                    [Environment]::GetEnvironmentVariable('Path', 'User')
    }
    if (-not (Test-Command 'node')) { throw 'Node.js installation completed but node is not available in this terminal.' }
    Assert-NodeVersion
}

function Assert-PythonVersion {
    # Prefer the py launcher (the source installer uses it too).
    $probe = if (Test-Command 'py') { 'py -3' } elseif (Test-Command 'python') { 'python' } else { $null }
    if (-not $probe) { throw 'Python 3.11+ required. Install it (winget install Python.Python.3.12) and re-run.' }
    $version = Invoke-Expression "$probe -c `"import sys; print('.'.join(map(str, sys.version_info[:2])))`""
    if ([version]$version -lt [version]'3.11') {
        throw "Python >= 3.11 required (found $version)."
    }
}

Write-Host ''
Write-Host '  A T L A S  —  operator install' -ForegroundColor White
Write-Host '  L2 Systems' -ForegroundColor DarkGray
Write-Host ''

# ── RELEASE mode (default) ───────────────────────────────────────────────────
if (-not $Source) {
    Write-Step 'Checking the only external prerequisite: Node.js 20+'
    Ensure-ReleaseNode
    $npm = Resolve-NpmCommand

    Write-Step 'Installing the latest @systemsl2/atlas lifecycle launcher'
    & $npm install --global '@systemsl2/atlas@latest'
    if ($LASTEXITCODE -ne 0) { throw 'npm install --global @systemsl2/atlas@latest failed' }

    $npmPrefix = [string]((& $npm prefix --global | Select-Object -Last 1))
    $launcher = Join-Path $npmPrefix 'atlas.cmd'
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) {
        throw "npm installed ATLAS but the launcher was not found at $launcher"
    }

    Write-Step 'Materializing the verified, self-contained ATLAS runtime'
    if ($ReleaseManifest) { & $launcher install --manifest $ReleaseManifest }
    else { & $launcher install }
    if ($LASTEXITCODE -ne 0) { throw 'atlas install failed' }

    # Older source installers placed a Python-forwarding shim before npm on
    # PATH. Replace only that ATLAS-owned compatibility shim so `atlas update`
    # always reaches the lifecycle launcher from every directory.
    $legacyShim = Join-Path $env:LOCALAPPDATA 'atlas\bin\atlas.cmd'
    if (Test-Path -LiteralPath $legacyShim) {
        $compat = "@echo off`r`ncall `"$launcher`" %*`r`nexit /b %errorlevel%`r`n"
        Set-Content -LiteralPath $legacyShim -Value $compat -Encoding ascii -NoNewline
    }

    & $launcher doctor --install-only
    if ($LASTEXITCODE -ne 0) { throw 'ATLAS package integrity verification failed' }
    Write-Step 'Done — run: atlas up, then atlas doctor'
    exit 0
}

# ── SOURCE mode (explicit) ───────────────────────────────────────────────────
Write-Step 'Checking source-development prerequisites'
if (-not (Ensure-Tool -Command 'git'  -Display 'Git'     -WingetId 'Git.Git')) { exit 1 }
if (-not (Ensure-Tool -Command 'node' -Display 'Node.js' -WingetId 'OpenJS.NodeJS.LTS')) { exit 1 }
Assert-NodeVersion
Assert-PythonVersion
Write-Host '    git / node / python OK'

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

Write-Host ''
Write-Step 'Done'
Write-Host '    atlas doctor   # verify the install'
Write-Host '    atlas up       # start gateway + cockpit (+ sidecars)'
Write-Host '    atlas          # launch the terminal UI'
Write-Host ''
