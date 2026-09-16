from __future__ import annotations

import argparse
import ctypes
import difflib
import hashlib
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import traceback
import zipfile
from collections import deque
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

import advisory
import common
import notify
import publish
import render
import vt

VERSION_FILE_WHITELIST = {
    "browser/config/version.txt",
    "browser/config/version_display.txt",
    "config/milestone.txt",
}

# git status --porcelain XY codes that mean "unmerged / conflicted" during a rebase.
CONFLICT_CODES = {"UU", "AA", "DD", "AU", "UA", "DU", "UD"}

VARIANTS = {
    "zen5": {"mozconfig": ".mozconfig", "objdir_key": "zen5"},
    "legacy": {"mozconfig": ".mozconfig-Legacy", "objdir_key": "legacy"},
}
_VARIANT_PHASE_SUFFIXES = ["CLOBBER", "BUILD", "SMOKE", "PACKAGE", "7Z"]

# Window class ntfy'd from mach run - confirmed for Firefox/Gecko historically, but NOT
# yet verified against an actual ducksteps launch (see Phase 4 report). Recheck before
# trusting this against a real build.
FIREFOX_WINDOW_CLASS = "MozillaWindowClass"

CLOBBER_TIMEOUT_SECONDS = 600
PACKAGE_TIMEOUT_SECONDS = 600
SEVENZIP_TIMEOUT_SECONDS = 1800
WINDOW_WAIT_SECONDS = 90
# How long to keep trying to get the smoke window in front. 15s was too short: the window
# only has to be occluded at its centre for that long, by anything transient (a toast, an
# overlay repainting, the build console being interacted with), and a 10-hour build halts
# one phase from the finish line. Waiting is free - nothing else is happening - and a
# transient by definition passes.
SMOKE_RAISE_TIMEOUT_SECONDS = 45

PHASES = (
    ["PREFLIGHT", "STASH", "FETCH", "VERIFY_TAG", "CHECKOUT", "REBASE", "STASH_POP", "VERIFY_VER"]
    + [f"{variant.upper()}_{suffix}" for variant in VARIANTS for suffix in _VARIANT_PHASE_SUFFIXES]
    + ["HASH", "VIRUSTOTAL", "ADVISORY", "DRAFT", "PUBLISH"]
)


class OrchestratorError(Exception):
    """Base class for all pipeline-halting errors."""


class RebaseConflictError(OrchestratorError):
    """REBASE failure category: never retried, always halts. Invariant 1."""


class BuildFailedError(OrchestratorError):
    def __init__(self, message, log_path, tail_lines):
        super().__init__(message)
        self.log_path = log_path
        self.tail_lines = tail_lines


class VTHaltError(OrchestratorError):
    """VirusTotal halt (immediate, ladder-exhausted, or an unapproved known-noise flag) -
    already fully notified by the time this is raised, so run_pipeline must not re-triage it."""


class Gate2HaltError(OrchestratorError):
    """Gate 2 ended in a reject or a timeout. Like VTHaltError, already notified, and not a
    fault - the build is intact and --resume picks it straight back up."""


class Context:
    def __init__(self, config, logger, state, gate2_preapproved=False):
        self.config = config
        self.logger = logger
        self.state = state
        self.source_dir = Path(config["project"]["source_dir"])
        # --publish-now: the draft has already been reviewed and edited, so PUBLISH should
        # not send a Gate 2 notification and wait for a tap that has effectively happened.
        self.gate2_preapproved = gate2_preapproved

    @property
    def build(self):
        return self.state["build"]


# --- small subprocess helpers ---

def _git(source_dir, *args, timeout=120):
    return subprocess.run(
        ["git", *args], cwd=source_dir, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )


def retry_transient(fn, logger, max_attempts=5, base_delay=2):
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == max_attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.info("transient failure (attempt %d/%d): %s - retrying in %ds", attempt, max_attempts, exc, delay)
            time.sleep(delay)


