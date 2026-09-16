from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

_DEFAULT_LOGGER = logging.getLogger("notify")

# Notification matrix (Phase 3 spec): event -> priority.
PRIORITIES = {
    "gate1": "default",
    "build_started": "low",
    "retrying": "low",
    "smoke_ready": "high",
    "fatal_error": "urgent",
    "vt_flagged": "urgent",
    "draft_ready": "high",
    "published": "default",
    "gate2_halt": "high",
}

SNOOZE_INTERVAL_SECONDS = 3 * 3600
MAX_SNOOZES = 3
# Per-connection idle timeout for poll_topic, not a reconnect cadence: requests'
# timeout= during streaming is a read/inactivity timeout that resets on every
# received chunk, and ntfy sends a keepalive well under 60s, so one connection
# normally holds for the whole snooze window. This only fires if the server
# actually goes quiet.
POLL_SECONDS = 60

# Subtracted from every freshly-taken `since` anchor. ntfy compares `since=<unix ts>`
# against the SERVER's clock, so a PC clock running fast would silently place the anchor
# after a tap that has already happened and drop it - the one direction of clock skew that
# loses messages. A minute of slack costs nothing: an over-wide window can only replay
# messages that are then matched or ignored on their body.
CLOCK_SKEW_MARGIN_SECONDS = 60

# What ntfy.sh will still hand back to a late subscriber. Measured, not assumed: a message
# published to a fresh topic came back with expires - time == 43200. This is what makes a
# tap survive at all while nothing is connected, and therefore the ceiling on how long a
# gate can go unanswered-but-recoverable.
CACHE_WINDOW_SECONDS = 12 * 3600


def _encode_header(value: str) -> bytes:
    """ntfy titles/actions carry emoji; http.client refuses non-latin1 str headers, so send raw UTF-8 bytes."""
    return value.encode("utf-8")


def _headers(title, priority, *, actions=None, tags=None, click=None, message=None, filename=None) -> dict:
    headers = {"Title": _encode_header(title), "Priority": priority}
    if actions:
        headers["Actions"] = _encode_header("; ".join(actions))
    if tags:
        headers["Tags"] = ",".join(tags)
    if click:
        headers["Click"] = click
    if message is not None:
        headers["Message"] = _encode_header(message)
    if filename:
        headers["Filename"] = filename
    return headers


def _topic_url(config: dict, topic_key: str) -> str:
    ntfy = config["ntfy"]
    topic = ntfy[topic_key]
    if not topic:
        raise RuntimeError(f"ntfy {topic_key} is not configured (check .env)")
    return f"{ntfy['server'].rstrip('/')}/{topic}"


def publish(config, title, body, *, priority="default", actions=None, tags=None, click=None) -> None:
    url = _topic_url(config, "notify_topic")
    headers = _headers(title, priority, actions=actions, tags=tags, click=click)
    response = requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=15)
    response.raise_for_status()


def publish_file(config, title, message, file_path, *, priority="default", actions=None, tags=None) -> None:
    url = _topic_url(config, "notify_topic")
    file_path = Path(file_path)
    headers = _headers(title, priority, actions=actions, tags=tags, message=message, filename=file_path.name)
    with open(file_path, "rb") as f:
        response = requests.put(url, data=f, headers=headers, timeout=60)
    response.raise_for_status()


def _approve_url(config: dict) -> str:
    return _topic_url(config, "approve_topic")


# --- Notification matrix: one function per event type ---

def send_gate1(config, version) -> None:
    approve_url = _approve_url(config)
    actions = [
        f"http, ✅ Approve, {approve_url}, method=POST, body=approve-{version}",
        f"http, ⏰ Wait 3h, {approve_url}, method=POST, body=snooze-{version}",
        f"http, \U0001f6d1 Reject, {approve_url}, method=POST, body=reject-{version}",
    ]
    publish(
        config,
        title=f"ducksteps {version} ready to build",
        body="Upstream tagged. Both variants, roughly 10 hours.",
        priority=PRIORITIES["gate1"],
        actions=actions,
    )


