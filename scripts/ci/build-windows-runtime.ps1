[CmdletBinding()]
param(
    [string]$Version = '',
    [string]$OutputDir = '',
    [switch]$SkipNativeBuild,
    [switch]$SkipWebBuild
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$launcherManifest = Join-Path $repo 'packages\atlas-cli\package.json'
if (-not $Version) { $Version = (Get-Content -Raw -LiteralPath $launcherManifest | ConvertFrom-Json).version }
$buildSha = (& git -C $repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or -not $buildSha) { throw 'could not resolve build Git SHA' }
$artifactRoot = Join-Path $repo 'artifacts'
if (-not $OutputDir) { $OutputDir = Join-Path $artifactRoot "atlas-windows-$Version" }
$bundle = [IO.Path]::GetFullPath($OutputDir)
$artifactPrefix = [IO.Path]::GetFullPath($artifactRoot) + [IO.Path]::DirectorySeparatorChar
if (-not $bundle.StartsWith($artifactPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDir must stay inside $artifactRoot"
}

$pythonVersion = '3.13.11'
$pythonUrl = "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-embed-amd64.zip"
$pythonSha256 = '1EC066FB61BA5E8C73E29E048CD07C26850F74585E3A116005135B31B8004890'
# Pinned to an immutable pypa/get-pip commit rather than
# https://bootstrap.pypa.io/get-pip.py, which is a rolling URL: PyPA rotates it
# on every pip release, so a fixed hash against it fails the build the day pip
# ships. It did — 26.1.2 (5e84c836, the old pin) became 26.2.1 (af54dfe7) on
# 2026-08-04 and broke the 0.1.9 release. A commit-addressed URL cannot rotate,
# so the hash and the URL agree by construction. To bump: pick the new commit
# from https://github.com/pypa/get-pip/commits/main/public/get-pip.py and record
# its SHA-256 here.
$getPipCommit = 'af54dfe793b24685f8dc4ebba0630d9f2d77653c'  # "Update to 26.2.1"
# bootstrap.pypa.io stays as a second mirror: it serves these exact bytes for as
# long as 26.2.1 is current, and once it rotates it simply stops matching the
# hash — the same failure the commit-addressed primary now prevents.
$getPipUrls = @(
    "https://raw.githubusercontent.com/pypa/get-pip/$getPipCommit/public/get-pip.py",
    'https://bootstrap.pypa.io/get-pip.py'
)
$getPipSha256 = 'FB24E693BAB954209A063D90953621412CCAD4A500905A726286E038F508DDF6'
$cache = Join-Path $artifactRoot '.cache'
$nativeBuildRoot = Join-Path $artifactRoot ".build\$Version"
$gatewayBuild = Join-Path $nativeBuildRoot 'cargo\release\atlas-gateway.exe'
$tuiBuild = Join-Path $nativeBuildRoot 'atlas-tui.exe'
$pythonZip = Join-Path $cache "python-$pythonVersion-embed-amd64.zip"
$getPip = Join-Path $cache 'get-pip.py'

function Assert-Hash([string]$Path, [string]$Expected) {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
    if ($actual -ne $Expected) { throw "SHA-256 mismatch for $Path (expected $Expected, got $actual)" }
}

# The SHA-256 is the contract, so any mirror serving the pinned bytes is
# acceptable and anything else still fails Assert-Hash. Both hosts throttle
# under load — a codeload 429 and a raw.githubusercontent 503 each broke a 0.1.9
# release attempt — so try every mirror with backoff before giving up.
function Get-PinnedFile([string[]]$Uris, [string]$Destination, [string]$Sha256) {
    if (-not (Test-Path -LiteralPath $Destination)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) | Out-Null
        $failures = @()
        $ok = $false
        foreach ($uri in $Uris) {
            for ($attempt = 1; $attempt -le 3; $attempt++) {
                try {
                    Invoke-WebRequest -Uri $uri -OutFile $Destination
                    $ok = $true
                    break
                } catch {
                    $failures += "$uri (attempt $attempt): $($_.Exception.Message)"
                    if ($attempt -lt 3) { Start-Sleep -Seconds (5 * $attempt) }
                }
            }
            if ($ok) { break }
        }
        if (-not $ok) {
            throw "could not download $Destination from any mirror:`n$($failures -join "`n")"
        }
    }
    Assert-Hash $Destination $Sha256
}

function Copy-Tree([string]$Relative) {
    $source = Join-Path $repo $Relative
    if (-not (Test-Path -LiteralPath $source)) { throw "required runtime path missing: $Relative" }
    $destination = Join-Path $bundle $Relative
    New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force
}

function Copy-TrackedPath([string]$Pathspec) {
    $files = @(git -C $repo ls-files -- $Pathspec)
    if ($LASTEXITCODE -ne 0 -or $files.Count -eq 0) { throw "tracked runtime path missing: $Pathspec" }
    foreach ($file in $files) {
        $source = Join-Path $repo $file
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { continue }
        $destination = Join-Path $bundle $file
        New-Item -ItemType Directory -Force -Path (Split-Path $destination -Parent) | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }
}

# Copy every entry declared in the shared payload manifest. Keep this parser in
# sync with the POSIX twins in build-linux-runtime.sh / build-darwin-runtime.sh
# and with readPayloadManifest() in scripts/ci/payload-manifest.js.
function Invoke-PayloadManifest([string]$ManifestPath) {
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        throw "payload manifest missing: $ManifestPath"
    }
    $entries = 0
    foreach ($line in Get-Content -LiteralPath $ManifestPath) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        $parts = $trimmed -split '\s+', 2
        if ($parts.Count -ne 2) { throw "malformed payload manifest line: $line" }
        $pathspec = $parts[1].Trim()
        switch ($parts[0]) {
            'tracked' { Copy-TrackedPath $pathspec }
            'tree'    { Copy-Tree $pathspec }
            default   { throw "unknown payload manifest mode '$($parts[0])' in line: $line" }
        }
        $entries++
    }
    if ($entries -eq 0) { throw "payload manifest declared no entries: $ManifestPath" }
    Write-Host "payload entries: $entries"
}

if (-not $SkipNativeBuild) {
    New-Item -ItemType Directory -Force -Path $nativeBuildRoot | Out-Null
    $previousCargoTarget = $env:CARGO_TARGET_DIR
    $previousReleaseVersion = $env:ATLAS_RELEASE_VERSION
    $previousBuildSha = $env:ATLAS_BUILD_SHA
    $env:CARGO_TARGET_DIR = Join-Path $nativeBuildRoot 'cargo'
    $env:ATLAS_RELEASE_VERSION = $Version
    $env:ATLAS_BUILD_SHA = $buildSha
    Push-Location (Join-Path $repo 'native\atlas-core-rs')
    try { cargo build --release -p atlas-gateway; if ($LASTEXITCODE) { throw 'cargo build failed' } }
    finally {
        Pop-Location
        $env:CARGO_TARGET_DIR = $previousCargoTarget
        $env:ATLAS_RELEASE_VERSION = $previousReleaseVersion
        $env:ATLAS_BUILD_SHA = $previousBuildSha
    }
    Push-Location (Join-Path $repo 'services\atlas-tui')
    try {
        $tuiLdflags = "-s -w -X main.version=$Version -X main.commit=$buildSha"
        go build -trimpath -ldflags $tuiLdflags -o $tuiBuild .
        if ($LASTEXITCODE) { throw 'go build failed' }
    }
    finally { Pop-Location }
} else {
    $gatewayBuild = Join-Path $repo 'native\atlas-core-rs\target\release\atlas-gateway.exe'
    $tuiBuild = Join-Path $repo 'services\atlas-tui\atlas-tui.exe'
}
if (-not $SkipWebBuild) {
    Push-Location (Join-Path $repo 'services\web-ui-react')
    try { npm run build; if ($LASTEXITCODE) { throw 'cockpit build failed' } }
    finally { Pop-Location }
}

$required = @(
    'services\web-ui-react\dist\index.html',
    'packages\atlas-cli\runtime\win32\atlas.js'
)
foreach ($relative in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $repo $relative))) { throw "required build output missing: $relative" }
}
foreach ($output in @($gatewayBuild, $tuiBuild)) {
    if (-not (Test-Path -LiteralPath $output)) { throw "required native build output missing: $output" }
}
$tuiIdentity = (& $tuiBuild --version).Trim()
if ($LASTEXITCODE -ne 0 -or $tuiIdentity -ne "atlas-tui $Version ($buildSha)") {
    throw "Go TUI identity mismatch: $tuiIdentity"
}
& node (Join-Path $repo 'scripts\ci\verify-gateway-identity.js') `
    --binary $gatewayBuild --release-version $Version --build-sha $buildSha `
    --launcher-manifest $launcherManifest
if ($LASTEXITCODE) { throw 'gateway binary identity verification failed' }

if (Test-Path -LiteralPath $bundle) { Remove-Item -LiteralPath $bundle -Recurse -Force }
New-Item -ItemType Directory -Force -Path $bundle | Out-Null

Get-PinnedFile $pythonUrl $pythonZip $pythonSha256
Get-PinnedFile $getPipUrls $getPip $getPipSha256
$pythonDir = Join-Path $bundle 'python'
Expand-Archive -LiteralPath $pythonZip -DestinationPath $pythonDir
$pth = Join-Path $pythonDir 'python313._pth'
@(
    'python313.zip',
    '.',
    'Lib\site-packages',
    '..\services\agent-runtime',
    '..\packages\atlas-core',
    '..\services\wiki-runtime',
    '..\foundation\atlas-hermes',
    'import site'
) | Set-Content -LiteralPath $pth -Encoding ascii

$python = Join-Path $pythonDir 'python.exe'
$previousNoUserSite = $env:PYTHONNOUSERSITE
$env:PYTHONNOUSERSITE = '1'
& $python -s $getPip --disable-pip-version-check --no-warn-script-location
if ($LASTEXITCODE) { throw 'get-pip bootstrap failed' }
$runtimeDependencies = @(
    'openai==2.24.0',
    'python-dotenv==1.2.2',
    'fire==0.7.1',
    'httpx[socks]==0.28.1',
    'rich==14.3.3',
    'tenacity==9.1.4',
    'pyyaml==6.0.3',
    'ruamel.yaml==0.18.17',
    'requests==2.33.0',
    'jinja2==3.1.6',
    'pydantic==2.13.4',
    'prompt_toolkit==3.0.52',
    'croniter==6.0.0',
    'PyJWT[crypto]==2.12.1',
    'tzdata==2025.3',
    'psutil==7.2.2',
    'typer==0.25.1',
    # First-class Claude Code execution must work in the self-contained
    # release. The SDK includes its own runtime, so users do not repair the
    # embedded Python environment after npm installation.
    'claude-agent-sdk==0.2.104'
)
& $python -s -m pip install --disable-pip-version-check --no-compile $runtimeDependencies
if ($LASTEXITCODE) { throw 'runtime dependency installation failed' }

# Payload composition is declared once in infra/release/payload.manifest and
# consumed identically by all three platform builders. Previously this list was
# hardcoded here and hand-mirrored into the linux and darwin scripts, so a tree
# could ship on one OS and silently vanish on another.
Invoke-PayloadManifest (Join-Path $repo 'infra\release\payload.manifest')

Copy-TrackedPath 'services/atlas-tui/go.mod'
New-Item -ItemType Directory -Force -Path (Join-Path $bundle 'native\atlas-core-rs\target\release') | Out-Null
Copy-Item -LiteralPath $gatewayBuild -Destination (Join-Path $bundle 'native\atlas-core-rs\target\release\atlas-gateway.exe') -Force
New-Item -ItemType Directory -Force -Path (Join-Path $bundle 'services\atlas-tui') | Out-Null
Copy-Item -LiteralPath $tuiBuild -Destination (Join-Path $bundle 'services\atlas-tui\atlas-tui.exe') -Force
New-Item -ItemType Directory -Force -Path (Join-Path $bundle 'bin') | Out-Null
Copy-Item -LiteralPath (Join-Path $repo 'packages\atlas-cli\runtime\win32\atlas.js') -Destination (Join-Path $bundle 'bin\atlas.js')
Copy-Item -LiteralPath (Join-Path $repo 'LICENSE') -Destination (Join-Path $bundle 'LICENSE')
Copy-Item -LiteralPath (Join-Path $repo 'THIRD_PARTY_LICENSES.md') -Destination (Join-Path $bundle 'THIRD_PARTY_LICENSES.md')

# Never publish bytecode copied from a developer interpreter. The embedded
# runtime may create version-correct caches locally after installation.
Get-ChildItem -LiteralPath $bundle -Recurse -Directory -Filter '__pycache__' | `
    Sort-Object { $_.FullName.Length } -Descending | `
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
Get-ChildItem -LiteralPath $bundle -Recurse -File -Filter '*.pyc' | `
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }

$manifest = [ordered]@{
    version = $Version
    platform = 'win32-x64'
    entrypoint = 'bin/atlas.js'
    python = $pythonVersion
    built_at = (Get-Date).ToUniversalTime().ToString('o')
}
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $bundle 'runtime.json') -Encoding utf8

$previousNoBytecode = $env:PYTHONDONTWRITEBYTECODE
$env:PYTHONDONTWRITEBYTECODE = '1'
& $python -s -c 'import atlas_core, atlas_runtime, atlas_wiki, agent, claude_agent_sdk; print("embedded runtime imports: OK")'
if ($LASTEXITCODE) { throw 'embedded runtime import verification failed' }
$helpOutput = & $python -s -m atlas_runtime.cli.main --help 2>&1
$helpExit = $LASTEXITCODE
if ($helpExit) { throw "embedded atlas CLI verification failed: $($helpOutput -join [Environment]::NewLine)" }
$helpOutput | Select-Object -First 1
$env:PYTHONNOUSERSITE = $previousNoUserSite
$env:PYTHONDONTWRITEBYTECODE = $previousNoBytecode

# Verification imports must not leave interpreter caches in the immutable
# payload, even if a caller overrides Python's bytecode environment.
Get-ChildItem -LiteralPath $bundle -Recurse -Directory -Filter '__pycache__' | `
    Sort-Object { $_.FullName.Length } -Descending | `
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
Get-ChildItem -LiteralPath $bundle -Recurse -File -Filter '*.pyc' | `
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }

$size = (Get-ChildItem -LiteralPath $bundle -Recurse -File | Measure-Object Length -Sum).Sum
Write-Host "bundle: $bundle"
Write-Host ("files: {0}" -f (Get-ChildItem -LiteralPath $bundle -Recurse -File).Count)
Write-Host ("size: {0:N1} MB" -f ($size / 1MB))
