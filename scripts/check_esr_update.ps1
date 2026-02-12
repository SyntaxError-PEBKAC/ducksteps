[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$NoPublish
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# =========================
# Configuration (edit here)
# =========================
$Config = [ordered]@{
    SourceRoot          = 'D:\mozilla-source\ducksteps'
    DistDir             = 'D:\ducksteps-obj\esr140\dist'
    LogsDir             = 'D:\ducksteps-obj\esr140\dist\logs'

    VersionsUrl         = 'https://product-details.mozilla.org/1.0/firefox_versions.json'
    LastBuiltFileName   = 'LAST_BUILT_ESR.txt'

    BuildScriptPath     = 'scripts\build_and_release.ps1'
    PowerShellExe       = 'powershell'

    # lockfile prevents concurrent watcher runs
    LockFileName        = 'esr-watcher.lock'
    LogFileName         = 'esr-watcher.log'
}

$LastBuiltPath = Join-Path $Config.SourceRoot $Config.LastBuiltFileName
$LockPath = Join-Path $Config.LogsDir $Config.LockFileName
$WatcherLogPath = Join-Path $Config.LogsDir $Config.LogFileName

New-Item -ItemType Directory -Path $Config.LogsDir -Force | Out-Null

function Write-WatcherLog([string]$Text) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[$stamp] $Text"
    Write-Host $line
    Add-Content -Path $WatcherLogPath -Value $line
}

function Normalize-EsrVersion([string]$RawVersion) {
    if ([string]::IsNullOrWhiteSpace($RawVersion)) { return $RawVersion }
    # If Mozilla returns values like 140.8.0esr, normalize to 140.8.0.
    return ($RawVersion -replace '(?i)esr$','').Trim()
}

$lockHandle = $null
try {
    Write-WatcherLog 'Starting ESR watcher run.'
    Write-WatcherLog "DryRun=$DryRun NoPublish=$NoPublish"

    # lock acquisition
    if (Test-Path $LockPath) {
        throw "Another run appears active (lock file exists): $LockPath"
    }
    $lockHandle = [System.IO.File]::Open($LockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    Write-WatcherLog "Acquired lock: $LockPath"

    Write-WatcherLog "Fetching version JSON: $($Config.VersionsUrl)"
    $json = Invoke-RestMethod -Uri $Config.VersionsUrl -Method Get

    $rawCurrent = [string]$json.FIREFOX_ESR
    $rawNext = [string]$json.FIREFOX_ESR_NEXT
    $currentEsr = Normalize-EsrVersion $rawCurrent
    $nextEsr = Normalize-EsrVersion $rawNext

    Write-WatcherLog "FIREFOX_ESR raw='$rawCurrent' normalized='$currentEsr'"
    Write-WatcherLog "FIREFOX_ESR_NEXT raw='$rawNext' normalized='$nextEsr'"

    $lastBuilt = ''
    if (Test-Path $LastBuiltPath) {
        $lastBuilt = Normalize-EsrVersion ((Get-Content -Path $LastBuiltPath -Raw).Trim())
        Write-WatcherLog "LAST_BUILT_ESR current value: '$lastBuilt'"
    } else {
        Write-WatcherLog "LAST_BUILT_ESR file missing; treating as first run: $LastBuiltPath"
    }

    if ($currentEsr -eq $lastBuilt) {
        Write-WatcherLog 'No ESR change detected. Nothing to do.'
        exit 0
    }

    Write-WatcherLog "ESR change detected: '$lastBuilt' -> '$currentEsr'"

    $buildScript = Join-Path $Config.SourceRoot $Config.BuildScriptPath
    if (-not (Test-Path $buildScript)) {
        throw "Build script not found: $buildScript"
    }

    $args = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $buildScript,
        '-Version', $currentEsr
    )
    if ($NoPublish) { $args += '-NoPublish' }
    if ($DryRun) { $args += '-DryRun' }

    Write-WatcherLog "Calling build script: $($Config.PowerShellExe) $($args -join ' ')"
    if (-not $DryRun) {
        & $Config.PowerShellExe @args
        if ($LASTEXITCODE -ne 0) {
            throw "build_and_release.ps1 failed with exit code $LASTEXITCODE"
        }

        Set-Content -Path $LastBuiltPath -Value $currentEsr -Encoding UTF8
        Write-WatcherLog "Updated LAST_BUILT_ESR.txt to '$currentEsr'"
    }
    else {
        Write-WatcherLog 'DRYRUN enabled: skipped build call and LAST_BUILT_ESR update.'
    }

    Write-WatcherLog 'ESR watcher run complete.'
}
catch {
    Write-WatcherLog "ERROR: $($_.Exception.Message)"
    exit 1
}
finally {
    if ($lockHandle) {
        $lockHandle.Close()
        $lockHandle.Dispose()
    }
    if (Test-Path $LockPath) {
        Remove-Item -Path $LockPath -Force -ErrorAction SilentlyContinue
        Write-WatcherLog "Released lock: $LockPath"
    }
}
