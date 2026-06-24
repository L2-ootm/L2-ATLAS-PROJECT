[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Root,

    [Parameter(Mandatory = $true)]
    [string]$ForbiddenTermsFile,

    [string[]]$ApprovedDocumentationRoots = @(),

    [string[]]$DependencyAllowlist = @(),

    [switch]$SelfTest
)

$ErrorActionPreference = "Stop"

function Resolve-ExistingPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Label,

        [switch]$Leaf
    )

    $pathType = if ($Leaf) { "Leaf" } else { "Container" }
    if (-not (Test-Path -LiteralPath $Path -PathType $pathType)) {
        throw "$Label does not exist or has the wrong type: $Path"
    }

    return (Resolve-Path -LiteralPath $Path).Path
}

function Get-ForbiddenTerms {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = Resolve-ExistingPath -Path $Path -Label "Forbidden terms file" -Leaf
    $terms = @(
        Get-Content -LiteralPath $resolved |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -and -not $_.StartsWith("#") } |
            Sort-Object -Unique
    )
    if ($terms.Count -eq 0) {
        throw "Forbidden terms file contains no active rules: $resolved"
    }
    return $terms
}

function Test-IsApprovedPath {
    param(
        [Parameter(Mandatory = $true)][string]$Candidate,
        [AllowEmptyCollection()][string[]]$ApprovedRoots
    )

    $candidatePath = [System.IO.Path]::GetFullPath($Candidate)
    foreach ($approvedRoot in $ApprovedRoots) {
        $rootPath = [System.IO.Path]::GetFullPath($approvedRoot).TrimEnd(
            [System.IO.Path]::DirectorySeparatorChar,
            [System.IO.Path]::AltDirectorySeparatorChar
        )
        if (
            $candidatePath.Equals($rootPath, [System.StringComparison]::OrdinalIgnoreCase) -or
            $candidatePath.StartsWith(
                "$rootPath$([System.IO.Path]::DirectorySeparatorChar)",
                [System.StringComparison]::OrdinalIgnoreCase
            )
        ) {
            return $true
        }
    }
    return $false
}