def send_build_started(config, version) -> None:
    publish(
        config,
        title=f"ducksteps {version} build started",
        body="PREFLIGHT passed, pipeline running. Expect roughly 10 hours.",
        priority=PRIORITIES["build_started"],
    )


def send_retrying(config, version, reason) -> None:
    publish(
        config,
        title=f"ducksteps {version} retrying",
        body=f"Known-recoverable failure, retrying once: {reason}",
        priority=PRIORITIES["retrying"],
    )


def send_smoke_test_ready(config, version, variant, screenshot_path) -> None:
    approve_url = _approve_url(config)
    actions = [
        f"http, ✅ Looks good, {approve_url}, method=POST, body=smoke-ok-{version}-{variant}",
        f"http, \U0001f6d1 Reject, {approve_url}, method=POST, body=smoke-reject-{version}-{variant}",
    ]
    publish_file(
        config,
        title=f"ducksteps {version} {variant} smoke test",
        message="Firefox launched, here's the window. Approve to continue packaging.",
        file_path=screenshot_path,
        priority=PRIORITIES["smoke_ready"],
        actions=actions,
    )


def send_fatal_error(config, version, summary, log_path) -> None:
    # No remote log-viewing mechanism exists in this project (web dashboards are
    # explicitly out of scope), so unlike the other gates this has no real target
    # for a button. The path goes in the body text instead of a dead "View log" action.
    publish(
        config,
        title=f"ducksteps {version} FATAL",
        body=f"{summary}\n\nLog: {log_path}",
        priority=PRIORITIES["fatal_error"],
    )


def send_vt_flagged(config, version, summary) -> None:
    approve_url = _approve_url(config)
    actions = [
        f"http, ✅ Approve, {approve_url}, method=POST, body=vt-approve-{version}",
        f"http, \U0001f6d1 Halt, {approve_url}, method=POST, body=vt-halt-{version}",
    ]
    publish(
        config,
        title=f"ducksteps {version} VirusTotal flagged",
        body=summary,
        priority=PRIORITIES["vt_flagged"],
        actions=actions,
    )


# Sent the moment "✏️ Still editing" is tapped, which is the last point before the browser
# is opened and therefore the only point where this can still be read in time. The mistake
# it exists to prevent is a natural one - you are already on the release page, GitHub's own
# "Publish release" button is right there, and pressing it looks like it finishes the job.
# It does not: publishing from GitHub tags the release at whatever the default branch
# pointed to when the draft was created, and skips the changelog entry, the patch-stack
# export, the docs sync, the release commit and the discussion. That is precisely the state
# the last two releases had to be recovered from by hand.
EDITING_INSTRUCTIONS = (
    # Plain text, no markdown: the ntfy phone apps render the body literally unless the
    # Markdown header is set, and asterisks around the one instruction that matters would
    # be worse than no emphasis at all.
    "Edit the draft on GitHub, then hit Save draft.\n\n"
    "Do NOT use GitHub's own \"Publish release\" button. Publishing there skips the "
    "changelog, the version tag, the release commit and the discussion, and leaves a "
    "release that has to be fixed up by hand.\n\n"
    "Come back and tap ✅ Publish here when you are done. Whatever the draft says at that "
    "moment is what ships, changelog included."
)


def send_draft_ready(config, version, draft_url, *, reminder=False) -> None:
    """Gate 2. Three buttons, because editing the notes is the expected case, not an escape hatch.

    "Still editing" buys another window instead of forcing a decision inside one: the draft
    is meant to be rewritten in the browser before it ships, and a gate that expires while
    you are doing the thing it asked you to do is the reason the last two releases were
    finished by hand. PUBLISH reads the draft back at approval time, so whatever the draft
    says when you finally tap Publish is what goes into the release, the changelog and the
    commit. Reject still means reject.
    """
    approve_url = _approve_url(config)
    actions = [
        f"http, ✅ Publish, {approve_url}, method=POST, body=publish-{version}",
        f"http, ✏️ Still editing, {approve_url}, method=POST, body=edit-draft-{version}",
        f"http, \U0001f6d1 Reject, {approve_url}, method=POST, body=reject-draft-{version}",
    ]
    lead = "Still holding." if reminder else "Review before it goes public."
    publish(
        config,
        title=f"ducksteps {version} draft ready",
        body=f"{lead} Edit the draft on GitHub and Save draft; don't use GitHub's own "
             f"Publish button. Whatever the draft says when you tap ✅ Publish here is what "
             f"ships, changelog included.\n\n{draft_url}",
        priority=PRIORITIES["draft_ready"],
        actions=actions,
        click=draft_url,
    )


