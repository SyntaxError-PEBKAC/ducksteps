# scripts/

## build_and_release.ps1

Automates the ducksteps manual release flow on Windows:
- build (`mach clobber/configure/build`)
- package installer + standalone archive
- generate `ducksteps-<ver>-Setup.exe` and `ducksteps-<ver>-Standalone.7z` in `dist/`
- generate `dist/RELEASE_NOTES.md`
- write a full timestamped log to `dist/logs/`
- create git tag
- create a draft GitHub Release and upload both files

### Usage

```powershell
# Normal run (build + publish draft release)
.\scripts\build_and_release.ps1

# Force a version label for release artifacts/tag/release
.\scripts\build_and_release.ps1 -Version 140.8.0

# Show actions only (no command execution)
.\scripts\build_and_release.ps1 -DryRun

# Build/package only (skip tag + GitHub release)
.\scripts\build_and_release.ps1 -NoPublish

# If build fails, create fix branch + minimal safe edits (scripts/docs), retry once, then stop
.\scripts\build_and_release.ps1 -AttemptFix
```

### Before first run

Edit the config block at the top of `build_and_release.ps1`:
- `SourceRoot`, `ObjDir`, `DistDir`, `LogsDir`
- `MozBuildBash`, `SevenZipExe`
- `GitHubRepoOwner`, `GitHubRepoName`
- naming/tag patterns if needed

If your local `upx` does not support `--ultra-brute`, adjust `UpxArgs` in config.

## generate_release_notes.ps1

Creates `dist/RELEASE_NOTES.md` for a given version in a casual devlog style.

```powershell
.\scripts\generate_release_notes.ps1 -Version 140.8.0 -DistDir D:\ducksteps-obj\esr140\dist -SourceRoot D:\mozilla-source\ducksteps -IncludeCommits
```

## check_esr_update.ps1

Checks Mozilla ESR metadata and triggers a build only when ESR changed.

What it does:
- fetches `https://product-details.mozilla.org/1.0/firefox_versions.json`
- reads `FIREFOX_ESR` and `FIREFOX_ESR_NEXT`
- normalizes trailing `esr` suffix (e.g. `140.8.0esr` -> `140.8.0`)
- compares against `LAST_BUILT_ESR.txt` in repo root
- runs `build_and_release.ps1 -Version <new>` only on change
- writes logs to `dist/logs/esr-watcher.log`
- uses a lock file to avoid concurrent runs

```powershell
# default: build + draft release (not a final published release)
.\scripts\check_esr_update.ps1

# check only / no side effects
.\scripts\check_esr_update.ps1 -DryRun

# build only if ESR changed, skip tag/release creation
.\scripts\check_esr_update.ps1 -NoPublish
```

## triage_build_log.ps1

Reads a build log and prints:
- the most likely error block(s)
- a plain-English explanation
- a checklist of likely fixes

```powershell
.\scripts\triage_build_log.ps1 -LogPath D:\ducksteps-obj\esr140\dist\logs\build-20260208-010000.log
```