def run_streamed(cmd, cwd, env, log_path, timeout_seconds, description):
    """Runs cmd, tee-ing stdout+stderr to log_path as it arrives (not buffered to the end -
    a multi-hour mach build can produce many MB of output). Returns (returncode, last_200_lines).
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    tail = deque(maxlen=200)
    q = queue.Queue()

    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )

    def reader():
        try:
            for line in proc.stdout:
                q.put(line)
        except Exception:
            pass
        finally:
            q.put(None)

    threading.Thread(target=reader, daemon=True).start()

    start = time.monotonic()
    with open(log_path, "w", encoding="utf-8") as log_file:
        while True:
            remaining = timeout_seconds - (time.monotonic() - start)
            if remaining <= 0:
                proc.kill()
                proc.wait(timeout=30)
                raise TimeoutError(f"{description} exceeded {timeout_seconds}s, killed")
            try:
                line = q.get(timeout=min(remaining, 5))
            except queue.Empty:
                continue
            if line is None:
                break
            log_file.write(line)
            log_file.flush()
            tail.append(line.rstrip("\n"))

    returncode = proc.wait(timeout=30)
    return returncode, list(tail)


def find_known_signature(log_path, signatures):
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            for sig in signatures:
                if sig in line:
                    return sig
    return None


def _mozconfig_env(ctx, variant):
    env = dict(os.environ)
    env["MOZCONFIG"] = str(ctx.source_dir / VARIANTS[variant]["mozconfig"])
    return env


def _objdir(ctx, variant):
    return Path(ctx.config["objdirs"][VARIANTS[variant]["objdir_key"]])


def _release_dir(ctx):
    d = common.RELEASES_DIR / ctx.build["version"]
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- PREFLIGHT..VERIFY_VER ---

def phase_preflight(ctx):
    build_error_log = ctx.source_dir / "build_error.log"
    if build_error_log.exists():
        ctx.logger.info("removing stale build_error.log")
        build_error_log.unlink()

    min_free_gb = ctx.config["preflight"]["min_free_disk_gb"]
    for drive in ("C:\\", "D:\\"):
        free_gb = shutil.disk_usage(drive).free / (1024 ** 3)
        ctx.logger.info("%s free space: %.1fGB", drive, free_gb)
        if free_gb < min_free_gb:
            raise OrchestratorError(f"only {free_gb:.1f}GB free on {drive}, need at least {min_free_gb}GB")


def phase_stash(ctx):
    status = _git(ctx.source_dir, "status", "--porcelain")
    if not status.stdout.strip():
        ctx.build["stashed"] = False
        return
    result = _git(ctx.source_dir, "stash", "push", "-m", f"ducksteps-orchestrator-{ctx.build['version']}")
    if "No local changes to save" in result.stdout:
        ctx.build["stashed"] = False
    elif result.returncode == 0:
        ctx.build["stashed"] = True
        ctx.logger.info("stashed local changes")
    else:
        raise OrchestratorError(f"git stash failed: {result.stderr.strip()}")


def phase_fetch(ctx):
    def _do():
        result = _git(ctx.source_dir, "fetch", "--tags", "origin", timeout=180)
        if result.returncode != 0:
            raise OrchestratorError(f"git fetch failed: {result.stderr.strip()}")
    retry_transient(_do, ctx.logger)


def phase_verify_tag(ctx):
    tag = ctx.build["tag"]

    def _do():
        return common.tag_exists(ctx.source_dir, tag)  # raises RuntimeError on git failure (transient)

    exists = retry_transient(_do, ctx.logger)
    if not exists:
        raise OrchestratorError(f"tag {tag} not found on origin - watcher's earlier tag check may be stale")


def phase_checkout(ctx):
    branch = ctx.config["project"]["branch"]
    result = _git(ctx.source_dir, "checkout", branch)
    if result.returncode != 0:
        raise OrchestratorError(f"git checkout {branch} failed: {result.stderr.strip()}")


def _conflicted_paths(source_dir) -> set:
    result = _git(source_dir, "status", "--porcelain")
    paths = set()
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        code, path = line[:2], line[3:].strip().strip('"')
        if code in CONFLICT_CODES:
            paths.add(path)
    return paths


def phase_rebase(ctx):
    tag = ctx.build["tag"]
    result = _git(ctx.source_dir, "rebase", tag, timeout=300)

    while result.returncode != 0:
        conflicted = _conflicted_paths(ctx.source_dir)
        if not conflicted:
            raise RebaseConflictError(f"git rebase failed with no conflicted paths detected: {result.stderr.strip()}")

        non_whitelisted = conflicted - VERSION_FILE_WHITELIST
        if non_whitelisted:
            raise RebaseConflictError(
                f"rebase conflict touches non-whitelisted paths: {sorted(non_whitelisted)}. "
                f"Invariant 1: never skip blind. Repo left mid-rebase for manual resolution."
            )

        ctx.logger.warning("rebase conflict on whitelisted version files only %s, running --skip", sorted(conflicted))
        result = _git(ctx.source_dir, "rebase", "--skip", timeout=300)


def phase_stash_pop(ctx):
    if not ctx.build.get("stashed"):
        return
    result = _git(ctx.source_dir, "stash", "pop")
    if result.returncode != 0:
        raise OrchestratorError(
            f"git stash pop failed (conflict?): {result.stderr.strip()}. Stash preserved, resolve manually."
        )


def phase_verify_version(ctx):
    version = ctx.build["version"]
    actual = (ctx.source_dir / "browser/config/version.txt").read_text(encoding="utf-8").strip()
    if actual != version:
        raise OrchestratorError(f"version.txt shows {actual!r}, expected {version!r} after rebase")

    expected_display = f"{version}esr"
    actual_display = (ctx.source_dir / "browser/config/version_display.txt").read_text(encoding="utf-8").strip()
    if actual_display != expected_display:
        raise OrchestratorError(f"version_display.txt shows {actual_display!r}, expected {expected_display!r}")

    ctx.logger.info("version verified: %s / %s", actual, actual_display)


# --- per-variant build phases ---

def clobber(ctx, variant):
    env = _mozconfig_env(ctx, variant)
    log_path = common.LOGS_DIR / f"{variant}-clobber-{ctx.build['version']}.log"
    returncode, tail = run_streamed(
        ["python", "mach", "clobber"], ctx.source_dir, env, log_path, CLOBBER_TIMEOUT_SECONDS, f"{variant} mach clobber"
    )
    if returncode != 0:
        raise BuildFailedError(f"mach clobber failed for {variant}", log_path, tail)


def build(ctx, variant):
    env = _mozconfig_env(ctx, variant)
    version = ctx.build["version"]
    log_path = common.LOGS_DIR / f"{variant}-build-{version}.log"
    timeout_seconds = ctx.config["timeouts"]["variant_hours"] * 3600

    notify.send_build_started(ctx.config, f"{version} ({variant})")

    returncode, tail = run_streamed(
        ["python", "mach", "build"], ctx.source_dir, env, log_path, timeout_seconds, f"{variant} mach build"
    )
    if returncode == 0:
        return

    signature = find_known_signature(log_path, ctx.config["known_recoverable"]["signatures"])
    retry_counts = ctx.build.setdefault("retry_counts", {})
    retry_key = f"{variant}_build"

    if signature and retry_counts.get(retry_key, 0) == 0:
        retry_counts[retry_key] = 1
        ctx.logger.warning("known-recoverable failure (%r) on %s build, retrying once after clobber", signature, variant)
        notify.send_retrying(ctx.config, version, signature)
        clobber(ctx, variant)
        returncode, tail = run_streamed(
            ["python", "mach", "build"], ctx.source_dir, env, log_path, timeout_seconds, f"{variant} mach build (retry)"
        )
        if returncode == 0:
            return

    raise BuildFailedError(f"mach build failed for {variant}", log_path, tail)


# A real browser window is far bigger than this; anything smaller is a helper window.
# Sized generously below any plausible browser window rather than tuned tight.
MIN_SMOKE_WINDOW_WIDTH = 400
MIN_SMOKE_WINDOW_HEIGHT = 300


def _visible_windows_of_class(class_name):
    """Every visible top-level window of class_name, as (hwnd, rect) pairs."""
    user32 = ctypes.windll.user32
    found = []

    # WINFUNCTYPE (stdcall) is required for EnumWindows' callback on win64; CFUNCTYPE
    # would corrupt the stack. Keep a reference to the callback object alive for the
    # duration of the call, otherwise it can be collected mid-enumeration.
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def _callback(hwnd, _lparam):
        buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buffer, 256)
        if buffer.value == class_name and user32.IsWindowVisible(hwnd):
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            found.append((hwnd, (rect.left, rect.top, rect.right, rect.bottom)))
        return True

    callback = callback_type(_callback)
    user32.EnumWindows(callback, 0)
    return found


def _find_window(class_name, timeout_seconds, poll_interval=1.0):
    """The largest visible top-level window of class_name, or None before the deadline.

    Deliberately NOT FindWindowW, which returns whichever matching window Windows hands
    back first. Gecko creates several MozillaWindowClass top-levels besides the browser
    itself, and on the first real ducksteps run FindWindowW returned one of those: the
    gate captured a 64x26 corner of a helper window and asked for sign-off on it. A
    screenshot gate that cannot fail is worse than no gate, since it converts a human
    check into a rubber stamp.

    Taking the largest visible window, and requiring it to clear a minimum size, means a
    helper window can never satisfy the gate; if only helper windows exist we keep
    polling and eventually time out, which halts loudly instead of passing quietly.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        candidates = [
            (hwnd, rect)
            for hwnd, rect in _visible_windows_of_class(class_name)
            if (rect[2] - rect[0]) >= MIN_SMOKE_WINDOW_WIDTH
            and (rect[3] - rect[1]) >= MIN_SMOKE_WINDOW_HEIGHT
        ]
        if candidates:
            hwnd, _ = max(candidates, key=lambda c: (c[1][2] - c[1][0]) * (c[1][3] - c[1][1]))
            return hwnd
        time.sleep(poll_interval)
    return None


def _window_rect(hwnd):
    user32 = ctypes.windll.user32
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def _centre_owner(hwnd):
    """The top-level window that owns the pixels at hwnd's centre, or None.

    This is the check that matters: screenshot_region grabs whatever is painted at a
    screen rectangle, so the only thing worth asserting is that the paint there is ours.
    WindowFromPoint returns the deepest child under the point, so walk up to its
    top-level ancestor before comparing.

    Returns the owner rather than a bool so a caller that loses the race can say who won
    it. Compare against the hwnd you asked about: equal means the window is genuinely on
    top and safe to capture.
    """
    user32 = ctypes.windll.user32
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.restype = wintypes.HWND
    GA_ROOT = 2

    left, top, right, bottom = _window_rect(hwnd)
    point = wintypes.POINT((left + right) // 2, (top + bottom) // 2)
    topmost = user32.WindowFromPoint(point)
    if not topmost:
        return None
    root = user32.GetAncestor(topmost, GA_ROOT)
    return int(root) if root else None


def _virtual_screen_rect():
    """Bounding box of every monitor, as (left, top, right, bottom)."""
    user32 = ctypes.windll.user32
    SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
    SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
    left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    return (left, top,
            left + user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
            top + user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))


