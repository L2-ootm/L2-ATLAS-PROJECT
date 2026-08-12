<#
.SYNOPSIS
    Register (or remove) the 2-hourly ATLAS autonomous loop scheduled task.

.EXAMPLE
    pwsh -File scripts/loop/register-autonomous-loop.ps1
    pwsh -File scripts/loop/register-autonomous-loop.ps1 -Unregister
    Get-ScheduledTask -TaskName 'ATLAS-Autonomous-Loop' | Get-ScheduledTaskInfo
#>
[CmdletBinding()]
param(
    [string]$TaskName = 'ATLAS-Autonomous-Loop',
    [int]$IntervalHours = 2,
    [switch]$Unregister
)

$ErrorActionPreference = 'Stop'

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task '$TaskName'."
    return
}

$runner = Join-Path $PSScriptRoot 'run-autonomous-loop.ps1'
if (-not (Test-Path $runner)) { throw "Runner not found: $runner" }

$pwsh = (Get-Command pwsh).Source

$action = New-ScheduledTaskAction -Execute $pwsh `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))

# Start at the next interval boundary rather than immediately, so registering
# the task does not race a session the operator is currently working in.
$start = (Get-Date).AddHours($IntervalHours)
$trigger = New-ScheduledTaskTrigger -Once -At $start `
    -RepetitionInterval (New-TimeSpan -Hours $IntervalHours)

# RunOnlyIfIdle is deliberately NOT set: the loop is meant to make progress
# while the operator is away *or* busy. ExecutionTimeLimit backstops the
# runner's own lock-based timeout.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description 'ATLAS: every 2h, a clean headless Claude Code session works the next most high-leverage task.' `
    -Force | Out-Null

Write-Host "Registered '$TaskName': every $IntervalHours h, first run $start."
Write-Host "Logs: .ops/loop/logs/   Prompt: scripts/loop/autonomous-loop-prompt.md"
