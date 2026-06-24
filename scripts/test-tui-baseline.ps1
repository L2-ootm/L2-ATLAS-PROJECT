[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$baseline = Join-Path $PSScriptRoot "tui-baseline.ps1"
$output = Join-Path ([System.IO.Path]::GetTempPath()) "atlas-tui-baseline-$([guid]::NewGuid()).md"

if (-not (Test-Path -LiteralPath $baseline -PathType Leaf)) {
    throw "Baseline script is missing: $baseline"
}

try {
    & pwsh -NoProfile -File $baseline `
        -PackageRoot (Join-Path $repoRoot "apps/atlas-tui") `
        -OutputPath $output `
        -WarmSamples 3 `
        -IdleSeconds 2
    if ($LASTEXITCODE -ne 0) {
        throw "Baseline script failed with exit code $LASTEXITCODE"
    }

    $content = Get-Content -Raw -LiteralPath $output
    foreach ($required in @(
        "Cold start",
        "Warm start p95",
        "Idle working set",
        "Standalone artifact",
        "Direct runtime dependencies",
        "Unexpected network connections",
        "Budget verdict"
    )) {
        if (-not $content.Contains($required, [System.StringComparison]::Ordinal)) {
            throw "Baseline output is missing required field: $required"
        }
    }
}
finally {
    Remove-Item -LiteralPath $output -Force -ErrorAction SilentlyContinue
}

Write-Host "TUI baseline contract test passed."
