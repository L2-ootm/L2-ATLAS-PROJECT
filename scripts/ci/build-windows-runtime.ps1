[CmdletBinding()]
param(
    [string]$Version = '0.1.0',
    [string]$OutputDir = '',
    [switch]$SkipNativeBuild,
    [switch]$SkipWebBuild
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
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
$getPipUrl = 'https://bootstrap.pypa.io/get-pip.py'
$getPipSha256 = 'A341E1A43E38001C551A1508A73FF23636A11970B61D901D9A1CAD2A18F57055'
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

function Get-PinnedFile([string]$Uri, [string]$Destination, [string]$Sha256) {
    if (-not (Test-Path -LiteralPath $Destination)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $Destination -Parent) | Out-Null
        Invoke-WebRequest -Uri $Uri -OutFile $Destination
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

if (-not $SkipNativeBuild) {
    New-Item -ItemType Directory -Force -Path $nativeBuildRoot | Out-Null
    $previousCargoTarget = $env:CARGO_TARGET_DIR
    $env:CARGO_TARGET_DIR = Join-Path $nativeBuildRoot 'cargo'
    Push-Location (Join-Path $repo 'native\atlas-core-rs')
    try { cargo build --release -p atlas-gateway; if ($LASTEXITCODE) { throw 'cargo build failed' } }
    finally {
        Pop-Location
        $env:CARGO_TARGET_DIR = $previousCargoTarget
    }
    Push-Location (Join-Path $repo 'services\atlas-tui')
    try { go build -trimpath -ldflags '-s -w' -o $tuiBuild .; if ($LASTEXITCODE) { throw 'go build failed' } }
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

if (Test-Path -LiteralPath $bundle) { Remove-Item -LiteralPath $bundle -Recurse -Force }
New-Item -ItemType Directory -Force -Path $bundle | Out-Null

Get-PinnedFile $pythonUrl $pythonZip $pythonSha256
Get-PinnedFile $getPipUrl $getPip $getPipSha256
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

$runtimeTrees = @(
    'infra\migrations',
    'modules',
    'skills\atlas',
    'packages\atlas-core\atlas_core',
    'services\agent-runtime\atlas_runtime',
    'services\agent-runtime\atlas_audit',
    'services\wiki-runtime\atlas_wiki',
    'foundation\atlas-hermes\acp_adapter',
    'foundation\atlas-hermes\acp_registry',
    'foundation\atlas-hermes\agent',
    'foundation\atlas-hermes\assets',
    'foundation\atlas-hermes\cron',
    'foundation\atlas-hermes\gateway',
    'foundation\atlas-hermes\hermes_cli',
    'foundation\atlas-hermes\locales',
    'foundation\atlas-hermes\optional-skills',
    'foundation\atlas-hermes\plugins',
    'foundation\atlas-hermes\providers',
    'foundation\atlas-hermes\skills',
    'foundation\atlas-hermes\tools',
    'foundation\atlas-hermes\tui_gateway'
)
foreach ($relative in $runtimeTrees) { Copy-TrackedPath $relative }
Copy-TrackedPath ':(glob)foundation/atlas-hermes/*.py'
Copy-Tree 'services\web-ui-react\dist'
Copy-Tree 'services\web-ui-react\scripts\serve-dist.mjs'

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
