[CmdletBinding()]
param(
    [string]$Version,
    [switch]$DryRun,
    [switch]$NoPublish,
    [switch]$AttemptFix
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# =========================
# Configuration (edit here)
# =========================
$Config = [ordered]@{
    # Core paths
    SourceRoot         = 'D:\mozilla-source\ducksteps'
    ObjDir             = 'D:\ducksteps-obj\esr140'
    DistDir            = 'D:\ducksteps-obj\esr140\dist'
    LogsDir            = 'D:\ducksteps-obj\esr140\dist\logs'

    # MozillaBuild bash launcher (used for ./mach commands)
    MozBuildBash       = 'D:\\mozilla-build\msys2\usr\bin\bash.exe'

    # Tool executables (must already be installed and on this machine)
    SevenZipExe        = 'C:\Program Files\7-Zip\7z.exe'
    UpxExe             = 'upx'
    GhExe              = 'gh'
    GitExe             = 'git'
    PowerShellExe      = 'powershell'

    # Helper scripts
    GenerateNotesScript = 'generate_release_notes.ps1'
    TriageScript        = 'triage_build_log.ps1'

    # Automatic fix-attempt safety guardrails
    AttemptFixAllowedRoots = @('scripts', 'docs')

    # Build command sequence run in MozillaBuild shell
    BuildCommands      = @(
        './mach clobber',
        './mach configure',
        './mach build',
        './mach package',
        './mach installer'
    )

    # Optional smoke-test command (set to $null to disable)
    SmokeTestCommand   = $null

    # UPX settings
    UseUpxOnInstaller  = $true
    UpxArgs            = @('--best', '--lzma', '--ultra-brute')

    # Output naming
    SetupNamePattern      = 'ducksteps-{0}-Setup.exe'
    StandaloneNamePattern = 'ducksteps-{0}-Standalone.7z'

    # Release/tag settings
    TagPattern         = 'ducksteps-{0}'
    ReleaseTitlePattern= 'ducksteps {0}'

    # GitHub target
    GitHubRepoOwner    = 'YOUR_GITHUB_OWNER'
    GitHubRepoName     = 'ducksteps'

    # Release defaults
    ReleaseDraftByDefault = $true
}

$Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
New-Item -ItemType Directory -Path $Config.LogsDir -Force | Out-Null
$LogPath = Join-Path $Config.LogsDir "build-$Timestamp.log"

function Convert-WindowsPathToMsys([string]$Path) {
    if ($Path -match '^[A-Za-z]:\\') {
        $drive = $Path.Substring(0,1).ToLowerInvariant()
        $rest = $Path.Substring(2).Replace('\\','/')
        return "/$drive$rest"
    }
    return $Path
}

$MsysSourceRoot = Convert-WindowsPathToMsys $Config.SourceRoot

function Write-Section([string]$Text) {
    $line = "`n========== $Text =========="
    Write-Host $line
    Add-Content -Path $LogPath -Value $line
}

function Write-Log([string]$Text) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[$stamp] $Text"
    Write-Host $line
    Add-Content -Path $LogPath -Value $line
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(Mandatory)] [string[]]$Arguments,
        [string]$WorkingDirectory
    )

    $display = "$FilePath " + ($Arguments -join ' ')
    Write-Log "RUN: $display"

    if ($DryRun) { return }

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.WorkingDirectory = if ($WorkingDirectory) { $WorkingDirectory } else { (Get-Location).Path }
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    foreach ($arg in $Arguments) { [void]$psi.ArgumentList.Add($arg) }

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi

    [void]$proc.Start()
    while (-not $proc.HasExited) {
        while (($line = $proc.StandardOutput.ReadLine()) -ne $null) {
            Write-Host $line
            Add-Content -Path $LogPath -Value $line
        }
        while (($line = $proc.StandardError.ReadLine()) -ne $null) {
            Write-Host $line
            Add-Content -Path $LogPath -Value $line
        }
        Start-Sleep -Milliseconds 100
    }

    while (($line = $proc.StandardOutput.ReadLine()) -ne $null) {
        Write-Host $line
        Add-Content -Path $LogPath -Value $line
    }
    while (($line = $proc.StandardError.ReadLine()) -ne $null) {
        Write-Host $line
        Add-Content -Path $LogPath -Value $line
    }

    if ($proc.ExitCode -ne 0) {
        throw "Command failed (exit $($proc.ExitCode)): $display"
    }
}

