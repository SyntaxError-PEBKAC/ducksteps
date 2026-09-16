<#
.SYNOPSIS
  Registers the two ducksteps automation Task Scheduler tasks.

.DESCRIPTION
  "ducksteps watcher"      - polls Mozilla for new releases, 2x daily (9am/5pm), then
                             stays subscribed to the ntfy approve topic until Gate 1 is
                             answered, recording the answer in state.json. Runs whether
                             logged on or not. Never builds anything.
  "ducksteps orchestrator" - runs the actual release pipeline. No automatic trigger:
                             start it manually (Task Scheduler UI "Run", or
                             `schtasks /run /tn "ducksteps orchestrator"`) once you've
                             approved a release from your phone. REQUIRES an unlocked,
                             interactive session - see SCHEDULER.md before the first
                             real build.

  Safe to re-run: uses -Force, so re-running this after changing a path below just
  updates the existing tasks in place rather than erroring.

.PARAMETER WhatIf
  Preview what would be registered without actually creating anything.

.NOTES
  Run this yourself, interactively, as the account that will be logged in during
  builds. It does not need to run elevated - both tasks run at standard ("Limited")
  rights, matching how you already build ducksteps by hand.
#>
[CmdletBinding(SupportsShouldProcess)]
param()

$ErrorActionPreference = "Stop"

# --- Update these if your install locations differ ---
$PythonExe     = "C:\Users\User\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$AutomationDir = "D:\ducksteps\automation"
$StartShell    = "D:\ducksteps\mozilla-build\start-shell.bat"
# -------------------------------------------------------

# The watcher task's S4U logon type (runs whether logged on or not, no stored password)
# requires an elevated session to register - confirmed directly: registering it from a
# non-elevated prompt fails with "Access is denied" partway through, after the
# orchestrator task (which doesn't need elevation) has already been created. Checking
# this up front avoids leaving the two tasks in a half-registered state.
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    throw "Run this from an elevated (Run as Administrator) PowerShell prompt. The watcher task's S4U logon type requires it to register."
}

foreach ($check in @(
    @{ Path = $PythonExe; What = "Python interpreter" },
    @{ Path = $AutomationDir; What = "automation directory" },
    @{ Path = $StartShell; What = "MozillaBuild start-shell.bat" },
    @{ Path = (Join-Path $AutomationDir "watcher.py"); What = "watcher.py" },
    @{ Path = (Join-Path $AutomationDir "orchestrator.py"); What = "orchestrator.py" }
)) {
    if (-not (Test-Path $check.Path)) {
        throw "$($check.What) not found at $($check.Path). Fix the path at the top of this script before running it."
    }
}

# MozillaBuild's own bundled python (used internally for `mach` calls) has neither
# requests nor PyYAML installed, and start-shell.bat defaults to an interactive mintty
# window unless USE_MINTTY=0 is set first - confirmed directly, not assumed. The
# absolute path below sidesteps both: orchestrator.py runs on a known-good interpreter,
# while its own subprocess calls to `python mach build` etc. still correctly resolve
# MozillaBuild's bundled python, since PATH is inherited from the launching shell
# regardless of which interpreter launched orchestrator.py itself.
#
# Verified end to end on 2026-08-14 by running this exact invocation with
# `orchestrator.py --help`: it reached argparse and printed usage, so the -c payload
# survives msys2_shell.cmd's argument parsing intact.
$pythonForwardSlash = $PythonExe -replace '\\', '/'
$orchestratorCommand = "cd /d/ducksteps/automation && '$pythonForwardSlash' orchestrator.py"
$cmdArgs = "/c set USE_MINTTY=0&& `"$StartShell`" -c `"$orchestratorCommand`""

# --- WATCHER task ---
$watcherAction = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "watcher.py" `
    -WorkingDirectory $AutomationDir

$watcherTriggers = @(
    (New-ScheduledTaskTrigger -Daily -At 9:00AM)
    (New-ScheduledTaskTrigger -Daily -At 5:00PM)
)

# 13h, not 10 minutes. The watcher no longer just polls and exits: once it has sent a Gate 1
# notification it stays subscribed to the approve topic until the question is answered, and
# that window is 4 x 3h (the initial ask plus MAX_SNOOZES re-asks) in the worst case. At the
# old 10-minute limit Windows killed the listener while the notification was still sitting
# unread on the phone, which is the whole reason a tapped Approve reached nothing.
#
# MultipleInstances IgnoreNew is kept deliberately. A listening run does suppress the next
# scheduled poll, and that is the right trade: the only thing that poll could discover is a
# release even newer than the one currently waiting for an answer, while two concurrent
# listeners would both record the same decision and both echo a confirmation to the phone.
$watcherSettings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 13)

# S4U: runs whether logged on or not, without storing a Windows password anywhere -
# watcher.py only ever makes outbound HTTPS calls (product-details, GitHub, ntfy),
# none of which need Windows-level network auth, so S4U's limitations don't apply here.
$watcherPrincipal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName "ducksteps watcher" `
    -Action $watcherAction `
    -Trigger $watcherTriggers `
    -Settings $watcherSettings `
    -Principal $watcherPrincipal `
    -Description "Polls Mozilla for new ducksteps-track ESR releases, 2x daily, and listens for the Gate 1 reply. Never builds." `
    -Force

# --- ORCHESTRATOR task ---
# Invariant 2: never "run whether user is logged on or not" here. PGO training needs
# real hardware compositing, which Session 0 (or a locked session) doesn't provide -
# it would silently produce a corrupted profile, not an obvious error.
$orchestratorAction = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument $cmdArgs `
    -WorkingDirectory $AutomationDir

$orchestratorSettings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 24) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

$orchestratorPrincipal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName "ducksteps orchestrator" `
    -Action $orchestratorAction `
    -Settings $orchestratorSettings `
    -Principal $orchestratorPrincipal `
    -Description "Runs the ducksteps release pipeline. Manual start only - see SCHEDULER.md. Requires an unlocked, interactive session (Invariant 2)." `
    -Force

Write-Host ""
Write-Host "Registered 'ducksteps watcher' (daily 9:00 AM / 5:00 PM) and 'ducksteps orchestrator' (manual start only)."
Write-Host "Read SCHEDULER.md before the first real build."