def send_gate2_halt(config, version, reason, draft_url) -> None:
    """Gate 2 ended without a publish. Says how to pick it back up, because the answer is
    two commands and neither is obvious at the point you need it."""
    publish(
        config,
        title=f"ducksteps {version} not published",
        body=(
            f"{reason}\n\nThe draft and its artifacts are intact. To re-ask Gate 2: "
            "python orchestrator.py --resume. To publish an already-edited draft without "
            "waiting for a tap: python orchestrator.py --publish-now.\n\n"
            f"{draft_url}"
        ),
        priority=PRIORITIES["gate2_halt"],
        click=draft_url,
    )


def send_published(config, version, release_url) -> None:
    publish(
        config,
        title=f"ducksteps {version} published",
        body="It's live.",
        priority=PRIORITIES["published"],
        actions=[f"view, View release, {release_url}"],
        click=release_url,
    )


# --- Receiving: approve_topic long-poll ---

def anchor(at=None) -> int:
    """A `since` value meaning "from about now onwards", for a gate that is about to be asked.

    Take it BEFORE sending the notification, not after: everything between the send and the
    moment the subscription is actually established (TLS handshake included) is a window in
    which a tap lands on the topic with nobody attached, and an anchor taken afterwards
    excludes exactly that window.
    """
    return int(at if at is not None else time.time()) - CLOCK_SKEW_MARGIN_SECONDS


def anchor_from_iso(timestamp) -> int | None:
    """A `since` value from a state.json timestamp (pending_release.last_notified_at).

    This is what lets a gate be answered by a tap that happened while nothing was listening:
    ntfy holds messages for CACHE_WINDOW_SECONDS, so subscribing with the moment the question
    was asked replays the answer instead of waiting for it to be given again. Returns None
    for a missing or unparseable timestamp, which callers read as "anchor at now".
    """
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return anchor(parsed.timestamp())


class Cursor:
    """Where the next subscription should resume from, carried across reconnects.

    poll_topic reconnects - on its idle timeout, on a dropped connection, and after every
    message it hands back - and each reconnect used to start a brand-new "from now on"
    subscription, so a tap arriving in the reconnect gap was simply never seen. A Cursor
    turns that sequence of independent windows into one continuous one: each message
    advances it past that exact message id, so the next connection resumes immediately
    after it, with neither a gap nor a redelivery.
    """

    def __init__(self, since=None):
        self.value = anchor() if since is None else since

    def advance(self, event) -> None:
        # ntfy always stamps an id (verified against a live topic), and `since=<id>` is
        # exclusive, which is exactly the "resume after this one" semantics wanted here.
        # The time-based fallback only exists so a hypothetical id-less message can still
        # move the cursor: leaving it unchanged would replay that same message forever and
        # spin await_decision into a hot loop.
        self.value = event.get("id") or int(event.get("time", time.time())) + 1