def _centre_is_on_screen(hwnd):
    """Whether hwnd's centre lands on an actual monitor.

    Separate from _centre_owner because WindowFromPoint answers by window GEOMETRY, not by
    what is painted on a display: a window parked at (-6000, -6000) still "owns" its own
    centre and passes the ownership check, while CopyFromScreen at those coordinates
    returns black. Confirmed directly, by moving a window off the virtual desktop and
    watching the ownership check report success.

    Without this the gate could not fail in exactly the case it exists for - Firefox
    restores its window position from the profile, so a position left over from a
    different monitor layout produces a black screenshot and a request to sign off on it.
    """
    left, top, right, bottom = _window_rect(hwnd)
    centre_x, centre_y = (left + right) // 2, (top + bottom) // 2
    v_left, v_top, v_right, v_bottom = _virtual_screen_rect()
    return v_left <= centre_x < v_right and v_top <= centre_y < v_bottom


def _describe_window(hwnd):
    """class, title and owning process for a window handle, for log messages.

    Exists because "something else owns the pixels at its centre" was true but useless: it
    halted a 10-hour build one phase from the end without saying what the something else
    was, leaving nothing to act on afterwards and no way to tell a transient toast from a
    permanently-on-top widget.
    """
    if not hwnd:
        return "<nothing>"
    user32 = ctypes.windll.user32
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    length = user32.GetWindowTextLengthW(hwnd)
    title = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, title, length + 1)
    pid = _window_pid(hwnd)
    name = ""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
        )
        if result.returncode == 0 and '"' in result.stdout:
            name = result.stdout.split('"')[1]
    except (OSError, subprocess.SubprocessError):
        pass
    return f"class={cls.value!r} title={(title.value or '')[:60]!r} pid={pid}{f' ({name})' if name else ''}"


def _raise_window(hwnd, timeout_seconds=SMOKE_RAISE_TIMEOUT_SECONDS, poll_interval=0.5,
                  logger=None):
    """Put hwnd visually on top and confirm it. Returns (raised, problem).

    `problem` is None on success, and otherwise a sentence naming what stopped it, ready to
    drop into an error message or a log line.

    Deliberately does NOT rely on SetForegroundWindow succeeding. Windows refuses
    foreground activation to a process that does not already own the foreground window
    or the last input event, which is exactly the orchestrator's situation when it runs
    hidden with redirected stdio - so an earlier version of this check failed the gate on
    a perfectly good build. SetWindowPos/HWND_TOPMOST is not subject to those rules and
    is what actually gets the window in front of the compositor.

    The result is then verified by asking who owns the pixels, rather than trusting any
    of the calls to have worked. Capturing without that check is how this gate previously
    shipped a screenshot of an unrelated application and asked for sign-off on it.
    """
    user32 = ctypes.windll.user32
    SW_RESTORE = 9
    HWND_TOPMOST = -1
    SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW = 0x0002, 0x0001, 0x0040

    deadline = time.monotonic() + timeout_seconds
    problem = "it never appeared on screen"
    reported = set()
    while time.monotonic() < deadline:
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)  # best effort; may be refused, that is fine
        time.sleep(poll_interval)

        # Order matters: off-screen first, because a window off the virtual desktop passes
        # the ownership check below and would otherwise look like success.
        if not _centre_is_on_screen(hwnd):
            problem = (f"it is positioned off-screen at {_window_rect(hwnd)}; the virtual "
                       f"desktop is {_virtual_screen_rect()}")
        else:
            owner = _centre_owner(hwnd)
            if owner == int(hwnd):
                return True, None
            problem = f"the pixels at its centre belong to {_describe_window(owner)}"

        # Logged once per distinct problem rather than every 0.5s: a transient costs one
        # line and still passes, while a persistent one names every window that took a turn
        # on top instead of only whichever happened to be last.
        if logger and problem not in reported:
            reported.add(problem)
            logger.info("waiting for the smoke window: %s", problem)
    return False, problem


def _clear_topmost(hwnd):
    """Undo _raise_window's topmost flag so the window dies as an ordinary one."""
    user32 = ctypes.windll.user32
    HWND_NOTOPMOST = -2
    SWP_NOMOVE, SWP_NOSIZE = 0x0002, 0x0001
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)


def _window_pid(hwnd):
    user32 = ctypes.windll.user32
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def screenshot_region(rect, out_path):
    left, top, right, bottom = rect
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0:
        raise OrchestratorError(f"window rect is degenerate: {rect}")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
        f"$bmp = New-Object System.Drawing.Bitmap {width}, {height}; "
        "$gfx = [System.Drawing.Graphics]::FromImage($bmp); "
        f"$gfx.CopyFromScreen({left}, {top}, 0, 0, $bmp.Size); "
        f"$bmp.Save('{out_path}', [System.Drawing.Imaging.ImageFormat]::Png); "
        "$gfx.Dispose(); $bmp.Dispose()"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    if result.returncode != 0:
        raise OrchestratorError(f"screenshot capture failed: {result.stderr.strip()}")


