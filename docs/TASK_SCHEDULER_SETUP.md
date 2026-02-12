# Task Scheduler setup for ducksteps ESR watcher (Windows 11)

This guide shows exactly how to run `scripts/check_esr_update.ps1` on a schedule and on-demand.

## What this gives you

- Daily automatic ESR check (`check_esr_update.ps1`)
- A task you can also run manually at any time
- Logs written by the script to:
  - `D:\ducksteps-obj\esr140\dist\logs\esr-watcher.log`
  - plus full build logs in `D:\ducksteps-obj\esr140\dist\logs\build-*.log`

---

## 0) Prerequisites

1. Confirm your repo and script exist:
   - `D:\mozilla-source\ducksteps\scripts\check_esr_update.ps1`
2. Confirm PowerShell path (default on Windows 11):
   - `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`
3. Confirm `build_and_release.ps1` config is already correct:
   - paths
   - `gh` auth and repo owner/name
   - tool locations

> Note: The watcher script itself handles lock files and ESR version normalization.

---

## 1) Import the provided task XML

The repo includes:
- `scripts/task_esr_watcher.xml`

### Option A — Import in Task Scheduler GUI

1. Open **Task Scheduler**.
2. In the right panel, click **Import Task...**.
3. Select: `D:\mozilla-source\ducksteps\scripts\task_esr_watcher.xml`
4. In the import dialog:
   - Set **Run whether user is logged on or not** (if available).
   - Leave **Do not store password** unchecked if you want background runs.
   - Check **Run with highest privileges** only if you know you need it.
5. Save and enter credentials when prompted.

### Option B — Import from PowerShell

```powershell
schtasks /Create /TN "ducksteps-esr-watcher" /XML "D:\mozilla-source\ducksteps\scripts\task_esr_watcher.xml"
```

You may be prompted for credentials.

---

## 2) Update task account + “run when not logged in”

If possible, use:
- **Run whether user is logged on or not**
- account that has access to:
  - `D:\mozilla-source\ducksteps`
  - `D:\ducksteps-obj\esr140`
  - toolchain binaries and `gh` auth context

### Important behavior notes

- This usually works best with a normal user account + stored password.
- If your build depends on user-only environment/profile settings, background runs can fail until those are made system-visible.
- **Admin rights are not always required** to create a user task, but may be required by your organization’s policy.

---

## 3) Daily schedule + manual run

The provided XML includes:
- Daily trigger at **09:00 local time**
- On-demand/manual run enabled

To run manually anytime:

- Task Scheduler GUI: right-click task → **Run**
- or PowerShell:

```powershell
schtasks /Run /TN "ducksteps-esr-watcher"
```

To stop a stuck run:

```powershell
schtasks /End /TN "ducksteps-esr-watcher"
```

---

## 4) Verify it actually runs

### Quick check command

```powershell
schtasks /Query /TN "ducksteps-esr-watcher" /V /FO LIST
```

Look at:
- **Last Run Time**
- **Last Result**

Common results:
- `0x0` = success
- non-zero = something failed (check logs below)

---

## 5) Where logs and failures are stored

## Script logs (primary)

- ESR watcher summary log:
  - `D:\ducksteps-obj\esr140\dist\logs\esr-watcher.log`
- Build logs (when a build is triggered):
  - `D:\ducksteps-obj\esr140\dist\logs\build-YYYYMMDD-HHMMSS.log`

These are the first place to debug failures.

## Task Scheduler history (secondary)

1. Open task in Task Scheduler.
2. Open **History** tab.
3. Check trigger/action events and action exit codes.

If History is empty, enable it in the right panel:
- **Enable All Tasks History**

---

## 6) What may require admin

Usually does **not** require admin:
- creating a scheduled task for your own account
- running task manually as your own user

May require admin (depends on policy/environment):
- creating tasks under another account
- using highest privileges
- changing task security options in locked-down environments
- writing to protected paths

If you cannot set “Run whether user is logged on or not”, create it as your own user first, verify it works while logged in, then adjust account/security later.

---

## 7) Safe first test flow

1. Run watcher manually once:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\mozilla-source\ducksteps\scripts\check_esr_update.ps1" -DryRun
```

2. Import task.
3. Manually trigger task (`schtasks /Run ...`).
4. Inspect:
   - `esr-watcher.log`
   - newest `build-*.log` (if ESR changed and build started)
5. Only after this, rely on daily schedule.