def poll_topic(config, topic_key, timeout_seconds=POLL_SECONDS, since=None):
    """One bounded long-poll against an ntfy topic. Returns the first message event seen as a
    dict (`message`, `id`, `time`, ...), or None if the window closes with nothing new.

    `since` is passed straight to ntfy and decides what the subscription can see. Omitted, it
    streams only messages published after the connection opens, with no cached-backlog replay
    (confirmed empirically against a topic with a pre-existing cached message; note this is
    not the same as `since=now`, which ntfy's API rejects with 400). Given a unix timestamp or
    a message id, it replays from there first and then streams - which is the only reason a
    tap made while the PC was not subscribed can still be honoured.

    Timeouts and connection drops are treated as routine and swallowed - a
    read-timeout while streaming surfaces as requests.exceptions.ConnectionError
    (wrapping urllib3's ReadTimeoutError), not requests.exceptions.Timeout, so both
    are caught here. HTTPError (bad status codes) is deliberately NOT caught: that
    means a real misconfiguration, and staying silent there would be indistinguishable
    from "no message yet" for hours - which is exactly how an earlier since="now" bug
    here went undetected until tested directly: ntfy's 400 was swallowed by a
    too-broad except clause.
    """
    ntfy = config["ntfy"]
    topic = ntfy[topic_key]
    url = f"{ntfy['server'].rstrip('/')}/{topic}/json"
    params = {} if since is None else {"since": str(since)}
    try:
        with requests.get(url, params=params, stream=True, timeout=timeout_seconds) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                if event.get("event") == "message":
                    return event
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        return None
    return None


def send_tap_confirmation(config, action_body, *, title=None, detail=None) -> None:
    """iOS ntfy issue #1728: clear=true never dismisses the source notification, so echo receipt back explicitly.

    The echo is also the only notification that arrives at the instant of a tap, which makes
    it the right place to put anything you need to read BEFORE acting on the button you just
    pressed - see EDITING_INSTRUCTIONS.
    """
    publish(
        config,
        title=title or "ducksteps: got it",
        body=detail or f"Received: {action_body}",
        priority="default",
    )


def await_decision(config, timeout_seconds, valid_bodies, logger=None, confirmations=None,
                   cursor=None) -> str:
    """
    Long-polls the approve_topic until a message matching a key in `valid_bodies`
    arrives, or timeout_seconds elapses with nothing relevant. Sends the iOS
    tap-confirmation workaround on any match. `valid_bodies` maps an exact expected
    message body (e.g. "smoke-ok-140.14.0-zen5") to the outcome string to return
    for it (e.g. "approved"). Returns "no_response" on timeout.

    `confirmations` optionally maps the same message bodies to a (title, body) pair to send
    back instead of the bare "Received: ..." echo, for a button whose confirmation needs to
    say something rather than just prove the tap landed.

    `cursor` is the Cursor to resume from, and is mutated in place as messages arrive, so a
    caller that calls this repeatedly (the snooze loops below) stays continuous across the
    boundary between one window and the next. Build it BEFORE sending the notification the
    question belongs to. Omitted, the window starts at "about now", which silently discards
    anything tapped before this call - correct only when nothing has been asked yet.
    """
    log = logger or _DEFAULT_LOGGER
    cursor = cursor if cursor is not None else Cursor()
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        event = poll_topic(config, "approve_topic",
                           timeout_seconds=min(POLL_SECONDS, remaining), since=cursor.value)
        if not event:
            continue
        cursor.advance(event)
        message = event.get("message", "")
        if not message:
            continue
        if message in valid_bodies:
            title, detail = (confirmations or {}).get(message, (None, None))
            send_tap_confirmation(config, message, title=title, detail=detail)
            return valid_bodies[message]
        log.info("ignoring unrelated approve-topic message: %s", message)
    return "no_response"


