# ATLAS one-line bootstrap for Windows (PowerShell).
#
#   $f="$env:TEMP\atlas-install.ps1"; (irm https://raw.githubusercontent.com/L2-ootm/L2-ATLAS-PROJECT/main/install/install.ps1) | Set-Content -Path $f -Encoding UTF8; powershell -ExecutionPolicy Bypass -File $f
#
# (irm | iex does not work because the param() block is only valid in script
#  files, not inside Invoke-Expression strings.  irm -OutFile can also save
#  with the wrong encoding on PS 5.1; Set-Content -Encoding UTF8 avoids this.)
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

# ── ATLAS install root ────────────────────────────────────────────────────────
# ATLAS_INSTALL_ROOT overrides the application root, exactly as
# packages/atlas-cli/src/paths.js:atlasInstallRoot(), install/install.sh's
# atlas_install_root() and docs/operations/INSTALL.md all define it. This script
# used to hardcode %LOCALAPPDATA%\atlas: with the variable set, it read
# install.json from the wrong root (so every run looked like a fresh install),
# cleaned the wrong versions/ tree, and wrote `current`/install.json where the
# npm launcher would never look — then aborted at the final `doctor` because the
# launcher, which DOES honor the variable, saw nothing installed.
# NOTE: this is the INSTALL root (immutable releases + lifecycle metadata), not
# ATLAS_HOME (the operator's state: atlas.db, config.yaml, auth.json, wiki/).
# The two are deliberately different trees; nothing here ever writes to state.
$InstallRoot = if ($env:ATLAS_INSTALL_ROOT) {
    [IO.Path]::GetFullPath($env:ATLAS_INSTALL_ROOT)
} else {
    "$env:LOCALAPPDATA\atlas"
}
$VersionsDir = Join-Path $InstallRoot 'versions'
$CurrentLink = Join-Path $InstallRoot 'current'
$ConfigDir = Join-Path $InstallRoot 'config'
$DataDir = Join-Path $InstallRoot 'data'
$SkillsDir = Join-Path $InstallRoot 'skills'
$InstallFile = Join-Path $InstallRoot 'install.json'
$RtkVersion = '0.43.0'
$RtkBinDir = Join-Path $InstallRoot 'rtk'
# Same suffix packages/atlas-cli/src/commands.js uses (STAGING_SUFFIX): a name
# that can never collide with a semver directory, and that listVersions/
# `atlas versions repair` already know to treat as reclaimable scratch.
$StagingSuffix = '.atlas-staging'

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
        $backupFile = Join-Path $InstallRoot "install-backup-$FromVersion.json"
        Copy-Item -LiteralPath $InstallFile -Destination $backupFile -Force
        Write-Ok "Install metadata backed up"
    }
}

# ── DB migration runner ────────────────────────────────────────────────────────
# Run-DbMigrations was DELETED here rather than repaired. It stacked three
# independent defects and could not report a true result under any of them:
#   1. it guarded on $DataDir\atlas.db — %LOCALAPPDATA%\atlas\data\atlas.db, a
#      path ATLAS never creates. The database lives at $ATLAS_HOME/atlas.db
#      (services/agent-runtime/atlas_runtime/db.py), so the guard returned early
#      on every real machine and the function was dead code;
#   2. it invoked `db migrate`, which does not exist — the runtime CLI registers
#      only `db init` and `db status`;
#   3. its catch{} could never fire, because a native non-zero exit does not
#      throw in PowerShell. Typer's usage error would be echoed and then
#      "[OK] Database migrations complete" printed on top of it.
# Migrations are already owned by the Node lifecycle path: install/update call
# runMigrations() (packages/atlas-cli/src/commands.js), which resolves the
# runtime entrypoint of the version just materialized, shells out to `db init`,
# and returns a structured result. The one gap that left is the GitHub-release
# fallback below, which never goes through the Node CLI — Invoke-DbInit covers
# exactly that, with a real exit-code check instead of an unreachable catch.