function Get-ContentFindings {
    param(
        [Parameter(Mandatory = $true)][string]$ScanRoot,
        [Parameter(Mandatory = $true)][string[]]$Terms,
        [AllowEmptyCollection()][string[]]$ApprovedRoots
    )

    $findings = [System.Collections.Generic.List[object]]::new()
    $rg = Get-Command rg -ErrorAction SilentlyContinue
    if (-not $rg) {
        throw "ripgrep is required for byte-safe boundary scanning"
    }

    foreach ($term in $Terms) {
        $output = & $rg.Source `
            --hidden `
            --no-ignore `
            --text `
            --fixed-strings `
            --line-number `
            --column `
            --no-heading `
            --color never `
            --glob "!**/node_modules/**" `
            --glob "!**/.git/**" `
            -- `
            $term `
            $ScanRoot 2>$null
        $exitCode = $LASTEXITCODE
        if ($exitCode -gt 1) {
            throw "ripgrep failed while scanning rule '$term' with exit code $exitCode"
        }

        foreach ($line in @($output)) {
            if (-not $line) {
                continue
            }
            $match = [regex]::Match($line, "^(.*?):(\d+):(\d+):(.*)$")
            if (-not $match.Success) {
                continue
            }
            $matchedPath = [System.IO.Path]::GetFullPath($match.Groups[1].Value)
            if (Test-IsApprovedPath -Candidate $matchedPath -ApprovedRoots $ApprovedRoots) {
                continue
            }
            $findings.Add([pscustomobject]@{
                Path = $matchedPath
                Line = [int]$match.Groups[2].Value
                Column = [int]$match.Groups[3].Value
                Rule = $term
            })
        }
    }
    return $findings
}

function Get-DependencyFindings {
    param(
        [Parameter(Mandatory = $true)][string]$ScanRoot,
        [Parameter(Mandatory = $true)][string[]]$Terms,
        [AllowEmptyCollection()][string[]]$Allowlist
    )

    $findings = [System.Collections.Generic.List[object]]::new()
    $packageFiles = Get-ChildItem -LiteralPath $ScanRoot -Recurse -Force -File -Filter "package.json" |
        Where-Object { $_.FullName -notmatch "[\\/]node_modules[\\/]" }

    foreach ($packageFile in $packageFiles) {
        try {
            $package = Get-Content -Raw -LiteralPath $packageFile.FullName | ConvertFrom-Json
        }
        catch {
            throw "Unreadable package metadata: $($packageFile.FullName): $($_.Exception.Message)"
        }

        $sections = @("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
        foreach ($section in $sections) {
            $entries = $package.$section
            if (-not $entries) {
                continue
            }
            foreach ($dependency in $entries.PSObject.Properties.Name) {
                $matchedRule = $Terms | Where-Object {
                    $dependency.Contains($_, [System.StringComparison]::Ordinal)
                } | Select-Object -First 1
                if ($matchedRule) {
                    $findings.Add([pscustomobject]@{
                        Path = $packageFile.FullName
                        Line = 1
                        Column = 1
                        Rule = "dependency:$matchedRule"
                    })
                    continue
                }
                if ($Allowlist.Count -gt 0 -and $dependency -notin $Allowlist) {
                    $findings.Add([pscustomobject]@{
                        Path = $packageFile.FullName
                        Line = 1
                        Column = 1
                        Rule = "dependency-not-allowed:$dependency"
                    })
                }
            }
        }
    }
    return $findings
}

function Invoke-BoundaryScan {
    param(
        [Parameter(Mandatory = $true)][string]$ScanRoot,
        [Parameter(Mandatory = $true)][string[]]$Terms,
        [AllowEmptyCollection()][string[]]$ApprovedRoots,
        [AllowEmptyCollection()][string[]]$Allowlist
    )

    $contentFindings = Get-ContentFindings `
        -ScanRoot $ScanRoot `
        -Terms $Terms `
        -ApprovedRoots $ApprovedRoots
    $dependencyFindings = Get-DependencyFindings `
        -ScanRoot $ScanRoot `
        -Terms $Terms `
        -Allowlist $Allowlist
    return @($contentFindings) + @($dependencyFindings)
}

try {
    $resolvedRoot = Resolve-ExistingPath -Path $Root -Label "Scan root"
    $terms = Get-ForbiddenTerms -Path $ForbiddenTermsFile
    $approvedRoots = @(
        foreach ($approvedRoot in $ApprovedDocumentationRoots) {
            Resolve-ExistingPath -Path $approvedRoot -Label "Approved documentation root"
        }
    )

    if ($SelfTest) {
        $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) "atlas-boundary-$([guid]::NewGuid())"
        try {
            $null = New-Item -ItemType Directory -Path $tempRoot
            $forbiddenFixture = Join-Path $tempRoot "forbidden.bin"
            [System.IO.File]::WriteAllBytes(
                $forbiddenFixture,
                [System.Text.Encoding]::UTF8.GetBytes("prefix$($terms[0])suffix")
            )
            $redFindings = Invoke-BoundaryScan `
                -ScanRoot $tempRoot `
                -Terms $terms `
                -ApprovedRoots @() `
                -Allowlist @()
            if ($redFindings.Count -eq 0) {
                throw "Self-test RED case did not detect the generated forbidden fixture"
            }

            Remove-Item -LiteralPath $forbiddenFixture -Force
            [System.IO.File]::WriteAllText(
                (Join-Path $tempRoot "allowed.txt"),
                "ATLAS boundary scanner fixture."
            )
            $greenFindings = Invoke-BoundaryScan `
                -ScanRoot $tempRoot `
                -Terms $terms `
                -ApprovedRoots @() `
                -Allowlist @()
            if ($greenFindings.Count -ne 0) {
                throw "Self-test GREEN case produced findings"
            }
        }
        finally {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    $findings = Invoke-BoundaryScan `
        -ScanRoot $resolvedRoot `
        -Terms $terms `
        -ApprovedRoots $approvedRoots `
        -Allowlist $DependencyAllowlist
    if ($findings.Count -gt 0) {
        foreach ($finding in $findings) {
            Write-Error (
                "{0}:{1}:{2}: boundary rule '{3}' matched" -f
                $finding.Path,
                $finding.Line,
                $finding.Column,
                $finding.Rule
            )
        }
        exit 1
    }

    Write-Host "Boundary scan passed: $resolvedRoot"
    exit 0
}
catch {
    Write-Error $_
    exit 2
}
