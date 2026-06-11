<#
.SYNOPSIS
  L2 ATLAS — Twenty CRM sidecar setup (D-020/D-021: pinned upstream, never forked).

.DESCRIPTION
  Fetches Twenty's OFFICIAL docker-compose.yml and .env.example at a pinned
  release tag into infra/compose/twenty/, generates required secrets into a
  local .env (gitignored), and manages the sidecar lifecycle.

  ATLAS integrates with Twenty via Core API, Metadata API, MCP, and webhooks
  only. No Twenty source is ever embedded in ATLAS (AGPL boundary, D-020).

.USAGE
  pwsh scripts/setup_twenty.ps1 fetch              # download pinned compose + env template, generate secrets
  pwsh scripts/setup_twenty.ps1 up                 # start the sidecar (Podman preferred, Docker fallback)
  pwsh scripts/setup_twenty.ps1 status             # show container status
  pwsh scripts/setup_twenty.ps1 down               # stop the sidecar (data volume preserved)
  pwsh scripts/setup_twenty.ps1 fetch -Version v2.2.0   # re-pin (check Twenty changelog first — v2.x had breaking API changes)
  pwsh scripts/setup_twenty.ps1 up -Engine docker  # force a specific engine

.NOTES
  Container engine: Podman is preferred (daemonless, lower idle RAM — no
  always-on VM service required; aligns with the no-bloat budget). Docker
  Desktop remains a supported fallback. Auto-detection order: podman, docker.
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet("fetch", "up", "down", "status")]
    [string]$Action = "fetch",
    # Pin per TWENTY_CRM_INTAKE: v2.1.0+ required; do not float on latest.
    [string]$Version = "v2.1.0",
    [ValidateSet("auto", "podman", "docker")]
    [string]$Engine = "auto"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$TwentyDir = Join-Path $RepoRoot "infra\compose\twenty"
$ComposeFile = Join-Path $TwentyDir "docker-compose.yml"
$EnvFile = Join-Path $TwentyDir ".env"
$RawBase = "https://raw.githubusercontent.com/twentyhq/twenty/$Version/packages/twenty-docker"

function New-Secret {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    [Convert]::ToBase64String($bytes)
}

function Invoke-Fetch {
    New-Item -ItemType Directory -Force $TwentyDir | Out-Null

    Write-Host "Fetching official Twenty compose at $Version ..."
    Invoke-WebRequest -Uri "$RawBase/docker-compose.yml" -OutFile $ComposeFile
    Invoke-WebRequest -Uri "$RawBase/.env.example" -OutFile (Join-Path $TwentyDir ".env.example")
    Set-Content -Path (Join-Path $TwentyDir "PINNED_VERSION") -Value $Version

    if (Test-Path $EnvFile) {
        Write-Host ".env already exists — secrets preserved. Delete it to regenerate."
    } else {
        # Fill secret-bearing placeholders in whatever schema this tag's
        # .env.example uses (APP_SECRET vs ENCRYPTION_KEY varies by version).
        $secretKeys = @("APP_SECRET", "ENCRYPTION_KEY", "PG_DATABASE_PASSWORD", "POSTGRES_PASSWORD")
        $lines = Get-Content (Join-Path $TwentyDir ".env.example") | ForEach-Object {
            $line = $_
            foreach ($key in $secretKeys) {
                if ($line -match "^\s*#?\s*$key=") {
                    $line = "$key=$(New-Secret)"
                    break
                }
            }
            if ($line -match "^\s*TAG=") { $line = "TAG=$Version" }
            $line
        }
        Set-Content -Path $EnvFile -Value $lines
        Write-Host "Generated $EnvFile with fresh secrets (gitignored — never commit)."
    }
    Write-Host "Done. Start with: pwsh scripts/setup_twenty.ps1 up"
}

function Assert-Fetched {
    if (-not (Test-Path $ComposeFile)) {
        throw "Compose file not found. Run: pwsh scripts/setup_twenty.ps1 fetch"
    }
}

function Resolve-Engine {
    # Returns the compose launcher as an array: e.g. @("podman","compose").
    if ($Engine -in @("auto", "podman") -and (Get-Command podman -ErrorAction SilentlyContinue)) {
        return @("podman", "compose")
    }
    if ($Engine -in @("auto", "docker") -and (Get-Command docker -ErrorAction SilentlyContinue)) {
        return @("docker", "compose")
    }
    throw ("No container engine found (looked for: $Engine). Preferred: Podman " +
        "(daemonless, lighter) — `winget install RedHat.Podman` then `podman machine init; podman machine start`. " +
        "Fallback: Docker Desktop (WSL2 backend).")
}

function Invoke-Compose {
    param([string[]]$ComposeArgs)
    $launcher = Resolve-Engine
    Write-Host "engine: $($launcher -join ' ')"
    & $launcher[0] $launcher[1] -f $ComposeFile --env-file $EnvFile @ComposeArgs
    if ($LASTEXITCODE -ne 0) { throw "compose exited with $LASTEXITCODE" }
}

switch ($Action) {
    "fetch"  { Invoke-Fetch }
    "up"     { Assert-Fetched; Invoke-Compose @("up", "-d"); Write-Host "Twenty starting — UI at http://localhost:3000 once healthy." }
    "down"   { Assert-Fetched; Invoke-Compose @("down") }
    "status" { Assert-Fetched; Invoke-Compose @("ps") }
}
