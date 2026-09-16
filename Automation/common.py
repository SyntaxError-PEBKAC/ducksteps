from __future__ import annotations

import ctypes
import json
import logging
import os
import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

AUTOMATION_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = AUTOMATION_DIR / "config.toml"
ENV_PATH = AUTOMATION_DIR / ".env"
STATE_PATH = AUTOMATION_DIR / "state.json"
LOCK_PATH = AUTOMATION_DIR / "orchestrator.lock"
LOGS_DIR = AUTOMATION_DIR / "logs"
RELEASES_DIR = AUTOMATION_DIR / "releases"

# Maps .env keys onto their [section][key] home in config.toml. Extend this
# tuple, not the function, when a new secret needs overlaying.
_ENV_OVERLAYS = (
    ("NTFY_NOTIFY_TOPIC", "ntfy", "notify_topic"),
    ("NTFY_APPROVE_TOPIC", "ntfy", "approve_topic"),
)


def _load_dotenv(path: Path) -> dict:
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_config(path: Path = DEFAULT_CONFIG_PATH, env_path: Path = ENV_PATH) -> dict:
    with open(path, "rb") as f:
        config = tomllib.load(f)

    secrets = _load_dotenv(env_path)
    for env_key, section, key in _ENV_OVERLAYS:
        if env_key in secrets:
            config[section][key] = secrets[env_key]

    return config


def setup_logging(name: str) -> logging.Logger:
    LOGS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = LOGS_DIR / f"{name}-{timestamp}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(message)s"))
    logger.addHandler(file_handler)

    # sys.stdout defaults to the console codepage (cp1252) on Windows regardless of
    # redirection, which raises UnicodeEncodeError on any emoji in a log message (release
    # notes text, notification bodies) - reconfigure it rather than let that crash the process.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
    logger.addHandler(console_handler)

    return logger


def load_state(path: Path = STATE_PATH) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def update_pending_status(version: str, status: str, path: Path = STATE_PATH) -> bool:
    """Write back one field - pending_release.status - re-reading the file first.

    Not save_state(state): the caller here is the watcher, which may have been sitting on an
    approve-topic subscription for hours and whose in-memory state is correspondingly stale.
    Writing that whole snapshot back would undo everything else that touched state.json in
    the meantime, silently, which is the same failure mode SCHEDULER.md warns about for
    hand-edits during a build.

    Returns False (writing nothing) if the pending release has moved on to a different
    version in the meantime - the decision being recorded is then about something that is no
    longer the question.
    """
    state = load_state(path)
    pending = state.get("pending_release")
    if not pending or pending.get("version") != version:
        return False
    pending["status"] = status
    pending["decided_at"] = datetime.now(timezone.utc).isoformat()
    save_state(state, path)
    return True


def gate1_asked_at(pending: dict) -> str | None:
    """When the Gate 1 question that is still outstanding was put, for replaying its answer.

    Not simply last_notified_at. The watcher re-asks an unanswered Gate 1 on every run and
    stamps last_notified_at with that re-ask, so anchoring there discards anything tapped
    between the previous ask and this one - a tap five minutes before the 5pm run would be
    thrown away by the 5pm run, which is the original "Approve does nothing" bug in a
    narrower window. previous_notified_at is one ask back, which covers that gap and never
    reaches further than a single watcher interval.
    """
    return pending.get("previous_notified_at") or pending.get("last_notified_at")


def orchestrator_running(path: Path = LOCK_PATH) -> bool:
    """True if an orchestrator process is alive and holding the lock right now.

    Deliberately not Lock.acquire's fuller logic: this asks only "is someone building",
    never reclaims a stale lock, and treats an unreadable or PID-less lockfile as "no",
    because the only caller uses it to decide whether to keep its hands off state.json.
    """
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
        pid = int(info["pid"])
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return False
    return _pid_alive(pid)


def _pid_alive(pid: int) -> bool:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


def kill_pid(pid: int) -> None:
    PROCESS_TERMINATE = 0x0001
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not handle:
        return
    ctypes.windll.kernel32.TerminateProcess(handle, 1)
    ctypes.windll.kernel32.CloseHandle(handle)


_DASH_SPACED = re.compile(r"\s+[—–]\s+")
# [.!?]\s+ : normal sentence end. Bare \n : hard boundary even without terminal
# punctuation, so a dash on one line can never pair against a dash on another -
# only a theoretical safety net, no real document seen so far needs it.
_SENTENCE_SPLIT = re.compile(r"([.!?]\s+|\n)")