def smoke(ctx, variant):
    env = _mozconfig_env(ctx, variant)
    version = ctx.build["version"]

    proc = subprocess.Popen(
        ["python", "mach", "run"], cwd=ctx.source_dir, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    hwnd = _find_window(FIREFOX_WINDOW_CLASS, WINDOW_WAIT_SECONDS)
    if not hwnd:
        proc.kill()
        raise OrchestratorError(f"no {variant} Firefox window appeared within {WINDOW_WAIT_SECONDS}s of 'mach run'")

    raised, problem = _raise_window(hwnd, logger=ctx.logger)
    if not raised:
        common.kill_pid(_window_pid(hwnd))
        proc.kill()
        raise OrchestratorError(
            f"could not get the {variant} window in front within "
            f"{SMOKE_RAISE_TIMEOUT_SECONDS}s: {problem}. Refusing to capture, because "
            f"screenshot_region grabs whatever is painted at that rectangle and would show "
            f"that instead of the browser. Clear whatever is in the way and re-run with "
            f"--resume; nothing already built is lost."
        )

    time.sleep(2)  # let it finish painting once it is actually on top
    rect = _window_rect(hwnd)
    screenshot_path = common.LOGS_DIR / f"{variant}-smoke-{version}.png"
    screenshot_region(rect, screenshot_path)
    _clear_topmost(hwnd)

    common.kill_pid(_window_pid(hwnd))
    proc.kill()

    # Before the send, not after: the subscription only opens once await_decision runs, and
    # anything tapped in between would fall outside a window anchored later.
    cursor = notify.Cursor()
    notify.send_smoke_test_ready(ctx.config, version, variant, screenshot_path)

    gate_wait_hours = ctx.config["timeouts"]["gate_wait_hours"]
    valid_bodies = {
        f"smoke-ok-{version}-{variant}": "approved",
        f"smoke-reject-{version}-{variant}": "rejected",
    }
    outcome = notify.await_decision(ctx.config, gate_wait_hours * 3600, valid_bodies,
                                    logger=ctx.logger, cursor=cursor)
    if outcome == "approved":
        return
    if outcome == "rejected":
        raise OrchestratorError(f"{variant} smoke test rejected")
    raise OrchestratorError(f"{variant} smoke test: no response within {gate_wait_hours}h")


def package(ctx, variant):
    objdir = _objdir(ctx, variant)
    log_path = common.LOGS_DIR / f"{variant}-package-{ctx.build['version']}.log"
    # The absolute msys2 bash from config, never a bare "bash". CreateProcess resolves a
    # bare program name against the System32 directory BEFORE anything on PATH, and
    # C:\Windows\System32\bash.exe is the WSL launcher, so subprocess.run(["bash", ...])
    # silently ran package.sh under WSL Linux instead of msys2. WSL cannot see D:\... or
    # /d/... (it mounts drives at /mnt/d), so it failed with "No such file or directory"
    # on a path that plainly exists. shutil.which("bash") does NOT show this, since it
    # searches PATH and correctly reports msys2's bash - the divergence between which()
    # and what actually launches is what makes this one hard to spot.
    # Once the right bash is used, msys2 accepts the native D:\... paths as-is.
    # env=_mozconfig_env(...) is load-bearing and was missing. package.sh runs
    # `python mach package`, and mach picks its objdir from MOZCONFIG, NOT from the
    # objdir argument (which package.sh only uses to locate the finished installer).
    # Without it mach falls back to the default .mozconfig, so LEGACY_PACKAGE rebuilt and
    # repackaged the ZEN5 objdir and then looked for the result under esr153-Legacy.
    # ZEN5_PACKAGE only appeared to work because the default mozconfig happens to be the
    # zen5 one. Had the installer lookup not failed, this would have shipped zen5 binaries
    # labelled Legacy - the two variants differ only in -march, so nothing downstream
    # (size, smoke test, even VirusTotal) would have looked wrong.
    result = subprocess.run(
        [ctx.config["msys"]["bash"], str(ctx.source_dir / "package.sh"), str(objdir)],
        cwd=ctx.source_dir, env=_mozconfig_env(ctx, variant), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=PACKAGE_TIMEOUT_SECONDS,
    )
    output = result.stdout + result.stderr
    log_path.write_text(output, encoding="utf-8")
    if result.returncode != 0:
        raise BuildFailedError(f"package.sh failed for {variant}", log_path, output.splitlines()[-200:])


# Artifact name infixes, e.g. ducksteps.153.1.0.AVX512.Setup.exe.
#
# These decide the order of the Assets box on the release page. GitHub sorts release assets
# by FILENAME and offers no way to reorder them: there is no position field, and upload
# order is irrelevant (verified on 153.0, where the ids ran Zen5-first while the page still
# listed Legacy first). "AVX512" sorts before "Legacy", which is the only reason the Zen5
# build appears on top. Renaming either of these silently reorders that box.
#
# Zen5 previously had no infix at all, which put it below Legacy alphabetically.
_ARTIFACT_SUFFIXES = {"zen5": ".AVX512", "legacy": ".Legacy"}


def _artifact_suffix(variant):
    return _ARTIFACT_SUFFIXES[variant]


def _build_7z(ctx, variant, *, solid=True, dictionary=None):
    """Extracts the packaged zip fresh each call (staging is not left lying around between
    calls) and compresses it. `solid`/`dictionary` let VT remediation (Phase 5) produce a
    byte-different archive without touching mozconfig, build flags, or source - packaging
    parameters only, per Invariant 6.
    """
    version = ctx.build["version"]
    objdir = _objdir(ctx, variant)
    suffix = _artifact_suffix(variant)

    zip_path = objdir / "dist" / f"firefox-{version}.en-US.win64.zip"
    if not zip_path.exists():
        raise OrchestratorError(f"expected zip not found: {zip_path}")

    staging = objdir / "dist" / "ducksteps-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(staging)
    (staging / "firefox").rename(staging / "ducksteps")

    release_dir = _release_dir(ctx)
    out_7z = release_dir / f"ducksteps.{version}{suffix}.Standalone.7z"
    if out_7z.exists():
        out_7z.unlink()

    sevenzip = ctx.config["sevenzip"]
    cmd = [
        sevenzip["binary"], "a", "-t7z", "-mx=9",
        f"-m0=LZMA2:d{dictionary or sevenzip['dictionary']}:fb{sevenzip['word_size']}",
        f"-ms={'on' if solid else 'off'}", f"-mmt={sevenzip['threads']}",
        str(out_7z), "ducksteps",
    ]
    # Deliberately "ducksteps", not the spec's literal ".\ducksteps\*": tested both against
    # 7z.exe invoked natively (as subprocess.run does here, not through a shell) and the
    # glob form strips the ducksteps\ prefix from every entry, producing a flat archive with
    # no top-level folder - contradicting the confirmed Phase 0 requirement that the 7z
    # contains a top-level folder renamed from firefox to ducksteps. Archiving the folder
    # itself preserves it as the wrapper, matching the original zip's own structure.
    result = subprocess.run(
        cmd, cwd=staging, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=SEVENZIP_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise OrchestratorError(f"7z failed for {variant}: {result.stderr.strip()}")

    shutil.rmtree(staging)
    return out_7z


def _copy_installer(ctx, variant):
    version = ctx.build["version"]
    objdir = _objdir(ctx, variant)
    suffix = _artifact_suffix(variant)

    # Upstream moved this between ESR lines, so check both layouts rather than pinning one.
    # toolkit/mozapps/installer/upload-files.mk on 140 had
    #   INSTALLER_PACKAGE = $(DIST)/$(PKG_INST_PATH)$(PKG_INST_BASENAME).exe   -> dist/install/sea/
    # and 153 changed that variable to $(PKG_PATH), which is empty for en-US builds:
    #   INSTALLER_PACKAGE = $(DIST)/$(PKG_PATH)$(PKG_INST_BASENAME).exe        -> dist/
    # Newest layout first; the old path stays as a fallback so this keeps working if an
    # older line ever gets built again.
    installer_name = f"firefox-{version}.en-US.win64.installer.exe"
    candidates = [
        objdir / "dist" / installer_name,
        objdir / "dist" / "install" / "sea" / installer_name,
    ]
    installer_src = next((c for c in candidates if c.exists()), None)
    if installer_src is None:
        raise OrchestratorError(
            "expected installer not found in any known layout: " + ", ".join(str(c) for c in candidates)
        )
    installer_dst = _release_dir(ctx) / f"ducksteps.{version}{suffix}.Setup.exe"
    shutil.copy2(installer_src, installer_dst)
    return installer_dst


def pack_7z(ctx, variant):
    out_7z = _build_7z(ctx, variant)
    installer_dst = _copy_installer(ctx, variant)
    ctx.build.setdefault("artifacts", {})[variant] = {
        "setup_exe": str(installer_dst),
        "standalone_7z": str(out_7z),
    }


def hash_artifacts(ctx):
    for variant, paths in ctx.build.get("artifacts", {}).items():
        kinds = [k for k in list(paths.keys()) if not k.endswith("_sha512")]
        hashes = {}
        for kind in kinds:
            path = Path(paths[kind])
            digest = hashlib.sha512()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(chunk)
            hex_digest = digest.hexdigest()
            hashes[f"{kind}_sha512"] = hex_digest
            ctx.logger.info("%s %s sha512: %s...", variant, kind, hex_digest[:16])
        paths.update(hashes)


# --- VirusTotal (Phase 5) ---

# Which remediation options apply to which artifact kind, in ladder order. Installers only
# get one shot (regenerate via a clean package.sh); 7z archives get two (non-solid, then a
# different dictionary size). All three are packaging-parameter changes only - Invariant 6
# forbids touching mozconfig, build flags, or source here.
ARTIFACT_KINDS = {
    "setup_exe": ["regenerate_installer"],
    "standalone_7z": ["repack_nonsolid", "repack_different_dict"],
}


def _sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _version_sort_key(version_string):
    try:
        return tuple(int(part) for part in version_string.split("."))
    except ValueError:
        return (0,)


def _previous_shipped_vt(ctx, variant, kind):
    """This variant/kind's recorded VT result from the most recent SHIPPED release, or None.

    Empty until a release actually completes PUBLISH, so the first run after adding this has
    no baseline and everything reads as new. That is correct rather than unfortunate: a
    baseline is only meaningful once it describes something users actually received.
    """
    history = ctx.state.get("vt_shipped_history", {})
    for version in sorted(history.keys(), key=_version_sort_key, reverse=True):
        entry = history[version].get(variant, {}).get(kind)
        if entry:
            return entry
    return None


def _previous_engines_for(ctx, variant, kind):
    """Engines that flagged this same variant/kind on the most recent SHIPPED release, for the
    KNOWN_NOISE delta check."""
    entry = _previous_shipped_vt(ctx, variant, kind)
    return set(entry.get("engines", [])) if entry else None


def _log_sigma(ctx, variant, kind, verdict):
    """Record Sigma matches and, more usefully, say what CHANGED since the last shipped
    release. Never gates anything: these are sandbox-behaviour rules from community
    rulesets, excluded from VT's own detection score, and an unsigned self-extracting
    installer trips several of them by construction. The signal is the delta, not the count.
    """
    current = {rule["title"]: rule.get("level", "") for rule in verdict.sigma_rules}
    if verdict.sigma_summary:
        ctx.logger.info("VT sigma %s/%s: %s", variant, kind, verdict.sigma_summary)

    previous_entry = _previous_shipped_vt(ctx, variant, kind)
    if previous_entry is None or "sigma" not in previous_entry:
        for title, level in sorted(current.items(), key=lambda kv: (kv[1], kv[0])):
            ctx.logger.info("  sigma [%s] %s", level or "?", title)
        return

    previous = previous_entry.get("sigma", {}).get("rules", {})
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    if not added and not removed:
        ctx.logger.info("  sigma unchanged from the last shipped release (%d rule(s))", len(current))
        return
    for title in added:
        ctx.logger.warning("  sigma NEW    [%s] %s", current[title] or "?", title)
    for title in removed:
        ctx.logger.info("  sigma GONE   [%s] %s", previous[title] or "?", title)


def _apply_remediation(ctx, variant, kind, remediation):
    if remediation == "regenerate_installer":
        package(ctx, variant)
        installer_dst = _copy_installer(ctx, variant)
        ctx.build["artifacts"][variant]["setup_exe"] = str(installer_dst)
    elif remediation == "repack_nonsolid":
        out_7z = _build_7z(ctx, variant, solid=False)
        ctx.build["artifacts"][variant]["standalone_7z"] = str(out_7z)
    elif remediation == "repack_different_dict":
        remediation_dict = ctx.config["sevenzip"]["remediation_dictionary"]
        out_7z = _build_7z(ctx, variant, dictionary=remediation_dict)
        ctx.build["artifacts"][variant]["standalone_7z"] = str(out_7z)
    else:
        raise ValueError(f"unknown remediation: {remediation}")
    hash_artifacts(ctx)  # the regenerated file needs a fresh SHA512 for the release notes


def _vt_resolve_artifact(ctx, variant, kind, bucket):
    version = ctx.build["version"]
    remediations = deque(ARTIFACT_KINDS[kind])

    while True:
        path = Path(ctx.build["artifacts"][variant][kind])
        sha256_hex = _sha256_of(path)
        verdict = vt.submit_file(path, sha256_hex, bucket, logger=ctx.logger)
        previous_engines = _previous_engines_for(ctx, variant, kind)
        result = vt.classify(verdict, previous_engines=previous_engines)

        ctx.logger.info("VT %s/%s: %s (%s)", variant, kind, result.status, result.reason)
        ctx.build.setdefault("vt_results", {}).setdefault(variant, {})[kind] = {
            "status": result.status,
            "engines": sorted(result.detections.keys()),
            "sha256": sha256_hex,
            "sigma": {
                "summary": verdict.sigma_summary,
                # title -> level, so the next release can diff by rule name
                "rules": {rule["title"]: rule.get("level", "") for rule in verdict.sigma_rules},
            },
        }
        _log_sigma(ctx, variant, kind, verdict)
        common.save_state(ctx.state)

        if result.status == "PASS":
            return

        if result.status == "KNOWN_NOISE":
            engines = ", ".join(sorted(result.detections.keys()))
            cursor = notify.Cursor()
            notify.send_vt_flagged(
                ctx.config, version,
                f"{variant}/{kind}: same engines as a previously shipped release ({engines}). "
                f"One tap to proceed, no rebuild needed.",
            )
            gate_seconds = ctx.config["timeouts"]["gate_wait_hours"] * 3600
            outcome = notify.await_decision(
                ctx.config, gate_seconds,
                {f"vt-approve-{version}": "approved", f"vt-halt-{version}": "halted"},
                logger=ctx.logger, cursor=cursor,
            )
            if outcome == "approved":
                return
            raise VTHaltError(f"{variant}/{kind}: known-noise flag not approved ({outcome})")

        if result.status == "IMMEDIATE_HALT":
            diagnosis = vt.draft_fp_submissions(result.detections, f"{variant}/{kind}", logger=ctx.logger)
            summary = f"{variant}/{kind}: {result.reason}"
            if diagnosis:
                summary += f"\n\nDraft FP submissions:\n{diagnosis}"
            notify.send_fatal_error(ctx.config, version, summary, str(common.LOGS_DIR))
            raise VTHaltError(f"{variant}/{kind}: {result.reason}")

        # NEW_DETECTIONS: work through the applicable remediation ladder for this artifact kind.
        if not remediations:
            diagnosis = vt.draft_fp_submissions(result.detections, f"{variant}/{kind}", logger=ctx.logger)
            summary = f"{variant}/{kind}: remediation ladder exhausted, still flagged ({result.reason})"
            if diagnosis:
                summary += f"\n\nDraft FP submissions:\n{diagnosis}"
            notify.send_fatal_error(ctx.config, version, summary, str(common.LOGS_DIR))
            raise VTHaltError(f"{variant}/{kind}: remediation ladder exhausted")

        remediation = remediations.popleft()
        ctx.logger.warning("%s/%s flagged (%s), trying remediation: %s", variant, kind, result.reason, remediation)
        notify.send_retrying(ctx.config, version, f"VT: {remediation} for {variant}/{kind}")
        _apply_remediation(ctx, variant, kind, remediation)


def phase_virustotal(ctx):
    bucket = vt.TokenBucket()
    # Invariant 7 (never ship half a variant): _vt_resolve_artifact raises on any artifact
    # that doesn't clear, which halts the whole pipeline here - there is no path where one
    # artifact ships while its sibling is still flagged.
    for variant in VARIANTS:
        for kind in ARTIFACT_KINDS:
            _vt_resolve_artifact(ctx, variant, kind, bucket)
    ctx.logger.info("VirusTotal: all four artifacts clear")


def phase_advisory(ctx):
    version = ctx.build["version"]
    tag = ctx.build["tag"]
    repo_dir = ctx.config["project"]["repo_dir"]

    # AdvisoryError halts, no triage needed - self-explanatory
    adv = advisory.resolve_advisory(
        version,
        ctx.config.get("advisory", {}).get("non_windows_markers", ()),
        logger=ctx.logger,
    )
    changes = render.get_ducksteps_changes(ctx.source_dir, repo_dir, tag, version, logger=ctx.logger)

    # Iterate VARIANTS, never ctx.build["artifacts"].items(). save_state writes with
    # sort_keys=True, so that dict comes back from JSON alphabetically ordered as
    # legacy, zen5 - which silently put the Legacy build above the Zen5 one in both the
    # SHA512 and VirusTotal lists. VARIANTS is the canonical order (Zen5 first) and is the
    # only thing that should decide presentation.
    artifacts = []
    for variant in VARIANTS:
        paths = ctx.build["artifacts"][variant]
        for kind in ("setup_exe", "standalone_7z"):
            sha256 = ctx.build["vt_results"][variant][kind]["sha256"]
            artifacts.append({
                "name": Path(paths[kind]).name,
                "sha512": paths[f"{kind}_sha512"],
                # ?nocache=1 matches Tim's own existing published releases - confirmed
                # against the real 140.13.0 release body rather than guessed.
                "vt_url": f"https://www.virustotal.com/gui/file/{sha256}?nocache=1",
            })

    previous_titles = publish.recent_release_titles(ctx.config["publish"]["repo_slug"], limit=2, logger=ctx.logger)

    data = render.build_release_data(
        version=version, esr_version=f"{version}esr", advisory=adv,
        ducksteps_changes=changes, artifacts=artifacts, previous_titles=previous_titles,
        logger=ctx.logger,
    )
    # Sweep freshly rendered output too, not just historical documents. The em dash ban is
    # absolute, and two sources bypass every other guard: the claude -p summary (free text,
    # and it does reach for em dashes), and ducksteps_changes, which is raw git commit
    # subjects - "ducksteps PGO: corpus updates - duckai behavior..." carried one straight
    # into a published release body. The sweep helpers were only ever pointed at old files
    # before this. The sweeps are idempotent by construction (each pattern matches only the
    # pre-sweep shape), so running them here costs nothing and closes the hole at the last
    # point before anything is written.
    ctx.build["release_notes"] = publish.sweep_release_body(render.render_release_notes(data))
    ctx.build["changelog_entry"] = publish.sweep_changelog_entry(render.render_changelog_entry(data))
    ctx.build["release_title"] = f'⛐ It\'s the "{data.title}" release!'


def phase_draft(ctx):
    """Create the GitHub draft release and ask for a decision. Writes NOTHING public.

    Every mutation of the docs repo (patch stack, docs sync, changelog, commit, tag) now
    lives in phase_publish, behind the Gate 2 approval. It used to happen here, which
    meant the changelog entry and the version tag were pushed before anyone had read the
    release notes. Editing the notes afterwards then left a published changelog quoting
    the superseded text, and correcting it meant force-updating a tag that was already
    public. A draft release is private and freely editable, so it is the only thing that
    should exist before approval.
    """
    version = ctx.build["version"]

    # Upload order IS display order: GitHub returns release assets by asset id, i.e. the
    # order they were uploaded, and offers no way to reorder them afterwards short of
    # deleting and re-uploading. So Zen5 must go up first, and again VARIANTS decides that
    # rather than the alphabetically-sorted dict that comes back out of state.json.
    artifact_paths = []
    for variant in VARIANTS:
        variant_artifacts = ctx.build["artifacts"][variant]
        artifact_paths.append(variant_artifacts["setup_exe"])
        artifact_paths.append(variant_artifacts["standalone_7z"])

    release_dir = _release_dir(ctx)
    notes_path = release_dir / "release_notes.md"
    # LF explicitly, not the platform default. This file IS the published release body -
    # gh reads it straight into the release via --notes-file - so its line endings should
    # not depend on which machine happened to run the build.
    notes_path.write_text(ctx.build["release_notes"], encoding="utf-8", newline="\n")
    # Second copy, never overwritten. release_notes.md is rewritten at PUBLISH with the text
    # as actually shipped, so without this the generated version is gone and there is no way
    # to see what was edited. Keeping both is what makes _record_note_edits possible, and
    # that diff is the only feedback loop render.py has.
    (release_dir / "release_notes.generated.md").write_text(
        ctx.build["release_notes"], encoding="utf-8", newline="\n")

    repo_slug = ctx.config["publish"]["repo_slug"]
    draft_url = publish.create_draft_release(
        repo_slug, version, ctx.build["release_title"], notes_path, artifact_paths, logger=ctx.logger,
    )
    ctx.build["draft_url"] = draft_url
    # Recorded now, while the draft is definitely there, so PUBLISH can address it by id.
    # Not fatal if it fails: fetch_release looks the id up itself when it is missing, and
    # losing the whole draft over a hiccup in a bookkeeping call would be absurd.
    try:
        ctx.build["draft_release_id"] = publish.find_release_id(repo_slug, version, logger=ctx.logger)
    except publish.PublishError as exc:
        ctx.logger.warning("could not record the draft's release id (%s); PUBLISH will look it up", exc)

    # Gate 2 is asked here but waited on in PUBLISH, and a --resume re-enters PUBLISH
    # without re-asking, so the moment of the ask has to outlive this phase.
    ctx.build["gate2_asked_at"] = datetime.now(timezone.utc).isoformat()
    notify.send_draft_ready(ctx.config, version, draft_url)


def _record_vt_history(ctx):
    """Persist this release's VT results as the baseline for the next one.

    Nothing wrote vt_shipped_history before this, so _previous_engines_for always returned
    None and the KNOWN_NOISE path was unreachable: every detection had to go through the
    full remediation ladder even when it was the exact same engine flagging the exact same
    thing as last time. Recorded only after publish_release succeeds, because the point of
    the baseline is "what users actually received", not "what we happened to build".
    """
    version = ctx.build["version"]
    history = ctx.state.setdefault("vt_shipped_history", {})
    entry = history.setdefault(version, {})
    for variant, kinds in ctx.build.get("vt_results", {}).items():
        for kind, result in kinds.items():
            entry.setdefault(variant, {})[kind] = {
                "engines": result.get("engines", []),
                "sigma": result.get("sigma", {}),
                "sha256": result.get("sha256"),
            }
    # Bounded like phase_timing_history: a baseline only ever needs the newest entry, and
    # this file is rewritten on every phase transition.
    for stale in sorted(history, key=_version_sort_key, reverse=True)[5:]:
        del history[stale]
    common.save_state(ctx.state)
    ctx.logger.info("recorded VT baseline for %s (%d variant(s))", version, len(entry))


def _record_note_edits(ctx, generated, shipped):
    """Save a diff of what was rewritten by hand, next to the artifacts.

    render.py has no other feedback loop. Every release so far has been edited before it
    went out and the edits have a clear shape (raw commit subjects rewritten as sentences,
    the drafted summary cut down), but that was only visible by diffing a published release
    against a local file after the fact. A few of these accumulated in releases/ is the
    evidence for what the generator should be doing differently.
    """
    diff = difflib.unified_diff(
        generated.splitlines(keepends=True), shipped.splitlines(keepends=True),
        fromfile="release_notes.generated.md", tofile="release_notes.md", n=2,
    )
    text = "".join(diff)
    if not text:
        return
    path = _release_dir(ctx) / "release_notes.edits.diff"
    path.write_text(text, encoding="utf-8", newline="\n")
    ctx.logger.info("recorded the hand edits made to %s's notes: %s", ctx.build["version"], path)


def _adopt_edited_release_text(ctx):
    """Re-read the draft from GitHub and make it authoritative for everything downstream.

    This is the fix for the failure that ended the last two releases. The draft exists to be
    edited - that is the entire reason DRAFT and PUBLISH are separate phases - but nothing
    read the edits back, so approving at Gate 2 would have published Tim's rewritten notes
    while committing ADVISORY's superseded text to Docs/Changelog.md and tagging it. The
    only safe move left was to reject and redo the tail by hand, twice.

    After this, the draft is the single source of truth for the release's prose and the
    changelog entry is derived from it, so the two cannot disagree by construction.

    The normalization pass is pushed BACK to the draft before publishing rather than applied
    only to the changelog copy. Otherwise the sweeps would themselves recreate the drift
    they exist to prevent: an em dash typed into the browser would be a semicolon in the
    changelog and an em dash on the release page.
    """
    repo_slug = ctx.config["publish"]["repo_slug"]
    version = ctx.build["version"]

    release = publish.fetch_release(
        repo_slug, version, ctx.build.get("draft_release_id"), logger=ctx.logger)
    ctx.build["draft_release_id"] = release["id"]

    fetched_body = publish.normalize_newlines(release["body"])
    generated = ctx.build.get("release_notes", "")
    if fetched_body.strip() != generated.strip():
        ctx.logger.info("draft %s was edited on GitHub since DRAFT; the edited text is what ships", version)
        _record_note_edits(ctx, generated, fetched_body)
    else:
        ctx.logger.info("draft %s is unchanged since DRAFT", version)

    body = publish.sweep_release_body(fetched_body)
    title = publish.sweep_release_title(release["name"])
    if body != fetched_body or title != release["name"]:
        ctx.logger.info("normalizing the draft before publishing (em dashes, smart quotes, spacing)")
        publish.update_release_text(repo_slug, release["id"], title, body, logger=ctx.logger)

    now = datetime.now(timezone.utc)
    # The date the notes were rendered with, not today's. A Gate 2 round trip can now span a
    # night, and re-dating the entry at publish time would make the changelog disagree with a
    # document that was already reviewed under that date.
    release_date = publish.changelog_entry_date(
        ctx.build.get("changelog_entry"), f"{now.day}/{now.strftime('%B')}/{now.year}")

    ctx.build["release_notes"] = body
    ctx.build["release_title"] = title
    ctx.build["changelog_entry"] = publish.sweep_changelog_entry(
        publish.changelog_entry_from_release(body, title, version, release_date, logger=ctx.logger)
    )
    common.save_state(ctx.state)

    # Local copy matches what shipped, so releases/<version>/ is a faithful record.
    (_release_dir(ctx) / "release_notes.md").write_text(body, encoding="utf-8", newline="\n")


def phase_publish(ctx):
    version = ctx.build["version"]
    draft_url = ctx.build.get("draft_url", "")
    gate_hours = ctx.config["timeouts"]["gate_wait_hours"]
    max_snoozes = ctx.config["timeouts"].get("gate2_max_extensions", 7)

    if ctx.gate2_preapproved:
        ctx.logger.warning("Gate 2 pre-approved on the command line (--publish-now), not waiting for a tap")
        outcome = "approved"
    else:
        outcome = notify.await_gate2_decision(
            ctx.config, version, draft_url, gate_hours * 3600, max_snoozes, logger=ctx.logger,
            since=notify.anchor_from_iso(ctx.build.get("gate2_asked_at")),
        )

    if outcome == "approved":
        repo_slug = ctx.config["publish"]["repo_slug"]

        # Before anything is written anywhere: adopt whatever the draft says now. Every
        # step below consumes ctx.build["release_notes"] / ["changelog_entry"], so this has
        # to happen first or the docs repo gets the stale text.
        _adopt_edited_release_text(ctx)

        # Everything that writes to the docs repo happens HERE, after approval, using the
        # release notes exactly as approved. Order matters: the tag has to be pushed before
        # the draft is flipped, otherwise GitHub creates the tag itself at whatever the
        # default branch currently points to.
        tag = ctx.build["tag"]
        repo_dir = ctx.config["project"]["repo_dir"]
        branch = ctx.config["project"]["branch"]
        publish.sync_patch_stack(repo_dir, ctx.source_dir, tag, logger=ctx.logger)
        publish.regenerate_patches_readme(repo_dir, ctx.source_dir, tag, branch, logger=ctx.logger)
        publish.sync_docs_files(repo_dir, ctx.source_dir, logger=ctx.logger)
        publish.sync_automation(repo_dir, common.AUTOMATION_DIR, logger=ctx.logger)
        publish.prepend_changelog(repo_dir, ctx.build["changelog_entry"], logger=ctx.logger)
        publish.commit_push_tag(repo_dir, version, logger=ctx.logger)

        publish.publish_release(
            repo_slug, version,
            discussion_category=ctx.config["publish"].get("discussion_category") or None,
            logger=ctx.logger,
        )
        _record_vt_history(ctx)
        # NOT draft_url. A draft lives at /releases/tag/untagged-<hash>, and that URL dies
        # the moment it is published; the tag URL only starts resolving to the release at
        # that same moment. So the two notifications need different links, and using
        # either one for both sends the reader somewhere useless. Gate 2 keeps draft_url
        # (the draft is not visible at the tag URL - that shows the tag's commit list
        # instead, which is exactly how this was discovered).
        notify.send_published(
            ctx.config, version, f"https://github.com/{repo_slug}/releases/tag/{version}"
        )
        ctx.logger.info("published %s", version)
        return

    if outcome == "rejected":
        reason = "Rejected at Gate 2. The draft is untouched and still private."
    else:
        reason = (f"No response within {gate_hours}h "
                  f"(plus up to {max_snoozes} extensions). The draft is still private.")
    notify.send_gate2_halt(ctx.config, version, reason, draft_url)
    # Gate2HaltError, not a bare OrchestratorError: this is a decision, not a fault, and
    # run_pipeline's generic handler would otherwise run a claude -p triage over a traceback
    # to explain that a button was pressed. PUBLISH stays out of completed_phases either
    # way, so --resume re-enters here and re-asks.
    raise Gate2HaltError(f"{version} not published: {reason}")


PHASE_HANDLERS = {
    "PREFLIGHT": phase_preflight,
    "STASH": phase_stash,
    "FETCH": phase_fetch,
    "VERIFY_TAG": phase_verify_tag,
    "CHECKOUT": phase_checkout,
    "REBASE": phase_rebase,
    "STASH_POP": phase_stash_pop,
    "VERIFY_VER": phase_verify_version,
    "HASH": hash_artifacts,
    "VIRUSTOTAL": phase_virustotal,
    "ADVISORY": phase_advisory,
    "DRAFT": phase_draft,
    "PUBLISH": phase_publish,
}
for _variant in VARIANTS:
    _prefix = _variant.upper()
    PHASE_HANDLERS[f"{_prefix}_CLOBBER"] = (lambda v: lambda ctx: clobber(ctx, v))(_variant)
    PHASE_HANDLERS[f"{_prefix}_BUILD"] = (lambda v: lambda ctx: build(ctx, v))(_variant)
    PHASE_HANDLERS[f"{_prefix}_SMOKE"] = (lambda v: lambda ctx: smoke(ctx, v))(_variant)
    PHASE_HANDLERS[f"{_prefix}_PACKAGE"] = (lambda v: lambda ctx: package(ctx, v))(_variant)
    PHASE_HANDLERS[f"{_prefix}_7Z"] = (lambda v: lambda ctx: pack_7z(ctx, v))(_variant)


# --- timing / rolling median ---

def _record_timing(ctx, phase_name, elapsed_seconds):
    history = ctx.state.setdefault("phase_timing_history", {}).setdefault(phase_name, [])
    if history:
        sorted_history = sorted(history)
        median = sorted_history[len(sorted_history) // 2]
        if median > 0 and elapsed_seconds > median * 1.5:
            ctx.logger.warning(
                "%s took %.1fs, over 150%% of the %.1fs rolling median (n=%d)",
                phase_name, elapsed_seconds, median, len(history),
            )
    history.append(elapsed_seconds)
    history[:] = history[-10:]  # bounded, no unbounded growth run over run


# --- failure handling (UNKNOWN category: capture, triage, urgent notify, never auto-retry) ---

def _triage_with_claude(ctx, phase_name, tail_text):
    prompt = (
        f"A ducksteps (custom Firefox ESR build) release pipeline failed at phase {phase_name}. "
        f"Here is the tail of its log:\n\n{tail_text}\n\n"
        f"In 2-3 sentences, give a build engineer your best diagnosis of the likely cause. "
        f"Do not invent specifics you cannot see in the log; characterize the failure honestly."
    )
    try:
        result = subprocess.run(
            ["claude", "-p", prompt], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120,
        )
        if result.returncode != 0:
            ctx.logger.warning("claude -p triage failed: %s", result.stderr.strip())
            return None
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError) as exc:
        ctx.logger.warning("could not invoke claude -p for triage: %s", exc)
        return None


def _handle_unknown_failure(ctx, phase_name, exc, log_path, tail_lines):
    if tail_lines is None:
        tail_lines = traceback.format_exc().splitlines()
    tail_text = "\n".join(tail_lines[-200:])

    diagnosis = _triage_with_claude(ctx, phase_name, tail_text)
    summary = f"{phase_name} failed: {exc}"
    if diagnosis:
        summary += f"\n\nClaude triage: {diagnosis}"

    notify.send_fatal_error(ctx.config, ctx.build["version"], summary, str(log_path or common.LOGS_DIR))


# --- pipeline driver ---

def _finish_build(ctx):
    """Retire the build checkpoint once every phase has completed.

    _start_fresh refuses to start while state["build"] exists, so leaving it behind means
    the NEXT release stops dead with "an in-progress or incomplete build exists" and needs
    state.json hand-edited before it can run. Nothing cleared it before simply because the
    pipeline had never once reached the end.

    pending_release is marked shipped rather than deleted, so the watcher sees a decided,
    terminal status (OPEN_STATUSES covers only awaiting_tag / awaiting_approval) and does
    not re-offer the version it just built.
    """
    build = ctx.state.pop("build", None)
    if build:
        ctx.state["last_shipped"] = {
            "version": build.get("version"),
            "tag": build.get("tag"),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        pending = ctx.state.get("pending_release")
        if pending and pending.get("version") == build.get("version"):
            pending["status"] = "shipped"
        ctx.logger.info("build checkpoint for %s retired; ready for the next release",
                        build.get("version"))
    common.save_state(ctx.state)


def run_pipeline(ctx, start_index):
    for phase_name in PHASES[start_index:]:
        ctx.logger.info("=== phase %s starting ===", phase_name)
        ctx.build["current_phase"] = phase_name
        common.save_state(ctx.state)
        start = time.monotonic()

        try:
            PHASE_HANDLERS[phase_name](ctx)
        except RebaseConflictError as exc:
            ctx.logger.error("REBASE HALT at %s: %s", phase_name, exc)
            notify.send_fatal_error(ctx.config, ctx.build["version"], f"REBASE halted: {exc}", str(common.LOGS_DIR))
            common.save_state(ctx.state)
            raise
        except VTHaltError as exc:
            # Already fully notified (send_vt_flagged / send_fatal_error + claude -p triage)
            # inside _vt_resolve_artifact - re-triaging here would double-notify.
            ctx.logger.error("VIRUSTOTAL HALT at %s: %s", phase_name, exc)
            common.save_state(ctx.state)
            raise
        except Gate2HaltError as exc:
            # Same contract as VTHaltError: notified at the raise site, and a decision rather
            # than a failure, so no triage and no FATAL.
            ctx.logger.warning("GATE 2 HALT at %s: %s", phase_name, exc)
            common.save_state(ctx.state)
            raise
        except Exception as exc:
            log_path = getattr(exc, "log_path", None)
            tail_lines = getattr(exc, "tail_lines", None)
            # Log BEFORE notifying. Without this line the only record of an UNKNOWN
            # failure was the ntfy push, so the log file simply stopped after
            # "=== phase X starting ===" and a dead pipeline was indistinguishable from a
            # running one - which cost real time twice while debugging this migration.
            # The two categories above already log; this one silently did not.
            ctx.logger.error("%s FAILED: %s", phase_name, exc)
            _handle_unknown_failure(ctx, phase_name, exc, log_path, tail_lines)
            common.save_state(ctx.state)
            raise

        elapsed = time.monotonic() - start
        _record_timing(ctx, phase_name, elapsed)
        ctx.build.setdefault("completed_phases", []).append(phase_name)
        common.save_state(ctx.state)
        ctx.logger.info("=== phase %s done in %.1fs ===", phase_name, elapsed)

    ctx.logger.info("pipeline complete through %s", PHASES[-1])
    _finish_build(ctx)


def _start_fresh(config, logger, state):
    if "build" in state:
        existing = state["build"]
        last_phase = (existing.get("completed_phases") or ["none"])[-1]
        logger.error(
            "an in-progress or incomplete build for %s exists (last completed phase: %s). "
            "Use --resume to continue it, or clear state.json's 'build' key to abandon it.",
            existing.get("version"), last_phase,
        )
        return None

    pending = state.get("pending_release")
    if not pending:
        logger.error("no pending_release in state.json - nothing to build")
        return None

    if pending["status"] == "awaiting_tag":
        logger.error("release %s is not yet tagged upstream, nothing to build", pending["version"])
        return None

    if pending["status"] == "awaiting_approval":
        logger.info("waiting for Gate 1 approval on %s", pending["version"])
        # since=: the watcher asked this question, possibly hours ago, and the answer may
        # already be sitting in ntfy's cache. Starting a fresh "from now on" subscription
        # here is what used to make an approval tapped before this run invisible, so that
        # walking to the PC after approving meant being asked all over again.
        outcome = notify.await_gate1_decision(
            config, pending["version"], logger=logger,
            since=notify.anchor_from_iso(common.gate1_asked_at(pending)),
        )
        if outcome == "approved":
            pending["status"] = "approved"
        elif outcome == "rejected":
            pending["status"] = "rejected"
            common.save_state(state)
            logger.info("release %s rejected, nothing to build", pending["version"])
            return None
        else:
            common.save_state(state)
            logger.info("no response for %s, exiting - watcher will re-ask", pending["version"])
            return None
    elif pending["status"] != "approved":
        logger.error("release %s has status %r, nothing to build", pending["version"], pending["status"])
        return None

    state["build"] = {
        "version": pending["version"],
        "tag": pending["tag"],
        "completed_phases": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    common.save_state(state)
    return 0


def _resume(logger, state):
    if "build" not in state or not state["build"].get("version"):
        logger.error("--resume given but no in-progress build found in state.json")
        return None
    completed = state["build"].get("completed_phases", [])
    start_index = len(completed)
    if start_index >= len(PHASES):
        logger.info("build %s already completed all phases", state["build"]["version"])
        return None
    logger.info("resuming %s from phase %s (index %d)", state["build"]["version"], PHASES[start_index], start_index)
    return start_index


def _run(config, logger, state, resume, publish_now=False):
    if resume or publish_now:
        start_index = _resume(logger, state)
    else:
        start_index = _start_fresh(config, logger, state)

    if start_index is None:
        return 1

    if publish_now and PHASES[start_index] != "PUBLISH":
        # Skipping a gate is only ever safe at the one phase the gate belongs to. Anywhere
        # else this flag would silently mean "run the rest of the build with Gate 2 waived",
        # including phases that have not produced a draft to approve yet.
        logger.error(
            "--publish-now only applies at PUBLISH, but %s is next for %s. Use --resume.",
            PHASES[start_index], state["build"]["version"],
        )
        return 1

    ctx = Context(config, logger, state, gate2_preapproved=publish_now)
    try:
        run_pipeline(ctx, start_index)
    except OrchestratorError:
        return 1
    except Exception:
        logger.exception("unhandled exception in pipeline")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ducksteps release orchestrator")
    parser.add_argument("--resume", action="store_true", help="resume an in-progress build from its last checkpoint")
    parser.add_argument(
        "--publish-now", action="store_true",
        help="resume straight into PUBLISH with Gate 2 already answered: publishes the draft "
             "as it currently stands on GitHub, edits included. For finishing a release you "
             "have already reviewed in the browser without waiting for another ntfy tap.",
    )
    args = parser.parse_args()

    config = common.load_config()
    logger = common.setup_logging("orchestrator")
    state = common.load_state()

    lock = common.Lock()
    try:
        lock.acquire()
    except common.LockHeldError as exc:
        logger.error("cannot start: %s", exc)
        return 1

    try:
        return _run(config, logger, state, resume=args.resume, publish_now=args.publish_now)
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
