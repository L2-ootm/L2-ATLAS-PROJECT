[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,

    [Parameter(Mandatory = $true)]
    [string]$SourceCommit,

    [Parameter(Mandatory = $true)]
    [string]$OutputCsv,

    [string]$ReviewedCsv
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
    throw "Source root does not exist: $SourceRoot"
}
if ([string]::IsNullOrWhiteSpace($SourceCommit)) {
    throw "Source commit must be explicit"
}

$resolvedSourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$reviewPath = if ($ReviewedCsv) {
    $ReviewedCsv
}
elseif (Test-Path -LiteralPath $OutputCsv -PathType Leaf) {
    $OutputCsv
}
else {
    $null
}

$reviewedByPath = @{}
if ($reviewPath) {
    if (-not (Test-Path -LiteralPath $reviewPath -PathType Leaf)) {
        throw "Reviewed CSV does not exist: $reviewPath"
    }
    foreach ($row in Import-Csv -LiteralPath $reviewPath) {
        if (-not $row.source_path) {
            throw "Reviewed CSV contains a row without source_path: $reviewPath"
        }
        $reviewedByPath[$row.source_path] = $row
    }
}

$rows = foreach ($file in Get-ChildItem -LiteralPath $resolvedSourceRoot -Recurse -Force -File) {
    $relativePath = [System.IO.Path]::GetRelativePath($resolvedSourceRoot, $file.FullName).
        Replace([System.IO.Path]::DirectorySeparatorChar, "/")
    $reviewed = $reviewedByPath[$relativePath]
    $area = if ($reviewed) {
        $reviewed.area
    }
    elseif ($relativePath.Contains("/")) {
        $relativePath.Split("/")[0]
    }
    else {
        "root"
    }

    [pscustomobject][ordered]@{
        source_commit = $SourceCommit
        source_path = $relativePath
        sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        size_bytes = $file.Length
        area = $area
        classification = if ($reviewed) { $reviewed.classification } else { "unclassified" }
        rationale = if ($reviewed) {
            $reviewed.rationale
        }
        else {
            "New source item requires explicit review before intake."
        }
        atlas_destination = if ($reviewed) { $reviewed.atlas_destination } else { "none" }
    }
}

$rowMap = @{}
[string[]]$sortedPaths = @(
    foreach ($row in $rows) {
        $rowMap[$row.source_path] = $row
        $row.source_path
    }
)
[System.Array]::Sort($sortedPaths, [System.StringComparer]::Ordinal)
$sortedRows = @($sortedPaths | ForEach-Object { $rowMap[$_] })
$outputDirectory = Split-Path -Parent ([System.IO.Path]::GetFullPath($OutputCsv))
if (-not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    $null = New-Item -ItemType Directory -Path $outputDirectory
}

$csvLines = @($sortedRows | ConvertTo-Csv -NoTypeInformation)
[System.IO.File]::WriteAllLines(
    [System.IO.Path]::GetFullPath($OutputCsv),
    $csvLines,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "Inventory written: $OutputCsv ($($sortedRows.Count) files)"
