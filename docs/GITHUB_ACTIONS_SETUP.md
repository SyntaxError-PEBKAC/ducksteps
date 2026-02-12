# GitHub Actions setup (self-hosted Windows runner)

This repo includes:
- `.github/workflows/esr-self-hosted.yml`

It runs on a **self-hosted Windows runner** and can:
- run `scripts/check_esr_update.ps1` on schedule
- run `scripts/build_and_release.ps1` manually with a version input
- default to `-NoPublish`
- upload installer/standalone/log files as workflow artifacts
- optionally allow draft release publishing when `publish_draft=true`

## Required runner labels

Your runner must match:
- `self-hosted`
- `windows`

## Required tools on runner

Use the same local toolchain you already use:
- PowerShell
- MozillaBuild + Firefox build deps
- Git / gh / upx / 7-Zip

## Required secret(s)

Do **not** commit secrets.

Add repository secret:
- `DUCKSTEPS_GH_TOKEN` (PAT or token usable by `gh` for repo/release operations)

Minimum scopes (typical):
- `repo`

If you only run in `-NoPublish` mode, this token may not be required for build-only runs, but keep it configured so publish mode works.

## How scheduled mode works

- Trigger: daily cron in workflow.
- Path: runs `scripts/check_esr_update.ps1`.
- Default: passes `-NoPublish` (build/package only, no tag/release publish).

## How manual mode works

From **Actions → ESR Watcher + Build (Self-hosted Windows) → Run workflow**:

Inputs:
- `version` (optional):
  - set version (e.g. `140.8.0`) to run `build_and_release.ps1 -Version <value>`
  - leave empty to run `check_esr_update.ps1`
- `publish_draft` (boolean, default `false`):
  - `false`: force `-NoPublish`
  - `true`: allow script publish path (draft release behavior controlled by script config)

## Artifacts uploaded by workflow

- Installer artifact bundle:
  - `D:\ducksteps-obj\esr140\dist\ducksteps-*-Setup.exe`
  - fallback installer pattern from `dist\install\sea`
- Standalone artifact bundle:
  - `D:\ducksteps-obj\esr140\dist\ducksteps-*-Standalone.7z`
  - fallback `.win64.zip`
- Logs bundle:
  - `D:\ducksteps-obj\esr140\dist\logs\*.log`
  - `D:\ducksteps-obj\esr140\dist\RELEASE_NOTES.md`

## Admin note

No extra admin rights are required in git for this workflow file itself.
Self-hosted runner service setup and machine permissions are managed outside this repo and may require admin privileges on the runner machine.
