[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$')]
    [string]$Version,
    [ValidateSet('Prepare', 'Publish', 'Verify')]
    [string]$Mode = 'Prepare',
    [switch]$AllowDirty,
    [switch]$SkipNativeBuild,
    [switch]$SkipWebBuild
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$launcherDir = Join-Path $repo 'packages\atlas-cli'
$artifactRoot = Join-Path $repo 'artifacts\npm'
$bundleDir = Join-Path $repo "artifacts\atlas-windows-$Version"
$platformDir = Join-Path $artifactRoot "atlas-win32-x64-$Version"
$releaseDir = Join-Path $repo "artifacts\npm-release-$Version"
$launcherName = '@systemsl2/atlas'
$platformName = '@systemsl2/atlas-win32-x64'

function Invoke-Checked([string]$Label, [scriptblock]$Action) {
    Write-Host "==> $Label" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit $LASTEXITCODE)" }
}

function Read-Package([string]$Path) {
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Assert-VersionContract {
    $launcher = Read-Package (Join-Path $launcherDir 'package.json')
    if ($launcher.version -ne $Version) {
        throw "$launcherName is $($launcher.version), expected $Version"
    }
    if ($launcher.optionalDependencies.$platformName -ne $Version) {
        throw "$launcherName does not pin $platformName@$Version"
    }
    $platform = Read-Package (Join-Path $platformDir 'package.json')
    if ($platform.version -ne $Version -or $platform.atlasPlatform.version -ne $Version) {
        throw "$platformName metadata does not match $Version"
    }
}

function Assert-Unpublished([string]$Package) {
    $existing = [string](& npm view "$Package@$Version" version 2>$null)
    $global:LASTEXITCODE = 0
    if ($existing.Trim() -eq $Version) {
        Write-Host "$Package@$Version is already published; skipping" -ForegroundColor Yellow
        return $false
    }
    return $true
}

if ($Mode -eq 'Prepare') {
    $dirty = @(git -C $repo status --porcelain)
    if ($dirty.Count -gt 0 -and -not $AllowDirty) {
        throw 'working tree is not clean; commit/stash first or pass -AllowDirty intentionally'
    }

    Invoke-Checked 'Set exact launcher/platform dependency versions' {
        Push-Location $launcherDir
        try {
            npm pkg set "version=$Version" "optionalDependencies.$platformName=$Version"
        } finally { Pop-Location }
    }
    Invoke-Checked 'Run launcher lifecycle tests' {
        Push-Location $launcherDir
        try { npm test } finally { Pop-Location }
    }
    Invoke-Checked 'Run config migration and doctor tests' {
        & (Join-Path $repo '.venv\Scripts\python.exe') -m pytest `
            (Join-Path $repo 'services\agent-runtime\tests\test_config_service.py') `
            (Join-Path $repo 'services\agent-runtime\tests\test_cli_doctor.py') -q
    }

    $buildArgs = @{ Version = $Version; OutputDir = $bundleDir }
    if ($SkipNativeBuild) { $buildArgs.SkipNativeBuild = $true }
    if ($SkipWebBuild) { $buildArgs.SkipWebBuild = $true }
    Write-Host '==> Build self-contained Windows runtime' -ForegroundColor Cyan
    & (Join-Path $repo 'scripts\ci\build-windows-runtime.ps1') @buildArgs

    Invoke-Checked 'Build exact Windows platform package' {
        node (Join-Path $repo 'scripts\ci\build-platform-package.js') `
            --bundle $bundleDir --out-dir $artifactRoot --version $Version `
            --platform win32-x64 --entrypoint bin/atlas.js
    }
    Assert-VersionContract

    New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
    Invoke-Checked 'Pack platform package' { npm pack $platformDir --pack-destination $releaseDir }
    Invoke-Checked 'Pack launcher package' { npm pack $launcherDir --pack-destination $releaseDir }
    Invoke-Checked 'Verify embedded Python dependency closure' {
        & (Join-Path $bundleDir 'python\python.exe') -s -m pip check
        & (Join-Path $bundleDir 'python\python.exe') -s -c `
            'import atlas_core, atlas_runtime, atlas_wiki, agent, claude_agent_sdk; print("runtime dependency closure: OK")'
    }
    Write-Host "Prepared $Version in $releaseDir" -ForegroundColor Green
    Write-Host 'Commit the versioned source, wait for CI, then rerun with -Mode Publish.'
    exit 0
}

Assert-VersionContract

if ($Mode -eq 'Publish') {
    $dirty = @(git -C $repo status --porcelain)
    if ($dirty.Count -gt 0 -and -not $AllowDirty) { throw 'publish requires a clean committed working tree' }
    Invoke-Checked 'Verify npm identity' { npm whoami }
    $needPlatform = Assert-Unpublished $platformName
    $needLauncher = Assert-Unpublished $launcherName
    if ($needPlatform) { Invoke-Checked "Publish $platformName@$Version" { npm publish $platformDir --access public } }
    if ($needLauncher) { Invoke-Checked "Publish $launcherName@$Version" { npm publish $launcherDir --access public } }
}

Invoke-Checked 'Verify public npm versions' {
    $platformVersion = [string](npm view "$platformName@$Version" version)
    $launcherVersion = [string](npm view "$launcherName@$Version" version)
    if ($platformVersion.Trim() -ne $Version -or $launcherVersion.Trim() -ne $Version) {
        throw 'registry verification returned an unexpected version'
    }
}
Write-Host "$launcherName@$Version and $platformName@$Version are public." -ForegroundColor Green
