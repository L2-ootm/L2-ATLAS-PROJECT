<#
.SYNOPSIS
    Local npm publish dry-run — validates everything without publishing.

.DESCRIPTION
    Runs all pre-publish gates locally:
    1. Version consistency check (package.json vs optional deps)
    2. Clean git status (or explicit -AllowDirty)
    3. Launcher tests (atlas-cli)
    4. Config/doctor tests (Python)
    5. npm pack --dry-run for both packages
    6. npm auth check (whoami)
    7. Registry pre-flight (version not already published)

    Exits 0 if ready to publish, 1 if any gate fails.

.PARAMETER Version
    Target version (e.g. 0.1.2). Defaults to packages/atlas-cli/package.json version.

.PARAMETER AllowDirty
    Skip the clean-git-status check.

.PARAMETER SkipPython
    Skip Python test gates (useful if .venv not set up).

.EXAMPLE
    .\scripts\release\publish-dry-run.ps1
    .\scripts\release\publish-dry-run.ps1 -Version 0.1.2
    .\scripts\release\publish-dry-run.ps1 -AllowDirty -SkipPython
#>
[CmdletBinding()]
param(
    [string]$Version,
    [switch]$AllowDirty,
    [switch]$SkipPython
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$launcherDir = Join-Path $repo 'packages\atlas-cli'

function Write-Gate([string]$Name, [string]$Status, [string]$Detail = '') {
    $color = if ($Status -eq 'PASS') { 'Green' } elseif ($Status -eq 'SKIP') { 'Yellow' } else { 'Red' }
    $mark = if ($Status -eq 'PASS') { 'OK  ' } elseif ($Status -eq 'SKIP') { 'SKIP' } else { 'FAIL' }
    $msg = "  [$mark] $Name"
    if ($Detail) { $msg += ": $Detail" }
    Write-Host $msg -ForegroundColor $color
}

function Invoke-Gate([string]$Name, [scriptblock]$Action) {
    try {
        & $Action
        Write-Gate $Name 'PASS'
        return $true
    } catch {
        Write-Gate $Name 'FAIL' $_.Exception.Message
        return $false
    }
}

# ── Resolve version ──────────────────────────────────────────────────────────
$launcherJson = Get-Content (Join-Path $launcherDir 'package.json') -Raw | ConvertFrom-Json
if (-not $Version) { $Version = $launcherJson.version }
$platformName = '@systemsl2/atlas-win32-x64'

Write-Host ""
Write-Host "ATLAS npm Publish Dry-Run - $Version" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor DarkGray
Write-Host ""

$allPass = $true
$gateCount = 0
$passCount = 0

# ── Gate 1: Version format ──────────────────────────────────────────────────
$gateCount++
$valid = Invoke-Gate 'Version format' {
    if ($Version -notmatch '^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$') {
        throw "invalid version: $Version"
    }
}
if ($valid) { $passCount++ } else { $allPass = $false }

# ── Gate 2: Version consistency ─────────────────────────────────────────────
$gateCount++
$valid = Invoke-Gate 'Version consistency' {
    if ($launcherJson.version -ne $Version) {
        throw "package.json is $($launcherJson.version), expected $Version"
    }
    $pinned = $launcherJson.optionalDependencies.$platformName
    if ($pinned -ne $Version) {
        throw "$platformName pinned at $pinned, expected $Version"
    }
}
if ($valid) { $passCount++ } else { $allPass = $false }

# ── Gate 3: Git status ──────────────────────────────────────────────────────
$gateCount++
if ($AllowDirty) {
    Write-Gate 'Git clean' 'SKIP' '-AllowDirty'
    $passCount++
} else {
    $valid = Invoke-Gate 'Git clean' {
        $dirty = @(git -C $repo status --porcelain)
        if ($dirty.Count -gt 0) {
            throw "$($dirty.Count) uncommitted change(s)"
        }
    }
    if ($valid) { $passCount++ } else { $allPass = $false }
}

# ── Gate 4: Launcher tests ──────────────────────────────────────────────────
$gateCount++
$valid = Invoke-Gate 'atlas-cli tests' {
    Push-Location $launcherDir
    try {
        $out = npm test 2>&1
        if ($LASTEXITCODE -ne 0) { throw "exit $LASTEXITCODE" }
    } finally { Pop-Location }
}
if ($valid) { $passCount++ } else { $allPass = $false }

# ── Gate 5: Python tests ────────────────────────────────────────────────────
$gateCount++
if ($SkipPython) {
    Write-Gate 'Python config/doctor tests' 'SKIP' '-SkipPython'
    $passCount++
} else {
    $venvPython = Join-Path $repo '.venv\Scripts\python.exe'
    if (Test-Path $venvPython) {
        $valid = Invoke-Gate 'Python config/doctor tests' {
            $out = & $venvPython -m pytest `
                (Join-Path $repo 'services\agent-runtime\tests\test_config_service.py') `
                (Join-Path $repo 'services\agent-runtime\tests\test_cli_doctor.py') -q 2>&1
            if ($LASTEXITCODE -ne 0) { throw "exit $LASTEXITCODE" }
        }
        if ($valid) { $passCount++ } else { $allPass = $false }
    } else {
        Write-Gate 'Python config/doctor tests' 'SKIP' '.venv not found'
        $passCount++
    }
}

# ── Gate 6: npm pack dry-run (launcher) ─────────────────────────────────────
$gateCount++
$valid = Invoke-Gate 'npm pack launcher (dry-run)' {
    Push-Location $launcherDir
    try {
        $out = npm pack --dry-run 2>&1
        if ($LASTEXITCODE -ne 0) { throw "exit $LASTEXITCODE" }
    } finally { Pop-Location }
}
if ($valid) { $passCount++ } else { $allPass = $false }

# ── Gate 7: npm auth ────────────────────────────────────────────────────────
$gateCount++
$valid = Invoke-Gate 'npm auth (whoami)' {
    $out = npm whoami 2>&1
    if ($LASTEXITCODE -ne 0) { throw "not authenticated; run 'npm login' first" }
    Write-Host "        Logged in as: $out" -ForegroundColor DarkGray
}
if ($valid) { $passCount++ } else { $allPass = $false }

# ── Gate 8: Registry pre-flight ─────────────────────────────────────────────
$gateCount++
$valid = Invoke-Gate "Registry: @systemsl2/atlas@$Version not published" {
    $out = npm view "@systemsl2/atlas@$Version" version 2>&1
    if ($LASTEXITCODE -eq 0) {
        throw "already published: @systemsl2/atlas@$Version"
    }
    $global:LASTEXITCODE = 0
}
if ($valid) { $passCount++ } else { $allPass = $false }

$gateCount++
$valid = Invoke-Gate "Registry: $platformName@$Version not published" {
    $out = npm view "$platformName@$Version" version 2>&1
    if ($LASTEXITCODE -eq 0) {
        throw "already published: $platformName@$Version"
    }
    $global:LASTEXITCODE = 0
}
if ($valid) { $passCount++ } else { $allPass = $false }

# ── Summary ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor DarkGray
if ($allPass) {
    Write-Host "ALL GATES PASSED ($passCount/$gateCount) - ready to publish $Version" -ForegroundColor Green
    Write-Host ""
    Write-Host "To publish:" -ForegroundColor Yellow
    Write-Host "  1. Tag:  git tag v$Version; git push origin v$Version" -ForegroundColor DarkGray
    Write-Host "  2. CI:   GitHub Actions will run publish-npm.yml automatically" -ForegroundColor DarkGray
    Write-Host "  3. Or:   .\scripts\release\npm-release.ps1 -Version $Version -Mode Publish" -ForegroundColor DarkGray
    exit 0
} else {
    Write-Host "GATES FAILED: $($gateCount - $passCount)/$gateCount failed" -ForegroundColor Red
    Write-Host "Fix the failures above before publishing." -ForegroundColor Yellow
    exit 1
}