def _rewrite_sentence_dashes(sentence: str) -> str:
    dashes = list(_DASH_SPACED.finditer(sentence))
    if not dashes:
        return sentence
    if len(dashes) % 2 == 0:
        # An even count means the dashes pair up to bracket a parenthetical aside
        # ("X - aside - Y"), structurally, regardless of what the aside says. Flattening
        # both to semicolons reads as a run-on, since the bracketed clause usually isn't
        # an independent one - converting to parens matches what a human editor would do.
        pieces = []
        last_end = 0
        for i, match in enumerate(dashes):
            pieces.append(sentence[last_end:match.start()])
            pieces.append(" (" if i % 2 == 0 else "), ")
            last_end = match.end()
        pieces.append(sentence[last_end:])
        result = "".join(pieces)
    else:
        # Odd count (including the common case of just one): a single dash is a clause
        # break, not a bracketed aside - semicolon is the safe default there.
        result = _DASH_SPACED.sub("; ", sentence)
    return re.sub(r" {2,}", " ", result)


def strip_em_dashes(text: str) -> str:
    """Absolute project rule: no em dashes anywhere, including text quoted from Mozilla or
    pulled from historical release notes. Shared by advisory.py (CVE titles) and publish.py
    (the one-time changelog/release-body sweep). Splits into sentences first (preserving the
    exact original separators, including blank lines between paragraphs) so paired-dash
    detection in _rewrite_sentence_dashes never accidentally spans two unrelated sentences.
    """
    if not text:
        return text
    parts = _SENTENCE_SPLIT.split(text)
    parts = [_rewrite_sentence_dashes(part) if i % 2 == 0 else part for i, part in enumerate(parts)]
    text = "".join(parts)
    # Catches anything the sentence-level pass didn't (e.g. a bare, unspaced dash) -
    # a plain substitution is the safe fallback since by this point it's already known
    # not to be part of a structurally-detected paired aside.
    return text.replace("—", ";").replace("–", ";")


_ESR_VERSION = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?esr$")


def parse_esr_version(version_string: str) -> tuple[int, int, int | None]:
    """(major, minor, patch) from a FIREFOX_ESR / FIREFOX_ESR_NEXT string.

    Two shapes exist upstream and both are load-bearing. The ordinary point release is
    three-component ("140.13.0esr"). The FIRST release of a new ESR line is
    two-component ("153.0esr") - it has no patch part at all, and patch is returned as
    None rather than 0 to preserve that. Everything downstream has to keep the
    distinction, because upstream's own artifacts do: the tag is
    FIREFOX_153_0esr_RELEASE (not FIREFOX_153_0_0esr_RELEASE) and version.txt at that
    tag reads "153.0" (not "153.0.0"), both confirmed against origin rather than
    assumed. Collapsing the two shapes here would put VERIFY_TAG and VERIFY_VER into a
    halt on the very first build of every new ESR line.
    """
    match = _ESR_VERSION.match(version_string)
    if not match:
        raise ValueError(f"unrecognized ESR version format: {version_string!r}")
    major, minor, patch = match.groups()
    return int(major), int(minor), None if patch is None else int(patch)


def version_number(major: int, minor: int, patch: int | None) -> str:
    """The plain version as it appears in browser/config/version.txt."""
    parts = (major, minor) if patch is None else (major, minor, patch)
    return ".".join(str(part) for part in parts)


def release_tag(major: int, minor: int, patch: int | None) -> str:
    """Upstream's git tag for that ESR release. Verified against origin's real tag list:
    FIREFOX_140_13_0esr_RELEASE and FIREFOX_153_0esr_RELEASE both exist in exactly this
    form, so the underscore count follows the version's component count."""
    return f"FIREFOX_{version_number(major, minor, patch).replace('.', '_')}esr_RELEASE"


def tag_exists(source_dir: Path, tag: str) -> bool:
    result = subprocess.run(
        ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}"],
        cwd=source_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git ls-remote failed: {result.stderr.strip()}")
    return bool(result.stdout.strip())


class LockHeldError(RuntimeError):
    pass


class Lock:
    """PID-based lockfile with a stale timeout, guarding against a second orchestrator instance."""

    # 72h, not 24: a live PID already blocks acquisition on its own, so this timeout only
    # decides how long to trust a PID NUMBER that may since have been reused. A ~10h build
    # followed by a Gate 2 held open for a day of note editing is now an ordinary run, and at
    # 24h that run's own lock became reclaimable while it was still holding it.
    def __init__(self, path: Path = LOCK_PATH, stale_timeout_seconds: int = 72 * 3600):
        self.path = path
        self.stale_timeout_seconds = stale_timeout_seconds

    def acquire(self) -> None:
        if self.path.exists():
            pid = None
            started_at = None
            try:
                info = json.loads(self.path.read_text(encoding="utf-8"))
                pid = info["pid"]
                started_at = datetime.fromisoformat(info["started_at"])
            except (json.JSONDecodeError, KeyError, ValueError):
                pass

            if pid is not None:
                age_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
                if _pid_alive(pid) and age_seconds < self.stale_timeout_seconds:
                    raise LockHeldError(
                        f"Lock held by PID {pid}, started {started_at.isoformat()} "
                        f"({age_seconds / 3600:.1f}h ago)"
                    )
            self.path.unlink()

        info = {
            "pid": os.getpid(),
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        self.path.write_text(json.dumps(info), encoding="utf-8")

    def release(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def __enter__(self) -> "Lock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
