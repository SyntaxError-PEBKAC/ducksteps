[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$Version,
    [Parameter(Mandatory)] [string]$DistDir,
    [Parameter(Mandatory)] [string]$SourceRoot,
    [string]$GitExe = 'git',
    [switch]$Tested,
    [switch]$InstallerReady,
    [switch]$StandaloneReady,
    [switch]$IncludeCommits
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

New-Item -ItemType Directory -Path $DistDir -Force | Out-Null
$notesPath = Join-Path $DistDir 'RELEASE_NOTES.md'
$buildDate = Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'

$testedMark = if ($Tested) { '[x]' } else { '[ ]' }
$installerMark = if ($InstallerReady) { '[x]' } else { '[ ]' }
$standaloneMark = if ($StandaloneReady) { '[x]' } else { '[ ]' }

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("🚀 It's the `"$Version - duck did the thing`" release:")
$lines.Add('')
$lines.Add("📦  Built ducksteps $Version on $buildDate.")
$lines.Add('🧪  Ran the release checklist and logged the rough edges like a responsible goblin.')
$lines.Add('⚙️  Configured build settings to match the current release runbook (LTO/PGO/branding/toolchain).')
$lines.Add('🗜️  Compressed release artifacts for shipping (UPX on installer, 7z for standalone package).')
$lines.Add('')
$lines.Add('## Quick checklist')
$lines.Add("- $testedMark Tested build launch")
$lines.Add("- $installerMark Installer artifact ready (.exe)")
$lines.Add("- $standaloneMark Standalone artifact ready (.7z)")
$lines.Add('')
$lines.Add('## Changes in ducksteps')
$lines.Add('- 🛠️  Placeholder: I did work, and I should describe the actual user-visible changes here before publishing.')
$lines.Add('- 🐤  Placeholder: If something is still rough, I should say it plainly instead of pretending it is polished.')

if ($IncludeCommits) {
    $tags = @()
    try {
        $tags = & $GitExe -C $SourceRoot tag --sort=-creatordate
    }
    catch {
        $tags = @()
    }

    if ($tags.Count -ge 2) {
        $currentTag = $tags[0]
        $previousTag = $tags[1]
        $commitLines = @()
        try {
            $commitLines = & $GitExe -C $SourceRoot log --pretty=format:'- %h %s' "$previousTag..$currentTag"
        }
        catch {
            $commitLines = @()
        }

        $lines.Add('')
        $lines.Add('## Commits since previous tag')
        $lines.Add("- Previous tag: $previousTag")
        $lines.Add("- Current tag: $currentTag")

        if ($commitLines.Count -gt 0) {
            foreach ($entry in $commitLines) {
                if ([string]::IsNullOrWhiteSpace($entry)) { continue }
                $lines.Add($entry)
            }
        }
        else {
            $lines.Add('- (No commits found in tag range, or git log not available.)')
        }
    }
    else {
        $lines.Add('')
        $lines.Add('## Commits since previous tag')
        $lines.Add('- Not enough tags yet to build a previous-vs-current commit list.')
    }
}

Set-Content -Path $notesPath -Value $lines -Encoding UTF8
Write-Host "Wrote release notes: $notesPath"