function Invoke-DbInit {
    param([string]$Launcher)

    Write-Step 'Applying database migrations (atlas db init)'
    & $Launcher db init 2>&1 | ForEach-Object { Write-Host "  $_" }
    if ($LASTEXITCODE -ne 0) {
        # Non-fatal: the runtime is installed and usable, and `atlas doctor`
        # surfaces schema problems. Never print success on a non-zero exit.
        Write-Warn "atlas db init exited $LASTEXITCODE — run 'atlas db init' manually to see the error"
        return $false
    }
    Write-Ok 'Database schema up to date'
    return $true
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

# ── Is the recorded version actually on disk and usable? ───────────────────────
# install.json is metadata, not evidence. This script deletes/replaces version
# directories as a normal part of every run, so the window where install.json
# names a version that is no longer materialized is routine — and an
# interrupted run (Ctrl-C, network drop, sleep) makes it permanent. Without this
# check the "Already on latest" fast path below would exit 0 forever against an
# install where `atlas doctor` reports current-version-present: FAIL and every
# other command dies with "ATLAS runtime entrypoint is not installed", because
# bin/atlas.js only re-materializes when the recorded version is FALSY — and a
# stale version string is not falsy. Verified here so re-running the bootstrap
# repairs the install instead of congratulating the operator on it.
function Test-VersionUsable {
    param([string]$Version)

    if (-not $Version) { return $false }
    $verDir = Join-Path $VersionsDir $Version
    if (-not (Test-Path -LiteralPath $verDir -PathType Container)) { return $false }

    $entrypoint = $null
    if (Test-Path $InstallFile) {
        try {
            $entrypoint = (Get-Content -LiteralPath $InstallFile -Raw | ConvertFrom-Json).runtimeEntrypoint
        } catch {
            $entrypoint = $null
        }
    }
    if ($entrypoint) {
        return (Test-Path -LiteralPath (Join-Path $verDir $entrypoint) -PathType Leaf)
    }
    # No recorded entrypoint (pre-manifest install): fall back to the same
    # candidates packages/atlas-cli/src/commands.js probes for.
    foreach ($candidate in @('bin\atlas.exe', 'atlas.exe', 'bin\atlas.js', 'atlas.js')) {
        if (Test-Path -LiteralPath (Join-Path $verDir $candidate) -PathType Leaf) { return $true }
    }
    return $false
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

# ── Runtime download from GitHub releases ─────────────────────────────────────
function Download-RuntimeFromGithub {
    $repo = 'L2-ootm/L2-ATLAS-PROJECT'
    $platformPkg = 'systemsl2-atlas-win32-x64'

    # Find the latest release that has the platform asset
    Write-Step 'Looking up latest release from GitHub'
    try {
        $releases = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases?per_page=10" -UseBasicParsing -ErrorAction Stop
    } catch {
        throw "Cannot reach GitHub releases API: $_"
    }

    $asset = $null; $tagName = $null; $version = $null
    foreach ($rel in $releases) {
        foreach ($a in $rel.assets) {
            # New-style: atlas-{version}-win32-x64.tar.gz
            if ($a.name -match '^atlas-(\d+\.\d+\.\d+)-win32-x64\.tar\.gz$') {
                $asset = $a; $tagName = $rel.tag_name; $version = $Matches[1]; break
            }
        }
        if ($asset) { break }
        foreach ($a in $rel.assets) {
            # Legacy: systemsl2-atlas-win32-x64-{version}.tgz
            if ($a.name -match '^systemsl2-atlas-win32-x64-(\d+\.\d+\.\d+)\.tgz$') {
                $asset = $a; $tagName = $rel.tag_name; $version = $Matches[1]; break
            }
        }
        if ($asset) { break }
    }
    if (-not $asset) { throw "No Windows x64 runtime asset found in any GitHub release" }

    Write-Step "Downloading ATLAS runtime v$version ($($asset.name))"
    $tmpDir = Join-Path $env:TEMP "atlas-runtime-$(Get-Random)"
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
    $archivePath = Join-Path $tmpDir $asset.name
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $archivePath -UseBasicParsing -ErrorAction Stop

    # Stage-then-swap, mirroring stageVersionAtomically in
    # packages/atlas-cli/src/commands.js. Extracting straight into
    # versions/<version>/ (which is what this used to do) meant a killed tar or
    # a truncated download left a half-populated directory AT THE REAL VERSION
    # PATH with no manifest.json. On the next run installBundledPlatform sees a
    # directory that exists, fails verification, and — because install.json
    # still names that version — is not orphaned, so it throws
    # "exists but failed verification" and the install is wedged. Building in a
    # sibling staging directory means a crash can only ever leave scratch behind
    # (`atlas versions repair` reclaims it); the real path appears fully formed
    # or not at all.
    $dest = Join-Path $VersionsDir $version
    $staging = Join-Path $VersionsDir "$version$StagingSuffix"
    if (Test-Path $staging) { Remove-Item -Path $staging -Recurse -Force }
    New-Item -ItemType Directory -Path $staging -Force | Out-Null

    try {
        Write-Step 'Extracting runtime'
        # .tar.gz or .tgz — extract with tar (available on Windows 10+)
        & tar -xzf $archivePath -C $staging 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to extract runtime archive (tar exited $LASTEXITCODE)"
        }

        # If the archive contained a single top-level directory, flatten it
        $children = Get-ChildItem $staging -Directory
        if ($children.Count -eq 1 -and (Test-Path (Join-Path $children[0].FullName 'bin\atlas.js'))) {
            Move-Item -Path "$($children[0].FullName)\*" -Destination $staging -Force
            Remove-Item -Path $children[0].FullName -Recurse -Force
        }

        $entrypoint = 'bin/atlas.js'
        if (-not (Test-Path (Join-Path $staging $entrypoint))) {
            $entrypoint = 'atlas.js'
        }
        if (-not (Test-Path (Join-Path $staging $entrypoint))) {
            throw "Extracted archive contains no runtime entrypoint (bin/atlas.js or atlas.js)"
        }

        # Swap last, once the payload is proven complete. Same-volume Move-Item
        # is the closest PowerShell equivalent of the Node path's rename.
        if (Test-Path $dest) { Remove-Item -Path $dest -Recurse -Force }
        Move-Item -Path $staging -Destination $dest -Force
    } catch {
        Remove-Item -Path $staging -Recurse -Force -ErrorAction SilentlyContinue
        throw
    } finally {
        Remove-Item -Path $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    # Merge over the existing state rather than replacing it, for the same
    # reason commitVersionState does: previousVersion/rollbackHistory/channel
    # are lifecycle history this path has no business erasing.
    Write-Step 'Writing version metadata'
    $state = [ordered]@{}
    if (Test-Path $InstallFile) {
        try {
            (Get-Content -LiteralPath $InstallFile -Raw | ConvertFrom-Json).PSObject.Properties |
                ForEach-Object { $state[$_.Name] = $_.Value }
        } catch {
            Write-Warn 'install.json was unreadable — writing a fresh one'
            $state = [ordered]@{}
        }
    }
    $priorVersion = $state['installedVersion']
    if ($priorVersion -and $priorVersion -ne $version) { $state['previousVersion'] = $priorVersion }
    $state['installedVersion'] = $version
    $state['installMethod'] = 'github-release'
    $state['lastUpdateCheck'] = (Get-Date -Format o)
    $state['runtimeEntrypoint'] = $entrypoint
    $state | ConvertTo-Json -Depth 10 | Set-Content -Path $InstallFile -Encoding ascii
    Set-Content -Path $CurrentLink -Value "$version`n" -Encoding ascii -NoNewline
    Write-Ok "Runtime v$version installed from GitHub release $tagName"
}

# ── Main banner ────────────────────────────────────────────────────────────────
Write-Host ''
Write-Host '  A T L A S  —  operator install' -ForegroundColor White
Write-Host '  L2 Systems' -ForegroundColor DarkGray
Write-Host ''

# ── Check existing installation ────────────────────────────────────────────────
$currentVersion = Get-CurrentVersion
$isUpdate = $null -ne $currentVersion

$currentUsable = Test-VersionUsable -Version $currentVersion

if ($isUpdate) {
    Write-Host "  Current installation: $currentVersion" -ForegroundColor DarkGray
    if (-not $currentUsable) {
        Write-Warn "install.json names $currentVersion but it is not materialized under $VersionsDir — repairing"
    }

    # Check if update is needed. "Same version" is only a reason to stop when
    # that version is ALSO present and usable on disk (see Test-VersionUsable);
    # otherwise this fast path turns an interrupted run into a permanently
    # broken install that reports itself as healthy.
    $latestVersion = Get-LatestVersion
    if ($latestVersion -and $latestVersion -eq $currentVersion -and $currentUsable -and -not $Force) {
        Write-Host ''
        Write-Host "  Already on latest version ($currentVersion)" -ForegroundColor Green
        Write-Host '  Run with -Force to reinstall, or: atlas update' -ForegroundColor DarkGray
        Write-Host ''
        exit 0
    }
    if ($latestVersion -and $latestVersion -ne $currentVersion) {
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

    # ── Repair stale version directories ───────────────────────────────────
    # This used to delete EVERY directory under versions/, on the grounds that
    # installBundledPlatform refuses to overwrite a version dir whose manifest
    # fails checksum verification. That also deleted the directories
    # install.json's previousVersion and rollbackHistory name, leaving those
    # references dangling — so `atlas rollback` failed with "version X is not
    # installed" exactly when a bad update made the operator reach for it.
    # `atlas versions repair` removes only what is genuinely useless (leaked
    # staging dirs, dirs that fail integrity verification, dirs nothing in
    # install.json references) and retains every healthy rollback target. The
    # orphan/verification logic lives in one place — packages/atlas-cli/src/
    # commands.js — instead of being reimplemented here and in install.sh.
    if (Test-Path $VersionsDir) {
        Write-Step 'Repairing stale version directories'
        & $launcher versions repair
        if ($LASTEXITCODE -ne 0) {
            # An older globally-installed launcher may not know the subcommand.
            # Never fatal: materialization below has its own orphan handling.
            Write-Warn "'atlas versions repair' exited $LASTEXITCODE — continuing"
        }
    }

    # ── Materialize the runtime ────────────────────────────────────────────
    Write-Step 'Materializing the verified, self-contained ATLAS runtime'
    $materialized = $false

    # Primary path: npm platform package (bundled inside the launcher)
    & $launcher install 2>$null
    if ($LASTEXITCODE -eq 0) {
        # Verify the entrypoint actually exists on disk
        $state = Get-Content -LiteralPath $InstallFile -Raw -ErrorAction SilentlyContinue
        if ($state) {
            $parsed = $state | ConvertFrom-Json
            if ($parsed.runtimeEntrypoint) {
                $verDir = Join-Path $VersionsDir $parsed.installedVersion
                if (Test-Path (Join-Path $verDir $parsed.runtimeEntrypoint)) {
                    $materialized = $true
                }
            }
        }
    }

    # Fallback path: download the release asset directly from GitHub
    if (-not $materialized) {
        Write-Warn 'npm platform package unavailable; downloading runtime from GitHub releases'
        Download-RuntimeFromGithub
        # This path never goes through the Node lifecycle code, so nothing has
        # run migrations for the version just materialized. `db init` is
        # idempotent (it stamps and skips already-applied files), so calling it
        # on every fallback install converges rather than double-applying.
        $newVersion = Get-CurrentVersion
        if ($newVersion) { Invoke-DbInit -Launcher $launcher | Out-Null }
    }

    # Older source installers placed a Python-forwarding shim before npm on
    # PATH. Replace only that ATLAS-owned compatibility shim so `atlas update`
    # always reaches the lifecycle launcher from every directory. Hardcoded to
    # the historical %LOCALAPPDATA% location on purpose: it is a legacy artifact
    # left by past installers, not something $InstallRoot ever creates.
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
