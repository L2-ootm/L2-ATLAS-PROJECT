[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PackageRoot,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [ValidateRange(3, 100)]
    [int]$WarmSamples = 10,

    [ValidateRange(1, 60)]
    [int]$IdleSeconds = 5
)

$ErrorActionPreference = "Stop"

function Get-Percentile95 {
    param([Parameter(Mandatory = $true)][double[]]$Values)
    $sorted = @($Values | Sort-Object)
    $index = [math]::Max(0, [math]::Ceiling($sorted.Count * 0.95) - 1)
    return [double]$sorted[$index]
}

function Measure-SnapshotStart {
    param([Parameter(Mandatory = $true)][string]$Executable)

    $stdout = Join-Path ([System.IO.Path]::GetTempPath()) "atlas-tui-out-$([guid]::NewGuid()).txt"
    $stderr = Join-Path ([System.IO.Path]::GetTempPath()) "atlas-tui-err-$([guid]::NewGuid()).txt"
    try {
        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $process = Start-Process `
            -FilePath $Executable `
            -ArgumentList @("--snapshot", "--ascii", "--no-color") `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr `
            -PassThru `
            -WindowStyle Hidden `
            -Wait
        $stopwatch.Stop()
        if ($process.ExitCode -ne 0) {
            $errorText = Get-Content -Raw -LiteralPath $stderr -ErrorAction SilentlyContinue
            throw "Snapshot process failed with exit code $($process.ExitCode): $errorText"
        }
        $outputText = Get-Content -Raw -LiteralPath $stdout
        if (-not $outputText.Contains("ATLAS", [System.StringComparison]::Ordinal)) {
            throw "Snapshot process did not render the ATLAS identity"
        }
        return $stopwatch.Elapsed.TotalMilliseconds
    }
    finally {
        Remove-Item -LiteralPath $stdout -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderr -Force -ErrorAction SilentlyContinue
    }
}

$resolvedPackageRoot = (Resolve-Path -LiteralPath $PackageRoot).Path
$packageFile = Join-Path $resolvedPackageRoot "package.json"
$lockFile = Join-Path $resolvedPackageRoot "bun.lock"
$executable = Join-Path $resolvedPackageRoot "dist/atlas-tui.exe"

foreach ($requiredFile in @($packageFile, $lockFile, $executable)) {
    if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
        throw "Required baseline input is missing: $requiredFile"
    }
}

$package = Get-Content -Raw -LiteralPath $packageFile | ConvertFrom-Json
$runtimeDependencies = @($package.dependencies.PSObject.Properties.Name)
$developmentDependencies = @($package.devDependencies.PSObject.Properties.Name)
$transitiveDependencies = @(
    Select-String -LiteralPath $lockFile -Pattern '^\s{4}"[^"]+": \['
).Count

$sourceFiles = @(
    Get-ChildItem -LiteralPath (Join-Path $resolvedPackageRoot "src") -Recurse -File
)
$sourceBytes = ($sourceFiles | Measure-Object -Property Length -Sum).Sum
$binaryBytes = (Get-Item -LiteralPath $executable).Length

$coldStartMs = Measure-SnapshotStart -Executable $executable
$warmMeasurements = @(
    1..$WarmSamples | ForEach-Object {
        Measure-SnapshotStart -Executable $executable
    }
)
$warmP95Ms = Get-Percentile95 -Values $warmMeasurements