function Get-LikelyCauseSummary {
    if (-not (Test-Path $LogPath)) { return 'No log file found.' }
    $tail = Get-Content $LogPath -Tail 500
    $matches = @()

    if ($tail -match 'No such file or directory|cannot find|not recognized as an internal or external command') {
        $matches += '- Missing executable/path issue (bash, mach, 7z, upx, git, or gh may be missing or wrong).'
    }
    if ($tail -match 'clobber|objdir|stale|config.status') {
        $matches += '- Stale or inconsistent objdir; retry after clobber/clean objdir.'
    }
    if ($tail -match 'MOZ_PGO|profile|instrument') {
        $matches += '- PGO/config mismatch; verify .mozconfig uses ac_add_options MOZ_PGO=1 and rerun configure.'
    }
    if ($tail -match 'LTO|lld-link|clang-cl') {
        $matches += '- Toolchain/LTO issue; verify clang-cl and lld-link are available in build environment.'
    }
    if ($tail -match 'gh auth|authentication failed|HTTP 401|HTTP 403') {
        $matches += '- GitHub CLI auth/permissions issue; run gh auth login and ensure repo access.'
    }

    if ($matches.Count -eq 0) {
        return '- No obvious signature found. Check the last error in the log for the first failing command.'
    }
    return ($matches -join "`n")
}

function Require-File([string]$Path, [string]$Label) {
    if (-not (Test-Path $Path)) {
        throw "$Label not found at: $Path"
    }
}

function Invoke-BuildCommandsOnly {
    Write-Section 'Build + package in MozillaBuild shell'
    foreach ($cmd in $Config.BuildCommands) {
        Invoke-LoggedCommand -FilePath $Config.MozBuildBash -Arguments @('-lc', "cd $MsysSourceRoot && $cmd") -WorkingDirectory $Config.SourceRoot
    }
}

function Invoke-AttemptFixFlow {
    param(
        [string]$FailureMessage
    )

    if (-not $AttemptFix) {
        return $false
    }

    Write-Section 'AttemptFix mode'
    Write-Log 'AttemptFix enabled: creating branch, applying minimal safe edits, and retrying build once.'

    $dateStamp = Get-Date -Format 'yyyyMMdd'
    $branchName = "fix-build-$dateStamp"

    if ($DryRun) {
        Write-Log "DRYRUN would create/switch branch: $branchName"
        Write-Log "DRYRUN would create docs/build-fix-attempt-$dateStamp.md"
        Write-Log 'DRYRUN would rerun build commands once and show git diff.'
        return $true
    }

    # create or switch local branch
    $branchExists = (& $Config.GitExe -C $Config.SourceRoot branch --list $branchName)
    if ([string]::IsNullOrWhiteSpace(($branchExists | Out-String).Trim())) {
        Invoke-LoggedCommand -FilePath $Config.GitExe -Arguments @('-C', $Config.SourceRoot, 'checkout', '-b', $branchName)
    }
    else {
        Invoke-LoggedCommand -FilePath $Config.GitExe -Arguments @('-C', $Config.SourceRoot, 'checkout', $branchName)
    }

    # minimal safe edit (docs/scripts only)
    $safeNotePath = Join-Path $Config.SourceRoot ("docs\build-fix-attempt-$dateStamp.md")
    $safeNote = @"
# Build fix attempt $dateStamp

- Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
- Trigger: build_and_release.ps1 -AttemptFix
- Failure: $FailureMessage
- Safety scope: only docs/scripts edits are allowed by default.

## Next manual action
- Review triage output and this branch diff.
- Adjust scripts/docs only unless you intentionally widen scope.
"@
    Set-Content -Path $safeNotePath -Value $safeNote -Encoding UTF8
    Write-Log "Created minimal safe edit: $safeNotePath"

    # enforce safety scope
    $changedFiles = (& $Config.GitExe -C $Config.SourceRoot diff --name-only) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    foreach ($file in $changedFiles) {
        $allowed = $false
        foreach ($root in $Config.AttemptFixAllowedRoots) {
            if ($file -like "$root/*" -or $file -like "$root\*") { $allowed = $true; break }
        }
        if (-not $allowed) {
            throw "AttemptFix safety violation: changed file outside allowed roots ($($Config.AttemptFixAllowedRoots -join ', ')): $file"
        }
    }

    # re-run build once
    Write-Section 'AttemptFix rebuild (single retry)'
    try {
        Invoke-BuildCommandsOnly
        Write-Log 'AttemptFix rebuild completed successfully.'
    }
    catch {
        Write-Log "AttemptFix rebuild failed: $($_.Exception.Message)"
    }

    # always show diff and stop
    Write-Section 'AttemptFix git diff (review required)'
    & $Config.GitExe -C $Config.SourceRoot status --short | ForEach-Object { Write-Host $_; Add-Content -Path $LogPath -Value $_ }
    & $Config.GitExe -C $Config.SourceRoot diff -- scripts docs | ForEach-Object { Write-Host $_; Add-Content -Path $LogPath -Value $_ }

    Write-Host "`nAttemptFix finished. Review the branch diff and decide next steps manually." -ForegroundColor Yellow
    return $true
}