def await_gate2_decision(config, version, draft_url, window_seconds, max_snoozes, logger=None,
                         since=None) -> str:
    """
    Waits for a response to an already-sent Gate 2 notification for `version`.
    Returns "approved", "rejected", or "no_response".

    Shaped like await_gate1_decision but with its own budget, because the two gates are
    waiting on different things. Gate 1 asks a yes/no question that takes ten seconds to
    answer. Gate 2 asks you to read and usually rewrite a release document, which realistically
    means opening a laptop, and a single gate_wait_hours window that starts whenever the build
    happens to finish is not a window anyone can count on being awake for.
    """
    log = logger or _DEFAULT_LOGGER
    snoozes_used = 0
    # Gate 2 is asked at the end of DRAFT but waited on in PUBLISH, and a --resume re-enters
    # PUBLISH hours later without re-asking at all, so `since` (when the draft notification
    # went out) is what makes a tap from before this process existed still count.
    cursor = Cursor(since)
    valid_bodies = {
        f"publish-{version}": "approved",
        f"reject-draft-{version}": "rejected",
        f"edit-draft-{version}": "snooze",
    }
    confirmations = {
        f"edit-draft-{version}": (f"ducksteps {version}: still editing", EDITING_INSTRUCTIONS),
    }

    while True:
        log.info(
            "waiting up to %.1fh for a Gate 2 response on %s (extension %d/%d used)",
            window_seconds / 3600, version, snoozes_used, max_snoozes,
        )
        outcome = await_decision(config, window_seconds, valid_bodies, logger=log,
                                 confirmations=confirmations, cursor=cursor)

        if outcome != "snooze":
            return outcome  # "approved" / "rejected" / "no_response"

        snoozes_used += 1
        if snoozes_used > max_snoozes:
            log.info("Gate 2 extension cap reached for %s, leaving the draft unpublished", version)
            return "no_response"
        log.info("still editing (%d/%d), re-asking in %.1fh", snoozes_used, max_snoozes, window_seconds / 3600)
        send_draft_ready(config, version, draft_url, reminder=True)


GATE1_APPROVED_DETAIL = (
    "Approval recorded. The build does not start by itself: PGO training needs a real "
    "unlocked session on the PC (Invariant 2), so nothing here can launch it for you.\n\n"
    "Start it at the machine - Task Scheduler, run \"ducksteps orchestrator\" - and it will "
    "pick this approval straight up instead of asking again."
)


def await_gate1_decision(config, version, logger=None, since=None) -> str:
    """
    Waits for a response to an already-sent Gate 1 notification for `version`.
    Snooze policy: up to MAX_SNOOZES re-asks, SNOOZE_INTERVAL_SECONDS apart.
    Returns "approved", "rejected", or "no_response".

    `since` should be when Gate 1 was last asked (pending_release.last_notified_at). Gate 1
    is the one gate whose question is asked by one process and answered to another, so a
    caller that starts up after the fact has to replay from the question rather than from
    its own start - otherwise a tap made while nothing was subscribed is simply gone.
    """
    log = logger or _DEFAULT_LOGGER
    snoozes_used = 0
    if isinstance(since, int) and time.time() - since > CACHE_WINDOW_SECONDS:
        # Says out loud the one case where a tap really is unrecoverable, so it never again
        # has to be guessed at from silence.
        log.warning(
            "Gate 1 for %s was last asked over %.0fh ago, beyond ntfy's cache: any tap made "
            "then is gone and the answer has to be given again",
            version, CACHE_WINDOW_SECONDS / 3600,
        )
    cursor = Cursor(since)
    valid_bodies = {
        f"approve-{version}": "approved",
        f"reject-{version}": "rejected",
        f"snooze-{version}": "snooze",
    }
    # Approving is the one tap whose visible effect is nothing happening for hours, because
    # the build still has to be started by hand. Without this, a recorded approval and a
    # dropped one look exactly alike from the phone - which is what made a broken button
    # indistinguishable from a working one.
    confirmations = {
        f"approve-{version}": (f"ducksteps {version}: approved", GATE1_APPROVED_DETAIL),
    }

    while True:
        log.info(
            "waiting up to %.0fm for a Gate 1 response on %s (snooze %d/%d used)",
            SNOOZE_INTERVAL_SECONDS / 60, version, snoozes_used, MAX_SNOOZES,
        )
        outcome = await_decision(config, SNOOZE_INTERVAL_SECONDS, valid_bodies, logger=log,
                                 confirmations=confirmations, cursor=cursor)

        if outcome != "snooze":
            return outcome  # "approved" / "rejected" / "no_response"

        snoozes_used += 1
        if snoozes_used > MAX_SNOOZES:
            log.info("snooze cap reached for %s, stopping until the next watcher run", version)
            return "no_response"
        log.info("snoozed (%d/%d), re-asking in %.0fh", snoozes_used, MAX_SNOOZES, SNOOZE_INTERVAL_SECONDS / 3600)
        send_gate1(config, version)