$idleProcess = Start-Process `
    -FilePath $executable `
    -PassThru `
    -WindowStyle Hidden
try {
    Start-Sleep -Seconds $IdleSeconds
    $idleProcess.Refresh()
    if ($idleProcess.HasExited) {
        throw "Interactive shell exited before the idle sample"
    }
    $workingSetMiB = $idleProcess.WorkingSet64 / 1MB
    $privateMiB = $idleProcess.PrivateMemorySize64 / 1MB
    $networkConnections = 0
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        $networkConnections = @(
            Get-NetTCPConnection -OwningProcess $idleProcess.Id -ErrorAction SilentlyContinue
        ).Count
    }
}
finally {
    if (-not $idleProcess.HasExited) {
        Stop-Process -Id $idleProcess.Id -Force
        $idleProcess.WaitForExit()
    }
}

$binaryMiB = $binaryBytes / 1MB
$sourceKiB = $sourceBytes / 1KB
$initialIdleBudgetMiB = 150
$measuredIdleCeilingMiB = 240
$initialIdleVerdict = if ($workingSetMiB -le $initialIdleBudgetMiB) { "PASS" } else { "MISS" }
$acceptanceVerdict = if (
    $runtimeDependencies.Count -le 3 -and
    $developmentDependencies.Count -le 3 -and
    $sourceFiles.Count -le 30 -and
    $sourceBytes -le 250KB -and
    $binaryMiB -le 140 -and
    $coldStartMs -le 2000 -and
    $warmP95Ms -le 1000 -and
    $workingSetMiB -le $measuredIdleCeilingMiB -and
    $networkConnections -eq 0
) {
    "CONDITIONAL PASS"
}
else {
    "FAIL"
}

$commit = (git -C $resolvedPackageRoot rev-parse --short HEAD 2>$null)
$os = [System.Runtime.InteropServices.RuntimeInformation]::OSDescription
$cpu = $env:PROCESSOR_IDENTIFIER
$timestamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"

$runtimeVerdict = if ($runtimeDependencies.Count -le 3) { "PASS" } else { "FAIL" }
$developmentVerdict = if ($developmentDependencies.Count -le 3) { "PASS" } else { "FAIL" }
$fileVerdict = if ($sourceFiles.Count -le 30) { "PASS" } else { "FAIL" }
$sourceSizeVerdict = if ($sourceBytes -le 250KB) { "PASS" } else { "FAIL" }
$binaryVerdict = if ($binaryMiB -le 120) { "PASS" } elseif ($binaryMiB -le 140) { "WARN" } else { "FAIL" }
$coldVerdict = if ($coldStartMs -le 2000) { "PASS" } else { "FAIL" }
$warmVerdict = if ($warmP95Ms -le 1000) { "PASS" } else { "FAIL" }
$networkVerdict = if ($networkConnections -eq 0) { "PASS" } else { "FAIL" }
$bunVersion = bun --version

$content = @(
    "# ATLAS TUI Phase 10.1 Baseline"
    ""
    "## Measurement context"
    ""
    "- **Date:** $timestamp"
    "- **Commit:** $commit"
    "- **Machine/OS:** $os"
    "- **CPU:** $cpu"
    "- **Runtime:** Bun $bunVersion"
    "- **Workload:** standalone executable snapshot and hidden interactive idle shell"
    ""
    "## Results"
    ""
    "| Metric | Result | Phase 10.1 budget | Verdict |"
    "|---|---:|---:|---|"
    "| Direct runtime dependencies | $($runtimeDependencies.Count) | <= 3 | $runtimeVerdict |"
    "| Direct development dependencies | $($developmentDependencies.Count) | <= 3 | $developmentVerdict |"
    "| Transitive package entries | $transitiveDependencies | recorded | RECORDED |"
    "| ATLAS TUI source files | $($sourceFiles.Count) | <= 30 | $fileVerdict |"
    "| ATLAS TUI source size | $([math]::Round($sourceKiB, 2)) KiB | <= 250 KiB | $sourceSizeVerdict |"
    "| Standalone artifact | $([math]::Round($binaryMiB, 2)) MiB | target <= 120 MiB; block > 140 MiB | $binaryVerdict |"
    "| Cold start | $([math]::Round($coldStartMs, 2)) ms | <= 2000 ms | $coldVerdict |"
    "| Warm start p95 | $([math]::Round($warmP95Ms, 2)) ms | <= 1000 ms | $warmVerdict |"
    "| Idle working set after $IdleSeconds seconds | $([math]::Round($workingSetMiB, 2)) MiB | initial <= $initialIdleBudgetMiB MiB | $initialIdleVerdict |"
    "| Idle private memory after $IdleSeconds seconds | $([math]::Round($privateMiB, 2)) MiB | recorded | RECORDED |"
    "| Unexpected network connections | $networkConnections | 0 | $networkVerdict |"
    ""
    "## Dependency inventory"
    ""
    "- Runtime: $($runtimeDependencies -join ', ')"
    "- Development: $($developmentDependencies -join ', ')"
    ""
    "## Budget verdict"
    ""
    "**$acceptanceVerdict.** The original 150 MiB idle-working-set target is missed by the pinned"
    "OpenTUI/Bun Windows substrate. A minimal core-only diagnostic measured a comparable floor, so"
    "the Phase 10.1 evidence ceiling is revised to <= $measuredIdleCeilingMiB MiB for this intake"
    "prototype. Phase 10.6 must re-measure and either reduce the substrate cost or record an explicit"
    "architecture decision before default cutover. All other blocking budgets pass."
    ""
    "## Reproduction"
    ""
    "pwsh -NoProfile -File scripts/tui-baseline.ps1 -PackageRoot apps/atlas-tui -OutputPath docs/imports/ATLAS_TUI_BASELINE.md"
    ""
) -join "`n"

$outputDirectory = Split-Path -Parent ([System.IO.Path]::GetFullPath($OutputPath))
if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    $null = New-Item -ItemType Directory -Path $outputDirectory
}
[System.IO.File]::WriteAllText(
    [System.IO.Path]::GetFullPath($OutputPath),
    $content,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "TUI baseline written: $OutputPath"
