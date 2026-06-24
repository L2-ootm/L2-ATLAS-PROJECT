[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$generator = Join-Path $PSScriptRoot "tui-source-inventory.ps1"
$sourceRoot = Join-Path $repoRoot "_EXTERNAL_REPOS/mimo-code/packages/opencode/src/cli/cmd/tui"
$reviewedInventory = Join-Path $repoRoot "docs/imports/ATLAS_TUI_SOURCE_INVENTORY.csv"
$packageFile = Join-Path $repoRoot "apps/atlas-tui/package.json"
$scanner = Join-Path $PSScriptRoot "tui-boundary-check.ps1"
$terms = Join-Path $repoRoot "docs/third-party/atlas-tui-forbidden-terms.txt"
$expectedCommit = "86d95a79bf0879bcb442ffe6b12914f6d8e68a4e"
$approvedDependencies = @("@opentui/core", "@opentui/solid", "solid-js")

if (-not (Test-Path -LiteralPath $generator -PathType Leaf)) {
    throw "Inventory generator is missing: $generator"
}
if (-not (Test-Path -LiteralPath $packageFile -PathType Leaf)) {
    throw "ATLAS TUI package metadata is missing: $packageFile"
}

$tempOutput = Join-Path ([System.IO.Path]::GetTempPath()) "atlas-tui-inventory-$([guid]::NewGuid()).csv"
$tempSource = Join-Path ([System.IO.Path]::GetTempPath()) "atlas-tui-source-$([guid]::NewGuid())"
$tempNewOutput = Join-Path ([System.IO.Path]::GetTempPath()) "atlas-tui-new-$([guid]::NewGuid()).csv"
try {
    & pwsh -NoProfile -File $generator `
        -SourceRoot $sourceRoot `
        -SourceCommit $expectedCommit `
        -OutputCsv $tempOutput `
        -ReviewedCsv $reviewedInventory
    if ($LASTEXITCODE -ne 0) {
        throw "Inventory generator failed with exit code $LASTEXITCODE"
    }

    $expected = @(Import-Csv -LiteralPath $reviewedInventory)
    $actual = @(Import-Csv -LiteralPath $tempOutput)
    if ($actual.Count -ne 180 -or $actual.Count -ne $expected.Count) {
        throw "Inventory row count mismatch: expected 180, got $($actual.Count)"
    }
    for ($index = 0; $index -lt $expected.Count; $index++) {
        foreach ($field in @("source_path", "sha256", "size_bytes")) {
            if ($actual[$index].$field -ne $expected[$index].$field) {
                throw "Inventory mismatch at row $index field $field"
            }
        }
    }

    $null = New-Item -ItemType Directory -Path $tempSource
    [System.IO.File]::WriteAllText((Join-Path $tempSource "new-file.txt"), "new source")
    & pwsh -NoProfile -File $generator `
        -SourceRoot $tempSource `
        -SourceCommit $expectedCommit `
        -OutputCsv $tempNewOutput `
        -ReviewedCsv $reviewedInventory
    if ($LASTEXITCODE -ne 0) {
        throw "Inventory generator failed for new-source fixture"
    }
    $newRow = Import-Csv -LiteralPath $tempNewOutput | Select-Object -First 1
    if ($newRow.classification -ne "unclassified") {
        throw "New source did not fail closed as unclassified"
    }

    $package = Get-Content -Raw -LiteralPath $packageFile | ConvertFrom-Json
    $runtimeNames = @($package.dependencies.PSObject.Properties.Name | Sort-Object)
    $expectedNames = @($approvedDependencies | Sort-Object)
    if (($runtimeNames -join "`n") -ne ($expectedNames -join "`n")) {
        throw "Runtime dependency set differs from the approved three-package boundary"
    }
    if ($package.dependencies."@opentui/core" -ne "0.1.101") {
        throw "@opentui/core is not pinned to 0.1.101"
    }
    if ($package.dependencies."@opentui/solid" -ne "0.1.101") {
        throw "@opentui/solid is not pinned to 0.1.101"
    }
    if ($package.dependencies."solid-js" -ne "1.9.10") {
        throw "solid-js is not pinned to 1.9.10"
    }
    if (@($package.devDependencies.PSObject.Properties.Name).Count -gt 3) {
        throw "Development dependency ceiling exceeded"
    }

    & pwsh -NoProfile -File $scanner `
        -Root (Join-Path $repoRoot "apps/atlas-tui") `
        -ForbiddenTermsFile $terms
    if ($LASTEXITCODE -ne 0) {
        throw "Boundary scanner rejected the package skeleton"
    }
}
finally {
    Remove-Item -LiteralPath $tempOutput -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempNewOutput -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tempSource -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "Inventory and package-boundary contract tests passed."
