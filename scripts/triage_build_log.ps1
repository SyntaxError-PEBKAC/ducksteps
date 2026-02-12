[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$LogPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not (Test-Path $LogPath)) {
    throw "Log file not found: $LogPath"
}

$lines = Get-Content -Path $LogPath
if (-not $lines -or $lines.Count -eq 0) {
    Write-Host 'No log content found.'
    exit 0
}

$patterns = @(
    @{ Name='tool-missing'; Regex='No such file or directory|cannot find|not recognized as an internal or external command|Command failed'; Explanation='A required executable or path is missing (mach/bash/7z/upx/git/gh), or a command failed immediately.'; Fixes=@('Check configured executable paths at top of build_and_release.ps1.','Verify MozillaBuild bash, 7-Zip, UPX, git, and gh are installed.','Run the failing command manually in the same shell context to confirm PATH and permissions.') },
    @{ Name='objdir-stale'; Regex='clobber|objdir|config.status|stale'; Explanation='Build state looks stale/inconsistent across source, objdir, or configuration outputs.'; Fixes=@('Run ./mach clobber, then ./mach configure and ./mach build again.','If that fails, remove the objdir and rebuild from configure.','Confirm MOZ_OBJDIR points to the expected ESR-specific path.') },
    @{ Name='pgo'; Regex='MOZ_PGO|profile|instrument'; Explanation='PGO-related settings or profile/instrumentation steps may be inconsistent.'; Fixes=@('Confirm .mozconfig uses: ac_add_options MOZ_PGO=1 (not mk_add_options).','Re-run ./mach configure after any .mozconfig edits.','Check about:buildconfig or config.status to confirm MOZ_PGO is active.') },
    @{ Name='toolchain'; Regex='LTO|lld-link|clang-cl|linker'; Explanation='Compiler/linker setup failed (clang-cl/lld-link/LTO mismatch or missing toolchain).'; Fixes=@('Verify CC/CXX/LINKER/HOST_LINKER values in .mozconfig.','Confirm clang-cl and lld-link are available from your build environment.','Try a clean configure/build after validating toolchain paths.') },
    @{ Name='gh-auth'; Regex='gh auth|authentication failed|HTTP 401|HTTP 403|insufficient scopes'; Explanation='GitHub CLI auth or permission issue blocked tag/release publication.'; Fixes=@('Run gh auth status and gh auth login.','Ensure token scopes include repo/release access.','Re-run build with -NoPublish to isolate build vs publish failures.') }
)

$hits = New-Object System.Collections.Generic.List[object]
for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    foreach ($p in $patterns) {
        if ($line -match $p.Regex) {
            $start = [Math]::Max(0, $i - 6)
            $end = [Math]::Min($lines.Count - 1, $i + 6)
            $block = ($lines[$start..$end] -join "`n")
            $hits.Add([pscustomobject]@{
                Score = $i
                Pattern = $p
                Index = $i
                Block = $block
                TriggerLine = $line
            })
            break
        }
    }
}

# Fallback: use trailing lines if no pattern matched
if ($hits.Count -eq 0) {
    $tailStart = [Math]::Max(0, $lines.Count - 80)
    $tailBlock = ($lines[$tailStart..($lines.Count - 1)] -join "`n")

    Write-Host '=== Most likely error block(s) ==='
    Write-Host $tailBlock
    Write-Host "`n=== Plain-English explanation ==="
    Write-Host 'No known signature matched. The failure is likely near the end of the log where the first fatal command appears.'
    Write-Host "`n=== Checklist of likely fixes ==="
    Write-Host '- Re-run the failing command manually from the same shell/environment.'
    Write-Host '- Confirm all tool paths in script config are correct and executable.'
    Write-Host '- If build-state related, clobber/clean objdir and retry.'
    exit 0
}

# pick up to 3 most relevant distinct hits (latest first)
$selected = $hits |
    Sort-Object Index -Descending |
    Select-Object -First 3

Write-Host '=== Most likely error block(s) ==='
$blockNum = 1
foreach ($h in $selected) {
    Write-Host "`n--- Block $blockNum ($($h.Pattern.Name)) ---"
    Write-Host $h.Block
    $blockNum++
}

$top = $selected | Select-Object -First 1
Write-Host "`n=== Plain-English explanation ==="
Write-Host $top.Pattern.Explanation

Write-Host "`n=== Checklist of likely fixes ==="
foreach ($fix in $top.Pattern.Fixes) {
    Write-Host "- $fix"
}
