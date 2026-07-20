# ATLAS one-line bootstrap for Windows (PowerShell).
#
#   irm https://raw.githubusercontent.com/L2-ootm/L2-ATLAS-PROJECT/main/install/install.ps1 -OutFile $env:TEMP\atlas-install.ps1; powershell -ExecutionPolicy Bypass -File $env:TEMP\atlas-install.ps1
#
# (irm | iex does not work because the param() block is only valid in script
#  files, not inside Invoke-Expression strings.)
#
# What it does:
#   1. RELEASE mode (default): ensures Node.js >= 20, installs the public npm
#      launcher, and materializes the self-contained Windows runtime. Python,
#      Rust, Go, Git, and build tools are not required.
#   2. SOURCE mode (-Source): verifies the developer toolchain, clones the repo,
#      and runs scripts/install-atlas-cli.ps1.
#
# Idempotent: re-running updates an existing source checkout in place.
# User content (config, DB, skills, wiki) is preserved across updates.
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
    [switch]$Claude,
    # Force update even if already on latest version.
    [switch]$Force,
    # Skip user content preservation (destructive reinstall).
    [switch]$NoPreserve
)

$ErrorActionPreference = 'Stop'

# ── ATLAS home directory ──────────────────────────────────────────────────────
$AtlasHome = "$env:LOCALAPPDATA\atlas"
$VersionsDir = Join-Path $AtlasHome 'versions'
$CurrentLink = Join-Path $AtlasHome 'current'
$ConfigDir = Join-Path $AtlasHome 'config'
$DataDir = Join-Path $AtlasHome 'data'
$SkillsDir = Join-Path $AtlasHome 'skills'
$InstallFile = Join-Path $AtlasHome 'install.json'
$RtkVersion = '0.43.0'
$RtkBinDir = Join-Path $AtlasHome 'rtk'

