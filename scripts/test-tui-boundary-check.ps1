[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$scanner = Join-Path $PSScriptRoot "tui-boundary-check.ps1"
$terms = Join-Path $repoRoot "docs/third-party/atlas-tui-forbidden-terms.txt"
$allowedRoot = Join-Path $repoRoot "apps/atlas-tui"

if (-not (Test-Path -LiteralPath $scanner -PathType Leaf)) {
    throw "Boundary scanner is missing: $scanner"
}

& pwsh -NoProfile -File $scanner -SelfTest -Root $allowedRoot -ForbiddenTermsFile $terms
if ($LASTEXITCODE -ne 0) {
    throw "Boundary scanner self-test failed with exit code $LASTEXITCODE"
}

$missingTerms = Join-Path ([System.IO.Path]::GetTempPath()) "atlas-missing-terms-$([guid]::NewGuid()).txt"
& pwsh -NoProfile -File $scanner -Root $allowedRoot -ForbiddenTermsFile $missingTerms *> $null
if ($LASTEXITCODE -eq 0) {
    throw "Boundary scanner accepted a missing forbidden-terms file"
}

$emptyTerms = Join-Path ([System.IO.Path]::GetTempPath()) "atlas-empty-terms-$([guid]::NewGuid()).txt"
try {
    [System.IO.File]::WriteAllText($emptyTerms, "")
    & pwsh -NoProfile -File $scanner -Root $allowedRoot -ForbiddenTermsFile $emptyTerms *> $null
    if ($LASTEXITCODE -eq 0) {
        throw "Boundary scanner accepted an empty forbidden-terms file"
    }
}
finally {
    Remove-Item -LiteralPath $emptyTerms -Force -ErrorAction SilentlyContinue
}

Write-Host "Boundary scanner contract tests passed."
