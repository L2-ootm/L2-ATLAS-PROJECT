[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('source', 'installed')][string]$Mode,
    [Parameter(Mandatory)][string]$Repo,
    [Parameter(Mandatory)][string]$GateRoot,
    [Parameter(Mandatory)][string]$AtlasHome,
    [Parameter(Mandatory)][string]$Database,
    [Parameter(Mandatory)][string]$Config,
    [Parameter(Mandatory)][string]$NpmPrefix,
    [Parameter(Mandatory)][string]$GatewayBinary,
    [Parameter(Mandatory)][string]$ReleaseVersion,
    [Parameter(Mandatory)][int[]]$Port,
    [ValidateSet('planning', 'python-core', 'python-runtime', 'node-cli', 'rust-gateway')][string[]]$TestCommand = @(),
    [string]$InstallRoot,
    [string]$InstalledLauncher,
    [switch]$Resume,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$entry = Join-Path $PSScriptRoot 'gate.py'
$gateArgs = @(
    $entry, '--mode', $Mode, '--repo', $Repo, '--gate-root', $GateRoot,
    '--atlas-home', $AtlasHome, '--database', $Database, '--config', $Config,
    '--npm-prefix', $NpmPrefix, '--gateway-binary', $GatewayBinary,
    '--release-version', $ReleaseVersion
)
foreach ($value in $Port) { $gateArgs += @('--port', [string]$value) }
foreach ($label in $TestCommand) { $gateArgs += @('--test-command', $label) }
if ($InstallRoot) { $gateArgs += @('--install-root', $InstallRoot) }
if ($InstalledLauncher) { $gateArgs += @('--installed-launcher', $InstalledLauncher) }
if ($Resume) { $gateArgs += '--resume' }
if ($DryRun) { $gateArgs += '--dry-run' }

& python @gateArgs
exit $LASTEXITCODE