try {
    Write-Section 'ducksteps build_and_release starting'
    Write-Log "Version=$Version DryRun=$DryRun NoPublish=$NoPublish AttemptFix=$AttemptFix"
    Write-Log "Log path: $LogPath"

    # Basic config validation
    if (-not (Test-Path $Config.SourceRoot)) { throw "SourceRoot does not exist: $($Config.SourceRoot)" }
    if (-not (Test-Path $Config.ObjDir)) { Write-Log "ObjDir does not exist yet (this may be fine on first run): $($Config.ObjDir)" }
    if (-not (Test-Path $Config.MozBuildBash)) { throw "MozBuild bash not found: $($Config.MozBuildBash)" }

    New-Item -ItemType Directory -Path $Config.DistDir -Force | Out-Null
    New-Item -ItemType Directory -Path $Config.LogsDir -Force | Out-Null

    Invoke-BuildCommandsOnly

    if ($Config.SmokeTestCommand) {
        Write-Section 'Optional smoke test'
        Invoke-LoggedCommand -FilePath $Config.MozBuildBash -Arguments @('-lc', "cd $MsysSourceRoot && $($Config.SmokeTestCommand)") -WorkingDirectory $Config.SourceRoot
    }

    Write-Section 'Locate base artifacts'

    $installer = Get-ChildItem (Join-Path $Config.DistDir 'install\sea') -Filter '*.installer.exe' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $installer) {
        $installer = Get-ChildItem (Join-Path $Config.DistDir 'install\sea') -Filter '*.exe' -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
    }
    if (-not $installer) { throw 'Could not find installer .exe under dist\install\sea.' }

    $zip = Get-ChildItem $Config.DistDir -Filter '*.win64.zip' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $zip) {
        $zip = Get-ChildItem $Config.DistDir -Filter '*.zip' -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
    }
    if (-not $zip) { throw 'Could not find standalone zip artifact under dist\.' }

    Write-Log "Found installer: $($installer.FullName)"
    Write-Log "Found zip: $($zip.FullName)"

    # Determine version from override or artifact names: firefox-<ver>.en-US.win64...
    $versionFromArtifacts = $null
    if ($installer.Name -match '^firefox-([0-9][0-9A-Za-z\.-]*)\.en-US\.win64') { $versionFromArtifacts = $Matches[1] }
    if (-not $versionFromArtifacts -and $zip.Name -match '^firefox-([0-9][0-9A-Za-z\.-]*)\.en-US\.win64') { $versionFromArtifacts = $Matches[1] }

    $effectiveVersion = $Version
    if ([string]::IsNullOrWhiteSpace($effectiveVersion)) {
        if (-not $versionFromArtifacts) {
            throw "Could not parse version from artifact names. Installer='$($installer.Name)' Zip='$($zip.Name)'"
        }
        $effectiveVersion = $versionFromArtifacts
        Write-Log "Detected version from artifacts: $effectiveVersion"
    }
    else {
        if ($versionFromArtifacts -and $versionFromArtifacts -ne $effectiveVersion) {
            Write-Log "WARNING: Requested Version '$effectiveVersion' does not match artifact version '$versionFromArtifacts'. Using requested version."
        }
        Write-Log "Using requested version override: $effectiveVersion"
    }

    $setupOut = Join-Path $Config.DistDir ([string]::Format($Config.SetupNamePattern, $effectiveVersion))
    $standaloneOut = Join-Path $Config.DistDir ([string]::Format($Config.StandaloneNamePattern, $effectiveVersion))
    $releaseNotesPath = Join-Path $Config.DistDir 'RELEASE_NOTES.md'

    Write-Section 'Prepare standalone .7z artifact'
    if (-not (Test-Path $Config.SevenZipExe)) { throw "7-Zip executable not found: $($Config.SevenZipExe)" }

    if ($DryRun) {
        Write-Log "DRYRUN copy '$($zip.FullName)' -> '$standaloneOut' via 7z"
    } else {
        if (Test-Path $standaloneOut) { Remove-Item $standaloneOut -Force }
        Invoke-LoggedCommand -FilePath $Config.SevenZipExe -Arguments @('a', '-t7z', '-mx=9', $standaloneOut, $zip.FullName) -WorkingDirectory $Config.DistDir
    }

    Write-Section 'Prepare installer artifact + UPX'
    if ($DryRun) {
        Write-Log "DRYRUN copy '$($installer.FullName)' -> '$setupOut'"
    } else {
        Copy-Item $installer.FullName $setupOut -Force
        Write-Log "Copied installer to: $setupOut"
    }

    if ($Config.UseUpxOnInstaller) {
        $upxArgs = @() + $Config.UpxArgs + @($setupOut)
        Invoke-LoggedCommand -FilePath $Config.UpxExe -Arguments $upxArgs -WorkingDirectory $Config.DistDir
        Invoke-LoggedCommand -FilePath $Config.UpxExe -Arguments @('-t', $setupOut) -WorkingDirectory $Config.DistDir
    }

    Write-Section 'Generate dist/RELEASE_NOTES.md'
    $notesScriptPath = Join-Path $PSScriptRoot $Config.GenerateNotesScript
    if (-not (Test-Path $notesScriptPath)) { throw "Release notes script not found: $notesScriptPath" }

    $notesArgs = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $notesScriptPath,
        '-Version', $effectiveVersion,
        '-DistDir', $Config.DistDir,
        '-SourceRoot', $Config.SourceRoot,
        '-GitExe', $Config.GitExe,
        '-InstallerReady',
        '-StandaloneReady',
        '-IncludeCommits'
    )
    if ($Config.SmokeTestCommand) { $notesArgs += '-Tested' }
    Invoke-LoggedCommand -FilePath $Config.PowerShellExe -Arguments $notesArgs -WorkingDirectory $Config.SourceRoot

    Write-Section 'Tag + draft release publish'
    $tag = [string]::Format($Config.TagPattern, $effectiveVersion)
    $title = [string]::Format($Config.ReleaseTitlePattern, $effectiveVersion)
    $repo = "$($Config.GitHubRepoOwner)/$($Config.GitHubRepoName)"

    if ($NoPublish) {
        Write-Log 'NoPublish is set: skipping git tag/push and GitHub Release creation/upload.'
    } else {
        # Create/push tag
        Invoke-LoggedCommand -FilePath $Config.GitExe -Arguments @('-C', $Config.SourceRoot, 'tag', '-a', $tag, '-m', "ducksteps $effectiveVersion")
        Invoke-LoggedCommand -FilePath $Config.GitExe -Arguments @('-C', $Config.SourceRoot, 'push', 'origin', $tag)

        # Create release (draft by default)
        $releaseArgs = @('release', 'create', $tag, '--repo', $repo, '--title', $title, '--notes-file', $releaseNotesPath)
        if ($Config.ReleaseDraftByDefault) { $releaseArgs += '--draft' }
        $releaseArgs += @($setupOut, $standaloneOut)
        Invoke-LoggedCommand -FilePath $Config.GhExe -Arguments $releaseArgs
    }

    Write-Section 'Success summary'
    Write-Log "Installer output: $setupOut"
    Write-Log "Standalone output: $standaloneOut"
    Write-Log "Build log: $LogPath"
    Write-Log "Release notes: $releaseNotesPath"
    Write-Log "Version: $effectiveVersion"
    if (-not $NoPublish) {
        Write-Log "Tag: $tag"
        Write-Log "GitHub repo target: $repo"
    }

    Write-Host "`nAll done."
}
catch {
    Write-Host "`nERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "`nLast ~200 lines of log ($LogPath):" -ForegroundColor Yellow
    if (Test-Path $LogPath) {
        Get-Content $LogPath -Tail 200 | ForEach-Object { Write-Host $_ }
    } else {
        Write-Host '(log file not found)'
    }

    $triageScriptPath = Join-Path $PSScriptRoot $Config.TriageScript
    Write-Host "`nTriage summary:" -ForegroundColor Yellow
    if ((Test-Path $triageScriptPath) -and (Test-Path $LogPath)) {
        try {
            & $Config.PowerShellExe -NoProfile -ExecutionPolicy Bypass -File $triageScriptPath -LogPath $LogPath
        }
        catch {
            Write-Host "Triage script failed: $($_.Exception.Message)"
            Write-Host "`nLikely cause summary:" -ForegroundColor Yellow
            Write-Host (Get-LikelyCauseSummary)
        }
    }
    else {
        Write-Host 'Triage script or log file missing; falling back to built-in summary.'
        Write-Host "`nLikely cause summary:" -ForegroundColor Yellow
        Write-Host (Get-LikelyCauseSummary)
    }

    $handledByAttemptFix = $false
    try {
        $handledByAttemptFix = Invoke-AttemptFixFlow -FailureMessage $_.Exception.Message
    }
    catch {
        Write-Host "AttemptFix flow failed: $($_.Exception.Message)" -ForegroundColor Red
    }

    if ($handledByAttemptFix) {
        exit 2
    }

    exit 1
}

