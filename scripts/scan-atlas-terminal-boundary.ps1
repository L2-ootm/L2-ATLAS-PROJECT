#Requires -Version 7
<#
.SYNOPSIS
    Runs the generic boundary scanner (tui-boundary-check.ps1) against
    services/atlas-terminal with the donor-branding forbidden-terms list.

.DESCRIPTION
    First real wiring of scripts/tui-boundary-check.ps1 since it was
    authored for an earlier, now-removed apps/atlas-tui prototype. Targets
    the wholesale-vendored donor TUI (services/atlas-terminal) so future
    scrub regressions in src/vendor/opencode/** (e.g. the raw MIMO/CODE
    ASCII wordmark found and fixed in logo.ts) are caught mechanically
    instead of only by manual review.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$scanRoot = Join-Path $repoRoot "services/atlas-terminal/src"
$termsFile = Join-Path $repoRoot "scripts/atlas-terminal-forbidden-terms.txt"

& (Join-Path $PSScriptRoot "tui-boundary-check.ps1") `
    -Root $scanRoot `
    -ForbiddenTermsFile $termsFile

exit $LASTEXITCODE
