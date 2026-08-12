<#
.SYNOPSIS
    One iteration of the ATLAS autonomous loop: a clean headless Claude Code
    session that picks and completes the next most high-leverage task.

.DESCRIPTION
    Registered as a Windows scheduled task by register-autonomous-loop.ps1 and
    fired every 2 hours. Each iteration is a fresh session with no inherited
    context — the standing prompt in autonomous-loop-prompt.md tells it how to
    reload state from HANDOFF.md, .planning/, and the previous iteration's log.

    A lock file prevents overlap: a long iteration is left alone rather than
    having a second agent start editing the same working tree underneath it.

.PARAMETER TimeoutMinutes
    Hard ceiling for one iteration. The lock is treated as stale past this.
#>
[CmdletBinding()]
param(
    [int]$TimeoutMinutes = 100
)

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$PromptFile = Join-Path $PSScriptRoot 'autonomous-loop-prompt.md'
$LoopDir = Join-Path $RepoRoot '.ops\loop'
$LogDir = Join-Path $LoopDir 'logs'
$LockFile = Join-Path $LoopDir 'loop.lock'

if (-not (Test-Path $PromptFile)) {
    throw "Standing prompt not found: $PromptFile"
}
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# --- Overlap guard -------------------------------------------------------
# Two agents editing one working tree concurrently is the failure mode worth
# spending a lock on. A lock older than the timeout is assumed to belong to a
# crashed iteration and is reclaimed.
if (Test-Path $LockFile) {
    $lockAge = (Get-Date) - (Get-Item $LockFile).LastWriteTime
    if ($lockAge.TotalMinutes -lt $TimeoutMinutes) {
        Write-Host "Iteration already running (lock is $([int]$lockAge.TotalMinutes)m old). Skipping."
        exit 0
    }
    Write-Host "Reclaiming stale lock ($([int]$lockAge.TotalMinutes)m old)."
    Remove-Item $LockFile -Force
}

$stamp = Get-Date -Format 'yyyy-MM-dd_HHmmss'
$logFile = Join-Path $LogDir "$stamp.log"
Set-Content -Path $LockFile -Value "pid=$PID started=$stamp" -Encoding utf8

try {
    Set-Location $RepoRoot
    $prompt = Get-Content $PromptFile -Raw

    "=== ATLAS autonomous loop — $stamp ===" | Tee-Object -FilePath $logFile
    "repo: $RepoRoot" | Tee-Object -FilePath $logFile -Append
    "head: $(git rev-parse --short HEAD)" | Tee-Object -FilePath $logFile -Append
    "" | Tee-Object -FilePath $logFile -Append

    # --dangerously-skip-permissions is required for an unattended run: there is
    # no operator present to approve tool calls. The blast radius is bounded by
    # the hard rules in the standing prompt (no force-push, no history rewrite,
    # no writes outside the repo) and by this being the operator's own machine
    # and own repository, at the operator's explicit instruction.
    & claude --print --dangerously-skip-permissions $prompt 2>&1 |
        Tee-Object -FilePath $logFile -Append

    $exit = $LASTEXITCODE
    "" | Tee-Object -FilePath $logFile -Append
    "=== iteration exit=$exit finished=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" |
        Tee-Object -FilePath $logFile -Append
}
finally {
    Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
    # Keep the last 40 iterations; the standing prompt only reads the newest.
    Get-ChildItem $LogDir -Filter '*.log' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip 40 |
        Remove-Item -Force -ErrorAction SilentlyContinue
}
