# Task Scheduler setup

## Read this before the first real build

**The console session must stay unlocked for the entire build.** Sleep and hibernate
must be disabled for the duration; screen-off (monitor sleep) is fine, that doesn't
affect this.

**Why:** Session 0 and locked sessions drop hardware compositing. PGO training drives a
real Firefox window through 88 sites for ~134 minutes to record which code paths
actually run under WebRender and the GPU compositor. Without real compositing, that
window either doesn't render normally or renders through a software fallback path, so
the profile gets recorded, the build finishes, everything *looks* fine, and the
resulting binary is measurably worse in exactly the paths PGO was supposed to optimize.
There's no error, no warning, nothing in the log: the only symptom is a binary that's
quietly worse than it should be. This is exactly why Invariant 2 (never Session 0) and
the orchestrator task's "run only when logged on" setting exist.

In practice: don't lock your session, don't let Windows sleep, and don't RDP into this
machine to run a build (RDP sessions used to force the same GPU-less compositing path
as Session 0; if you ever need remote access during a build, confirm your Windows
build's RDP client actually gives you hardware acceleration before trusting the result).

---

## What gets registered

Running `setup_scheduler.ps1` creates two Task Scheduler tasks:

| Task | Trigger | Runs whether logged on or not? |
|---|---|---|
| `ducksteps watcher` | Daily, 9:00 AM and 5:00 PM | Yes |
| `ducksteps orchestrator` | None (manual start only) | No, requires an interactive logon |

**`ducksteps watcher`** polls Mozilla, decides if there's something new to build, sends
the Gate 1 notification if so, and then **stays subscribed to the approve topic until you
answer it**, recording your answer in `state.json`. It never touches the source tree
beyond a read-only `git ls-remote`. Safe to run unattended, which is why it can run
whether you're logged on or not.

That listening half is what makes the ✅ Approve button do anything. Sending the
notification and exiting - which is what it used to do - left nothing on this machine
subscribed to the topic the button POSTs to, so a tap landed on an empty topic and was
simply gone.

A run that is listening can last up to 12 hours (the initial ask plus three snooze
re-asks, 3 hours apart), so the task's time limit is 13 hours and `MultipleInstances` is
`IgnoreNew`: while one run is waiting for an answer, the next scheduled poll is skipped.
That is deliberate. The only thing that poll could find is a release newer than the one
already waiting on you, and two listeners would both record the decision and both echo a
confirmation to your phone.

Use `python watcher.py --no-listen` for a quick "is there anything new" check that exits
immediately, the way the task used to behave.

### Approving from your phone

Tapping ✅ Approve records the approval and replies with a confirmation. It does **not**
start the build, and nothing here can: PGO training needs a real unlocked interactive
session (Invariant 2). Start the pipeline at the machine when you get to it - it reads the
recorded approval and goes straight to building instead of asking again.

**A tap is not lost if nothing happens to be listening.** ntfy keeps messages for 12
hours, and every gate now subscribes from the moment its question was asked rather than
from the moment the listener happened to start. So an approval given while the PC was
off, mid-reboot, or between watcher runs is picked up by whatever subscribes next, whether
that is the next watcher run or the orchestrator itself. Past 12 hours the message is gone
from ntfy's cache, and the next watcher run simply asks again.

**`ducksteps orchestrator`** runs the actual 10-hour build pipeline. It has **no
automatic trigger on purpose** - start it yourself once you've approved a release from
your phone. If the approval was already recorded it starts building immediately; if it
wasn't (say the watcher was killed mid-wait), it asks Gate 1 itself and will still find a
tap you made within the last 12 hours:

- Task Scheduler UI: right-click "ducksteps orchestrator" -> Run
- Or from an elevated or regular prompt: `schtasks /run /tn "ducksteps orchestrator"`

If a build gets interrupted (reboot, crash, you closed it), don't re-run the task as-is:
open `start-shell.bat` yourself and run `python orchestrator.py --resume` directly. The
registered task always does a fresh start, which correctly refuses to clobber an
in-progress build and will just tell you to use `--resume` instead - resuming from a
random restart isn't a case worth a second scheduled task for.

## Editing the release notes before they go out

**Edit the draft on GitHub. Then tap Publish. That is the whole workflow.**

The notes `render.py` generates are a first draft and are expected to be rewritten - so
far every release has been. Whatever the draft says at the moment you tap ✅ Publish is
what ships: the release body, the `Docs/Changelog.md` entry, and the release commit are
all taken from the draft as it stands at that instant, not from what was generated hours
earlier. The changelog entry is derived from the release body by cutting everything from
the `✅ SHA512:` block down, so the two can't disagree.

Editing the release **title** works the same way. So does editing on a phone: smart
quotes, doubled spaces and em dashes typed into the browser are normalized on the way
out, and the corrected text is written back to the release before it is published, so the
public page and the changelog stay identical.

The Gate 2 notification has three buttons:

| Button | What it does |
|---|---|
| ✅ Publish | Ships the draft as it currently stands. Tags, commits, pushes, opens the discussion. |
| ✏️ Still editing | Buys another `gate_wait_hours` window and re-sends the notification. Up to `gate2_max_extensions` times (default: 7, so about a day). Replies immediately with the editing instructions, since that tap is the last thing that happens before the browser opens. |
| 🛑 Reject | Halts. The draft and its artifacts survive untouched. |

**Save the draft. Never use GitHub's own "Publish release" button.** It is right there on
the page you are editing and it looks like it finishes the job. It does not: it tags the
release at whatever the default branch pointed to when the draft was created, and skips the
changelog entry, the patch-stack export, the docs sync, the release commit and the
discussion. Publishing has to happen through the ✅ Publish button (or `--publish-now`)
so the rest of the pipeline runs. This is the state both of the last two releases had to be
recovered from by hand.

Tap **✏️ Still editing** before you start rewriting anything substantial. The gate opens
whenever the ~10 hour build happens to finish, which is frequently the middle of the
night, and a gate that expires while you are doing the thing it asked you to do is what
sent the last two releases down the manual-recovery path.

### If Gate 2 ends without publishing

Nothing is lost and nothing needs fixing by hand. `PUBLISH` never records itself as
complete, so the build checkpoint is still sitting at exactly that phase:

```powershell
python orchestrator.py --resume       # waits at Gate 2 again, honouring a tap from the last 12h
python orchestrator.py --publish-now  # skips the gate; publishes the draft as it stands
```

Use `--publish-now` when you have already finished editing the draft and just want the
rest of the pipeline to run. It refuses to do anything unless `PUBLISH` is genuinely the
next phase, so it can't be used to waive a gate somewhere it doesn't belong.

### Seeing what you changed

Every release directory keeps both versions: `release_notes.generated.md` (what the
pipeline wrote) and `release_notes.md` (what actually shipped), plus
`release_notes.edits.diff` between them when they differ. That diff is the only feedback
`render.py` gets. If the same edit keeps showing up across releases, that's the generator
asking to be fixed.

## Never edit orchestrator.py or state.json while a build is running

Stop the orchestrator first, make the change, then relaunch with `--resume`. Both failure
modes here are silent, which is what makes them worth a section.

**Edits to the code don't apply.** Python loads the module once at startup, so a running
pipeline keeps executing the version it started with. Fixing a phase mid-build and watching
it fail again in exactly the same way is a confusing hour.

**Edits to `state.json` get overwritten.** The orchestrator holds the whole state file in
memory and calls `save_state()` after every phase, writing its own copy back. Anything you
edit by hand is silently replaced with the running process's stale version at the next phase
boundary. This is not theoretical: a VirusTotal Sigma backfill written during a live run was
wiped this way, and nothing in the log said so. It was only caught by re-reading the file
afterwards instead of assuming the write had held.

Check before touching either:

```powershell
Test-Path D:\ducksteps\automation\orchestrator.lock
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*orchestrator.py*' }
```

Stopping is cheap. `--resume` restarts at the last phase that didn't complete, so you lose
that phase and nothing else. Even stopping during a multi-hour BUILD phase only costs that
one variant's build, never the whole run.

## Running the setup script

```powershell
D:\ducksteps\automation\setup_scheduler.ps1
```

**Run this from an elevated (Run as Administrator) PowerShell prompt.** The watcher
task's logon type (S4U: runs whether logged on or not, without storing your Windows
password anywhere) requires elevation to register. Without it, registration fails
partway through with "Access is denied" - confirmed directly, not assumed, while
building this.

Safe to re-run any time (e.g. after moving the automation directory, or changing your
Python install path at the top of the script): it re-registers both tasks in place
rather than erroring on "task already exists."

**Re-run it after pulling a change to the watcher's listening window.** The task's
execution time limit lives in Task Scheduler, not in the Python, so a watcher that is
supposed to listen for 12 hours still gets killed at whatever limit was registered last.
At the old 10-minute limit it would send the notification and then die long before you
answered it.

## Checking on things

```powershell
Get-ScheduledTask -TaskName "ducksteps*"
Get-ScheduledTaskInfo -TaskName "ducksteps watcher"
Get-ScheduledTaskInfo -TaskName "ducksteps orchestrator"
```

`logs/` in the automation directory has the real record of what each run actually did;
Task Scheduler's own "Last Run Result" only tells you the process exit code.

## Removing everything

```powershell
Unregister-ScheduledTask -TaskName "ducksteps watcher" -Confirm:$false
Unregister-ScheduledTask -TaskName "ducksteps orchestrator" -Confirm:$false
```