function Write-Step([string]$msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Write-Ok([string]$msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Write-Warn([string]$msg) {
    Write-Host "  [WARN] $msg" -ForegroundColor Yellow
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

# ── User content preservation ──────────────────────────────────────────────────
function Preserve-UserContent {
    param([string]$FromVersion, [string]$ToVersion)

    if ($NoPreserve) {
        Write-Warn "Skipping user content preservation (-NoPreserve)"
        return
    }

    $fromDir = Join-Path $VersionsDir $FromVersion
    if (-not (Test-Path $fromDir)) { return }

    Write-Step "Preserving user content from $FromVersion -> $ToVersion"

    # User content to preserve (outside versions directory)
    $preservePaths = @(
        @{ Source = $ConfigDir; Dest = $ConfigDir; Name = 'config' },
        @{ Source = $DataDir; Dest = $DataDir; Name = 'data (DB, wiki, memory)' },
        @{ Source = $SkillsDir; Dest = $SkillsDir; Name = 'user skills' }
    )

    foreach ($item in $preservePaths) {
        if (Test-Path $item.Source) {
            Write-Ok "$($item.Name) preserved at $($item.Dest)"
        }
    }

    # Backup install metadata
    if (Test-Path $InstallFile) {
        $backupFile = Join-Path $AtlasHome "install-backup-$FromVersion.json"
        Copy-Item -LiteralPath $InstallFile -Destination $backupFile -Force
        Write-Ok "Install metadata backed up"
    }
}

# ── DB migration runner ────────────────────────────────────────────────────────
function Run-DbMigrations {
    param([string]$Version)

    $dbFile = Join-Path $DataDir 'atlas.db'
    if (-not (Test-Path $dbFile)) { return }

    $migrationsDir = Join-Path $VersionsDir "$Version\infra\migrations"
    if (-not (Test-Path $migrationsDir)) { return }

    Write-Step 'Running database migrations'

    # Find the atlas CLI in the new version
    $atlasCmd = Join-Path $VersionsDir "$Version\bin\atlas.js"
    if (-not (Test-Path $atlasCmd)) { return }

    try {
        & node $atlasCmd db migrate 2>&1 | ForEach-Object { Write-Host "  $_" }
        Write-Ok 'Database migrations complete'
    } catch {
        Write-Warn "DB migration failed (non-fatal): $_"
    }
}

# ── RTK (Rust Token Killer) — optional but recommended ─────────────────────────
function Ensure-Rtk {
    if (Test-Command 'rtk') {
        Write-Ok "RTK $((& rtk --version 2>$null | Select-Object -First 1)) found"
        return
    }

    $rtkExe = Join-Path $RtkBinDir 'rtk.exe'
    if (Test-Path -LiteralPath $rtkExe -PathType Leaf) {
        $env:Path = "$RtkBinDir;$env:Path"
        Write-Ok "RTK found at $RtkBinDir"
        return
    }

    Write-Step "Installing RTK v$RtkVersion (60-90% token savings on shell commands)"

    $rtkTarget = 'x86_64-pc-windows-msvc'
    $rtkUrl = "https://github.com/rtk-ai/rtk/releases/download/v$RtkVersion/rtk-$rtkTarget.zip"
    $tmpDir = Join-Path $env:TEMP "atlas-rtk-$(Get-Random)"

    try {
        New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
        Write-Step "Downloading RTK from $rtkUrl"
        Invoke-WebRequest -Uri $rtkUrl -OutFile "$tmpDir\rtk.zip" -UseBasicParsing -ErrorAction Stop

        Write-Step "Extracting RTK"
        Expand-Archive -Path "$tmpDir\rtk.zip" -DestinationPath $tmpDir -Force

        New-Item -ItemType Directory -Path $RtkBinDir -Force | Out-Null
        $rtkExtracted = Get-ChildItem -Path $tmpDir -Filter 'rtk.exe' -Recurse | Select-Object -First 1
        if ($rtkExtracted) {
            Copy-Item -LiteralPath $rtkExtracted.FullName -Destination $rtkExe -Force
            $env:Path = "$RtkBinDir;$env:Path"
            Write-Ok "RTK installed to $rtkBinDir"
        } else {
            Write-Warn "RTK binary not found in archive — RTK will not be installed (optional)"
        }
    } catch {
        Write-Warn "RTK installation failed (non-fatal): $_"
    } finally {
        if (Test-Path $tmpDir) { Remove-Item -Path $tmpDir -Recurse -Force -ErrorAction SilentlyContinue }
    }
}

# ── Get current version ────────────────────────────────────────────────────────
function Get-CurrentVersion {
    if (-not (Test-Path $InstallFile)) { return $null }
    try {
        $state = Get-Content -LiteralPath $InstallFile -Raw | ConvertFrom-Json
        return $state.installedVersion
    } catch {
        return $null
    }
}

# ── Check for updates ──────────────────────────────────────────────────────────
function Get-LatestVersion {
    try {
        $npm = Resolve-NpmCommand
        $version = & $npm view @systemsl2/atlas version 2>&1
        return $version.Trim()
    } catch {
        return $null
    }
}

# ── Main banner ────────────────────────────────────────────────────────────────
Write-Host ''
Write-Host '  A T L A S  —  operator install' -ForegroundColor White
Write-Host '  L2 Systems' -ForegroundColor DarkGray
Write-Host ''

# ── Check existing installation ────────────────────────────────────────────────
$currentVersion = Get-CurrentVersion
$isUpdate = $null -ne $currentVersion

if ($isUpdate) {
    Write-Host "  Current installation: $currentVersion" -ForegroundColor DarkGray

    # Check if update is needed
    $latestVersion = Get-LatestVersion
    if ($latestVersion -and $latestVersion -eq $currentVersion -and -not $Force) {
        Write-Host ''
        Write-Host "  Already on latest version ($currentVersion)" -ForegroundColor Green
        Write-Host '  Run with -Force to reinstall, or: atlas update' -ForegroundColor DarkGray
        Write-Host ''
        exit 0
    }
    if ($latestVersion) {
        Write-Host "  Available update: $latestVersion" -ForegroundColor Yellow
    }
}

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

    # Preserve user content before update
    if ($isUpdate) {
        Preserve-UserContent -FromVersion $currentVersion -ToVersion 'latest'
    }

    Write-Step 'Materializing the verified, self-contained ATLAS runtime'
    if ($ReleaseManifest) { & $launcher install --manifest $ReleaseManifest }
    else { & $launcher install }
    if ($LASTEXITCODE -ne 0) { throw 'atlas install failed' }

    # Run DB migrations
    $newVersion = Get-CurrentVersion
    if ($newVersion -and $isUpdate) {
        Run-DbMigrations -Version $newVersion
    }

    # Older source installers placed a Python-forwarding shim before npm on
    # PATH. Replace only that ATLAS-owned compatibility shim so `atlas update`
    # always reaches the lifecycle launcher from every directory.
    $legacyShim = Join-Path $env:LOCALAPPDATA 'atlas\bin\atlas.cmd'
    if (Test-Path -LiteralPath $legacyShim) {
        $compat = "@echo off`r`ncall `"$launcher`" %*`r`nexit /b %errorlevel%`r`n"
        Set-Content -LiteralPath $legacyShim -Value $compat -Encoding ascii -NoNewline
    }

    Write-Step 'Installing RTK (optional, 60-90% token savings)'
    Ensure-Rtk

    & $launcher doctor --install-only
    if ($LASTEXITCODE -ne 0) { throw 'ATLAS package integrity verification failed' }

    Write-Host ''
    if ($isUpdate) {
        Write-Host "  Updated: $currentVersion -> $newVersion" -ForegroundColor Green
    } else {
        Write-Host "  Installed: $newVersion" -ForegroundColor Green
    }
    Write-Host ''
    Write-Host '  Next steps:' -ForegroundColor Yellow
    Write-Host '    atlas up       # start gateway + cockpit (+ sidecars)'
    Write-Host '    atlas doctor   # verify the installation'
    Write-Host '    atlas          # launch the terminal UI'
    Write-Host ''
    exit 0
}

# ── SOURCE mode (explicit) ───────────────────────────────────────────────────
Write-Step 'Checking source-development prerequisites'
if (-not (Ensure-Tool -Command 'git'  -Display 'Git'     -WingetId 'Git.Git')) { exit 1 }
if (-not (Ensure-Tool -Command 'node' -Display 'Node.js' -WingetId 'OpenJS.NodeJS.LTS')) { exit 1 }
Assert-NodeVersion
Assert-PythonVersion
Write-Host '    git / node / python OK'

# Preserve user content before update
if ($isUpdate) {
    Preserve-UserContent -FromVersion $currentVersion -ToVersion 'source'
}

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
