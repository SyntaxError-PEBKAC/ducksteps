from __future__ import annotations

import json
import re
import subprocess
from fnmatch import fnmatch
from pathlib import Path

import common

_PATCH_SUBJECT_LINE = re.compile(r"^Subject:\s*(.+)$", re.MULTILINE)
_FORMAT_PATCH_PREFIX = re.compile(r"^\[PATCH[^\]]*\]\s*")

_DOCS_SYNC_FILES = [
    # (relative to source_dir, relative to repo_dir, normalize_to_lf)
    (".mozconfig", "Docs/.mozconfig", False),
    (".mozconfig-Legacy", "Docs/.mozconfig-Legacy", True),
    ("build/pgo/pgo_training_extension/background.js", "Docs/PGO/background.js", False),
    ("build/pgo/pgo_training_extension/manifest.json", "Docs/PGO/manifest.json", False),
    ("build/pgo/pgo_done.html", "Docs/PGO/pgo_done.html", False),
    ("build/pgo/profileserver.py", "Docs/PGO/profileserver.py", False),
]


# The automation source itself is published alongside the release it produced, so the
# pipeline that built an artifact is auditable by whoever downloads it. Globs rather than a
# fixed list so a new module is picked up without anyone remembering to add it here.
_AUTOMATION_SYNC_GLOBS = ("*.py", "*.md", "*.ps1", "config.toml", ".gitignore")

# Never copied, whatever the globs match. This lands in a PUBLIC repo: .env holds the ntfy
# topics, which are in practice the password for the approve-gate buttons (anyone who knows
# the approve topic can approve a build), and state.json carries build state, draft URLs and
# VT history. Enforced by name below rather than left to the globs happening not to match.
_AUTOMATION_NEVER_SYNC = frozenset({".env", "state.json"})
_AUTOMATION_NEVER_SYNC_SUFFIXES = (".key", ".lock", ".log", ".png", ".pyc")

# Hand-written for the published directory, with no counterpart in the automation folder,
# so the prune in sync_automation would otherwise delete it on the next publish.
_AUTOMATION_KEEP = frozenset({"README.md"})


class PublishError(Exception):
    pass


def sync_automation(repo_dir, automation_dir, logger=None) -> list:
    """Copy the automation source into <repo>/Automation/ so the published pipeline matches
    the release it produced. Returns the files written.

    Kept separate from sync_docs_files because that one resolves paths relative to the
    Firefox source tree, and the automation lives outside it.
    """
    automation_dir, repo_dir = Path(automation_dir), Path(repo_dir)
    destination = repo_dir / "Automation"
    destination.mkdir(parents=True, exist_ok=True)

    candidates = sorted({p for glob in _AUTOMATION_SYNC_GLOBS for p in automation_dir.glob(glob)})
    synced = []
    for src in candidates:
        if not src.is_file():
            continue
        if src.name in _AUTOMATION_NEVER_SYNC or src.name.endswith(_AUTOMATION_NEVER_SYNC_SUFFIXES):
            if logger:
                logger.warning("refusing to publish %s (excluded from the public repo)", src.name)
            continue
        dst = destination / src.name
        dst.write_bytes(src.read_bytes())
        synced.append(dst)

    # Prune. This used to only ever copy, so anything renamed or deleted upstream stayed
    # published forever: _finish_publish_153_1_0.py, a one-off from the 153.1.0 manual
    # recovery, outlived the automation folder it came from and sat in the public repo
    # making a liar out of Automation/README.md ("what is in this directory is what built
    # the newest release").
    #
    # Only files this function could itself have written are eligible - a name matching one
    # of the sync globs, minus the explicit keep list - so anything hand-added to the
    # published directory outside those patterns is untouched. Names on the never-sync list
    # are swept too, regardless of the globs: if a .env or a state.json ever reaches the
    # public repo, the next publish should take it back out rather than preserve it.
    synced_names = {p.name for p in synced}
    for existing in sorted(destination.iterdir()):
        if not existing.is_file() or existing.name in synced_names:
            continue
        secret = (existing.name in _AUTOMATION_NEVER_SYNC
                  or existing.name.endswith(_AUTOMATION_NEVER_SYNC_SUFFIXES))
        stale = (existing.name not in _AUTOMATION_KEEP
                 and any(fnmatch(existing.name, g) for g in _AUTOMATION_SYNC_GLOBS))
        if not (secret or stale):
            continue
        existing.unlink()
        if logger:
            logger.warning("pruned %s from %s (%s)", existing.name, destination,
                           "must never be published" if secret else "no longer in " + str(automation_dir))

    if logger:
        logger.info("synced %d automation file(s) to %s", len(synced), destination)
    return synced


def _run_git(args, cwd, logger=None, timeout=120):
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    if result.returncode != 0:
        message = f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip()}"
        if logger:
            logger.error(message)
        raise PublishError(message)
    return result.stdout


# --- 1. Export the patch stack ---

def sync_patch_stack(repo_dir, source_dir, upstream_tag, logger=None) -> list:
    repo_dir = Path(repo_dir)
    patches_dir = repo_dir / "Patches"

    _run_git(["pull"], repo_dir, logger=logger)

    for pattern in ("000*.patch", "001*.patch"):
        for f in patches_dir.glob(pattern):
            f.unlink()

    _run_git(
        ["-C", str(source_dir), "format-patch", "--binary", "-o", str(patches_dir), f"{upstream_tag}..HEAD"],
        cwd=None, logger=logger,
    )
    new_patches = sorted(patches_dir.glob("*.patch"))
    if logger:
        logger.info("exported %d patches to %s", len(new_patches), patches_dir)
    return new_patches


# --- 2. Regenerate Patches/README.md ---

def _patch_commit_subjects_ordered(source_dir, upstream_tag, logger=None) -> list:
    """--reverse: oldest first, matching "numbered in the order they were originally
    committed" - render.py's equivalent helper deliberately returns newest-first instead,
    which is right for release-notes display but wrong for this numbered list."""
    output = _run_git(["log", "--reverse", "--pretty=format:%s", f"{upstream_tag}..HEAD"], source_dir, logger=logger)
    return [line.strip() for line in output.splitlines() if line.strip()]


def _upstream_sha(source_dir, upstream_tag, logger=None) -> str:
    return _run_git(["rev-parse", "--short=12", upstream_tag], source_dir, logger=logger).strip()


def regenerate_patches_readme(repo_dir, source_dir, upstream_tag, branch, logger=None) -> Path:
    subjects = _patch_commit_subjects_ordered(source_dir, upstream_tag, logger=logger)
    sha = _upstream_sha(source_dir, upstream_tag, logger=logger)

    patches_dir = Path(repo_dir) / "Patches"
    patch_files = sorted(f.name for f in patches_dir.glob("*.patch"))
    if len(patch_files) <= 3:
        example_range = " ".join(f"Patches/{n}" for n in patch_files)
    else:
        example_range = f"Patches/{patch_files[0]} Patches/{patch_files[1]} ... Patches/{patch_files[-1]}"

    numbered = "\n".join(f"{i}. `{subject}`" for i, subject in enumerate(subjects, start=1))

    content = f"""# ducksteps patch stack

These are the commits that turn a stock Firefox ESR checkout into ducksteps: exported with `git format-patch` from the `{branch}` branch, applied on top of upstream Mozilla commit `{sha}` (see [`../Docs/Building.md`](../Docs/Building.md) for the full build workflow).

To use them: clone [mozilla-firefox/firefox](https://github.com/mozilla-firefox/firefox), check out the matching ESR branch/tag, then apply in order:

```bash
git am --keep-cr {example_range}
```

or all at once:

```bash
git am --keep-cr Patches/*.patch
```

`--keep-cr` is required, not optional. Some of these patches touch files that are CRLF in the Firefox tree (`tools/upx-after-package.ps1`, the PGO extension sources), so their context and content lines carry carriage returns. `git am` strips trailing CRs by default, which corrupts those lines and makes the patch fail to apply.

Numbered in the order they were originally committed:

{numbered}
"""
    readme_path = patches_dir / "README.md"
    with open(readme_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    if logger:
        logger.info("regenerated %s: %d patches, base %s", readme_path, len(subjects), sha)
    return readme_path


# --- 3-4. Sync Docs/.mozconfig, .mozconfig-Legacy, Docs/PGO/* ---

def sync_docs_files(repo_dir, source_dir, logger=None) -> list:
    source_dir, repo_dir = Path(source_dir), Path(repo_dir)
    synced = []
    for src_rel, dst_rel, normalize_lf in _DOCS_SYNC_FILES:
        src, dst = source_dir / src_rel, repo_dir / dst_rel
        if not src.exists():
            if logger:
                logger.warning("sync source missing, skipping: %s", src)
            continue
        content = src.read_bytes()
        if normalize_lf:
            content = content.replace(b"\r\n", b"\n")
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(content)
        synced.append(dst)
        if logger:
            logger.info("synced %s -> %s%s", src, dst, " (normalized to LF)" if normalize_lf else "")
    return synced


# --- 5. Prepend changelog entry ---

_CHANGELOG_SEPARATOR = "\n\n---\n\n"
_CHANGELOG_HEADING = re.compile(r"^## \[([^\]]+)\]")
_FIRST_ENTRY = re.compile(r"^## \[", re.MULTILINE)


def _split_changelog(text):
    """(header, entries). The header is the document title block that must stay at the top:
    everything before the first "## [version]" entry, including its trailing divider.

    Changelog.md opens with a title, a one-line description and a divider. Prepending to the
    file as a whole buries all of that under the newest release, which is what happened to
    the 153.0 entry: the file led with a release and only reached "# Changelog" on line 100.
    """
    match = _FIRST_ENTRY.search(text)
    if not match:
        return text, ""
    return text[:match.start()], text[match.start():]


def prepend_changelog(repo_dir, changelog_entry_text, logger=None) -> Path:
    """Put the entry at the top, REPLACING any existing entry for the same version.

    Idempotent by version, not blindly prepending. Two things make that necessary now:
    PUBLISH is resumable and may re-enter this after a partial run, and it executes after
    a Gate 2 round-trip during which the release notes may have been rewritten. A blind
    prepend in either case leaves one release with two entries, the stale one on top.
    """
    changelog_path = Path(repo_dir) / "Docs" / "Changelog.md"
    existing = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""

    entry = changelog_entry_text.rstrip("\n")
    new_version = _CHANGELOG_HEADING.match(entry)

    # The title block stays put; only the entry list below it is touched.
    header, entries = _split_changelog(existing)

    # Docs/Changelog.md's own convention (confirmed against the real file): entries
    # separated by a "---" divider.
    if entries.strip():
        head, separator, tail = entries.partition(_CHANGELOG_SEPARATOR)
        head_version = _CHANGELOG_HEADING.match(head.lstrip())
        replacing = (
            separator
            and new_version
            and head_version
            and head_version.group(1) == new_version.group(1)
        )
        if replacing:
            if logger:
                logger.info("changelog already has an entry for %s, replacing it in place",
                            new_version.group(1))
            entries = entry + _CHANGELOG_SEPARATOR + tail
        else:
            entries = f"{entry}{_CHANGELOG_SEPARATOR}{entries.lstrip()}"
        new_content = header + entries
    elif header.strip():
        # Header present but no entries yet: keep the header, add the first entry under it.
        new_content = header.rstrip("\n") + "\n\n" + entry + "\n"
    else:
        new_content = entry + "\n"
    # LF explicitly, matching regenerate_patches_readme above. The docs repo stores this
    # file with LF regardless, so writing CRLF here only meant git normalized it back on
    # every commit - and left the working copy disagreeing with the committed form.
    changelog_path.write_text(new_content, encoding="utf-8", newline="\n")
    if logger:
        logger.info("prepended changelog entry to %s", changelog_path)
    return changelog_path


# --- 6-7. Commit, push, tag ---

def commit_push_tag(repo_dir, version, logger=None) -> None:
    repo_dir = Path(repo_dir)
    _run_git(["add", "-A"], repo_dir, logger=logger)

    status = _run_git(["status", "--porcelain"], repo_dir, logger=logger)
    if not status.strip():
        if logger:
            logger.warning("nothing to commit in %s for %s - proceeding to tag anyway", repo_dir, version)
    else:
        _run_git(["commit", "-m", f"Release {version}"], repo_dir, logger=logger)
        _run_git(["push"], repo_dir, logger=logger)

    # Idempotent tagging. A plain `git tag <v>` fails outright when the tag exists, which
    # a resumed PUBLISH would hit every time. Move the tag only when it actually points
    # somewhere else, so the common no-op case never force-pushes anything.
    head = _run_git(["rev-parse", "HEAD"], repo_dir, logger=logger).strip()
    tagged = subprocess.run(
        ["git", "rev-list", "-n", "1", version], cwd=repo_dir, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    existing = tagged.stdout.strip() if tagged.returncode == 0 else None

    if existing == head:
        if logger:
            logger.info("tag %s already points at %s, nothing to do", version, head[:12])
        return

    # -m explicitly: tag.gpgsign=true (see Docs, all release tags are SSH-signed) forces
    # annotation, and an annotated tag with no message opens $EDITOR. Unattended, there is
    # no editor to open, and git fails outright with "fatal: no tag message?" - confirmed
    # directly during 153.2.0's manual recovery. Passing -m sidesteps needing an editor at all.
    message = f"Release {version}"
    if existing:
        if logger:
            logger.warning("tag %s points at %s, moving it to %s", version, existing[:12], head[:12])
        _run_git(["tag", "-f", "-m", message, version], repo_dir, logger=logger)
        _run_git(["push", "-f", "origin", version], repo_dir, logger=logger)
    else:
        _run_git(["tag", "-m", message, version], repo_dir, logger=logger)
        _run_git(["push", "origin", version], repo_dir, logger=logger)
    if logger:
        logger.info("committed, pushed, and tagged %s in %s", version, repo_dir)


# --- 8, 10. GitHub release ---

def create_draft_release(repo_slug, version, title, notes_path, artifact_paths, logger=None) -> str:
    cmd = [
        "gh", "release", "create", version,
        "--repo", repo_slug,
        "--draft",
        "--title", title,
        "--notes-file", str(notes_path),
        *[str(p) for p in artifact_paths],
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    if result.returncode != 0:
        raise PublishError(f"gh release create failed: {result.stderr.strip()}")
    draft_url = result.stdout.strip()
    if logger:
        logger.info("created draft release %s: %s", version, draft_url)
    return draft_url


def publish_release(repo_slug, version, discussion_category=None, logger=None) -> None:
    """Flip the draft public, and start its release discussion in the same call.

    --discussion-category only takes effect on the draft -> published transition, which is
    exactly this call, so the discussion has to be requested here rather than at
    create_draft_release time (a draft cannot own a discussion yet).
    """
    cmd = ["gh", "release", "edit", version, "--repo", repo_slug, "--draft=false"]
    if discussion_category:
        cmd += ["--discussion-category", discussion_category]

    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    if result.returncode != 0:
        raise PublishError(f"gh release edit --draft=false failed: {result.stderr.strip()}")
    if logger:
        logger.info("published release %s", version)

    if not discussion_category:
        return

    # Report the discussion URL rather than assuming it appeared. gh exits 0 whether or not
    # the discussion was actually created (a disabled Discussions tab or a renamed category
    # both fail quietly), and a silent miss here is the kind of thing nobody notices for
    # several releases. Never fatal: the release itself is already public by this point.
    probe = subprocess.run(
        ["gh", "api", f"repos/{repo_slug}/releases/tags/{version}", "--jq", ".discussion_url"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    url = probe.stdout.strip()
    if probe.returncode == 0 and url and url != "null":
        if logger:
            logger.info("release discussion: %s", url)
    elif logger:
        logger.warning(
            "no discussion was created for %s in category %r - check that Discussions are "
            "enabled and the category name matches exactly",
            version, discussion_category,
        )


def recent_release_titles(repo_slug, limit=2, logger=None) -> list:
    result = subprocess.run(
        ["gh", "release", "list", "--repo", repo_slug, "--limit", str(limit)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    if result.returncode != 0:
        if logger:
            logger.warning("gh release list failed: %s", result.stderr.strip())
        return []
    titles = []
    for line in result.stdout.splitlines():
        match = re.search(r'"([^"]*)"', line.split("\t")[0])
        if match:
            titles.append(match.group(1))
    return titles


# --- 9. The draft round trip ---
#
# The GitHub draft, not the text rendered at ADVISORY, is the source of truth for a
# release's prose from Gate 2 onwards. The generated notes are a first draft: every release
# so far has been hand-edited in the browser before going out (153.2.0 grew a "ducksteps
# specific changes:" heading, turned raw commit subjects into written-out bullets, and cut
# the drafted summary roughly in half). Nothing read those edits back, so approving at Gate
# 2 would have committed the SUPERSEDED text to Docs/Changelog.md and tagged it - which is
# why the last two releases were rejected at Gate 2 and finished by hand instead.
#
# Reading the draft back at publish time makes "edit it in the browser, then tap Publish"
# the normal path rather than the thing that breaks the pipeline.


def _run_gh(args, timeout=60, logger=None) -> str:
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    if result.returncode != 0:
        message = f"gh {' '.join(args)} failed: {result.stderr.strip()}"
        if logger:
            logger.error(message)
        raise PublishError(message)
    return result.stdout


def find_release_id(repo_slug, version, logger=None) -> int | None:
    """Numeric id of the release whose tag_name is `version`, draft or not.

    The LIST endpoint deliberately, not "get a release by tag name": a draft has no git tag
    yet, only a tag_name field on the release object, and GitHub's by-tag endpoint does not
    serve drafts. The list endpoint does return them to a caller with push access, which is
    who runs this. Everything that has to reach a DRAFT (reading the edited body back,
    pushing the normalized text) therefore goes by id, which is unambiguous.
    """
    output = _run_gh(
        ["api", f"repos/{repo_slug}/releases", "--paginate",
         "--jq", f'.[] | select(.tag_name=="{version}") | .id'],
        logger=logger,
    )
    ids = [line.strip() for line in output.splitlines() if line.strip()]
    if not ids:
        if logger:
            logger.warning("no release found in %s with tag_name %s", repo_slug, version)
        return None
    if len(ids) > 1 and logger:
        logger.warning("%d releases in %s share tag_name %s, using the first (%s)",
                       len(ids), repo_slug, version, ids[0])
    return int(ids[0])


def fetch_release(repo_slug, version, release_id=None, logger=None) -> dict:
    """The release as GitHub currently holds it: {id, name, body, draft}.

    Raises rather than falling back to the locally rendered text if this cannot be read.
    The whole point of the call is that the local copy may be stale, so quietly substituting
    it would reintroduce exactly the mismatch this exists to prevent - and PUBLISH is
    re-runnable (`--resume`), so halting on a transient failure costs one tap, not a release.
    """
    if release_id is None:
        release_id = find_release_id(repo_slug, version, logger=logger)
    if release_id is None:
        raise PublishError(f"cannot find a release tagged {version} in {repo_slug} to publish")

    data = json.loads(_run_gh(["api", f"repos/{repo_slug}/releases/{release_id}"], logger=logger))
    return {
        "id": data["id"],
        # A release created with an empty body comes back as JSON null, not "".
        "name": data.get("name") or "",
        "body": data.get("body") or "",
        "draft": bool(data.get("draft")),
    }


def update_release_text(repo_slug, release_id, title, body, logger=None) -> None:
    """Write title/body back to the release, by id so it works on a draft."""
    _run_gh(
        ["api", "-X", "PATCH", f"repos/{repo_slug}/releases/{release_id}",
         "-f", f"name={title}", "-f", f"body={body}"],
        logger=logger,
    )
    if logger:
        logger.info("updated release %s text in %s", release_id, repo_slug)


# GitHub normalizes a release body to CRLF on the way out. Everything downstream of a fetch
# (comparison against the rendered text, the changelog entry, the local release_notes.md)
# expects LF, and a body that only differs by line endings must not read as "Tim edited it".
def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


_SHA512_MARKER = "✅ SHA512"
_HORIZONTAL_RULE = "---"


def strip_artifact_sections(release_body, logger=None) -> str:
    """The prose half of a release body: everything above the SHA512 block.

    A release body is prose, then "---", then the SHA512 list, then "---", then the
    VirusTotal list. The changelog entry is the same prose under a version heading and
    nothing else (checked against every entry in Docs/Changelog.md). So deriving one from
    the other is a single cut, and the cut is anchored on the SHA512 marker rather than on
    "the first ---" because hand-written prose is free to contain its own divider.

    The blank lines and the divider immediately preceding the marker are eaten with it -
    they belong to the artifact block, and 153.2.0's hand-edited body proves the blank line
    between the prose and that divider cannot be assumed present.
    """
    lines = normalize_newlines(release_body).splitlines()

    cut = next((i for i, line in enumerate(lines) if line.strip().startswith(_SHA512_MARKER)), None)
    if cut is None:
        # The marker is generated, never typed, so losing it means the body was restructured
        # by hand well beyond a wording tweak. Fall back to the last standalone divider,
        # which still separates prose from artifacts in any layout resembling the template,
        # and say so loudly - a wrong cut here shows up as a wrong changelog entry, and this
        # log line is what explains it.
        rules = [i for i, line in enumerate(lines) if line.strip() == _HORIZONTAL_RULE]
        if not rules:
            if logger:
                logger.warning(
                    "release body has no %r marker and no divider; using the whole body as "
                    "the changelog entry - check Docs/Changelog.md before pushing",
                    _SHA512_MARKER,
                )
            return "\n".join(lines).rstrip() + "\n"
        cut = rules[-1]
        if logger:
            logger.warning(
                "release body has no %r marker; cutting the changelog entry at the last "
                "divider (line %d) instead - check Docs/Changelog.md before pushing",
                _SHA512_MARKER, cut + 1,
            )

    while cut > 0 and (not lines[cut - 1].strip() or lines[cut - 1].strip() == _HORIZONTAL_RULE):
        cut -= 1
    return "\n".join(lines[:cut]).rstrip() + "\n"


def changelog_entry_from_release(release_body, release_title, version, release_date, logger=None) -> str:
    """Rebuild the changelog entry from the release as published.

    Mirrors render.render_changelog_entry's shape (version heading, title line, then the
    same prose the release body carries) but sources the prose from GitHub instead of from
    ReleaseData, so a hand-edited release and its changelog entry cannot drift apart.
    """
    prose = strip_artifact_sections(release_body, logger=logger)
    return f"## [{version}] ({release_date})\n\n{release_title.strip()}\n\n{prose}"


CHANGELOG_HEADER_WITH_DATE = re.compile(r"^## \[([^\]]+)\]\s*\(([^)]*)\)")


def changelog_entry_date(entry_text, default) -> str:
    """The date already stamped on a rendered changelog entry, or `default`."""
    match = CHANGELOG_HEADER_WITH_DATE.match(entry_text or "")
    return match.group(2) if match else default


# --- Cleanup sweep: em dashes, smart quotes, spacing, changelog header shape ---
# Idempotent by construction: every pattern below only matches the OLD shape (em dash
# separator in the changelog header, a run of spaces mid-line, a curly quote). An
# already-swept document doesn't match and passes through unchanged, so re-running this is
# always safe - which matters now that the sweep runs over text a human just edited, on a
# phase that can be re-entered with --resume.

_CHANGELOG_HEADER = re.compile(r"^## \[([^\]]+)\]\s*[—–]\s*(.+)$", re.MULTILINE)

# Fenced blocks and inline code spans are masked out of every prose fix below. The SHA512
# section is 128-character hashes in backticks: collapsing spaces or rewriting quotes inside
# one would corrupt a checksum, which is the one thing in these documents that has to be
# byte-exact.
_CODE_SPAN = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)


def _outside_code(text: str, transform) -> str:
    parts, last = [], 0
    for match in _CODE_SPAN.finditer(text):
        parts.append(transform(text[last:match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(transform(text[last:]))
    return "".join(parts)


def normalize_changelog_header(text: str) -> str:
    """## [X] — date -> ## [X] (date), matching the target format from render.py and
    getting rid of the header's own em dash in one move."""
    return _CHANGELOG_HEADER.sub(r"## [\1] (\2)", text)


# (?<=\S) and (?=\S) confine this to runs BETWEEN words: leading indentation (preceded by a
# newline) and a trailing double space (followed by a newline, and a hard line break in
# markdown) are both left alone.
_INTERIOR_SPACE_RUN = re.compile(r"(?<=\S)[ \t]{2,}(?=\S)")


def normalize_inline_spacing(text: str) -> str:
    """Collapse mid-line runs of whitespace.

    Replaces an older rule that only fired after a fixed list of emoji. That list was both
    incomplete by construction (a release using a new emoji silently escaped it) and aimed
    at the wrong cause: the doubled spaces in 153.2.0's published body were after a colon
    ("PGO changes:  drop old.reddit.com"), typed on a phone, and no emoji rule was ever
    going to catch that. Whoever fixed that entry by hand collapsed it to one space, so this
    is the existing editorial convention, now enforced rather than remembered.
    """
    return _outside_code(text, lambda s: _INTERIOR_SPACE_RUN.sub(" ", s))


# Typed on a phone with smart punctuation on, which is where the release notes are now
# edited. 153.2.0 went out as: It's the “out of this world" release! - an opening curly
# quote against a closing straight one, because the browser edit was made on mobile and the
# generated text was not. Its changelog entry has straight quotes, again fixed by hand.
_SMART_PUNCTUATION = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})


def normalize_quotes(text: str) -> str:
    return _outside_code(text, lambda s: s.translate(_SMART_PUNCTUATION))


def _collapse_dividers(text: str) -> str:
    lines = text.split("\n")
    out = []
    for line in lines:
        if line.strip() == "---":
            previous = next((l for l in reversed(out) if l.strip()), None)
            if previous is not None and previous.strip() == "---":
                continue  # an identical rule already separates these two blocks
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def normalize_dividers(text: str) -> str:
    """One horizontal rule between two blocks, never a stack of them.

    Two rules separated only by blank lines render as two grey lines with a gap, which is
    never what anyone meant by it. The section boundaries in a release body are generated,
    so this cannot come from render.py; it comes from editing the prose half by hand and
    leaving (or adding) a rule that the block below already had. Blank-line runs are
    collapsed in the same pass, since the same edit tends to leave those behind too and
    markdown treats three blank lines as one anyway.
    """
    return _outside_code(text, _collapse_dividers)


_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_BARE_CVE = re.compile(r"CVE-(\d{4})-(\d+)(?:/(\d+))?")


def link_bare_cve_mentions(text: str) -> str:
    """Release notes no longer carry a CVE bullet list at all, so an inline prose mention is
    now the only way a CVE ID can reach a published document - from the drafted summary,
    which is told not to name one but is free text, or from a hand-written extra section.
    Also handles the "CVE-2026-6748/6751" shorthand seen in 140.10.0 (two CVEs, same year,
    slash-separated) by linking both.

    Existing markdown links are masked out first rather than guarded against with lookaround
    assertions on the CVE pattern itself, since a CVE ID legitimately appears a second time
    inside its own URL (?id=CVE-...) - trying to distinguish "in a URL" from "bare in
    parenthetical prose" (e.g. "(CVE-2026-6746)") with lookaround alone is exactly the kind
    of thing that's easy to get subtly wrong. Masking first means the bare-CVE pass never
    sees an already-linked occurrence at all, so it can't double-touch it.
    """
    protected = []

    def _mask(match):
        protected.append(match.group(0))
        return f"\x00LINK{len(protected) - 1}\x00"

    masked = _MARKDOWN_LINK.sub(_mask, text)

    def _link(match):
        year, first_num, second_num = match.groups()
        first_id = f"CVE-{year}-{first_num}"
        result = f"[{first_id}](https://www.cve.org/CVERecord?id={first_id})"
        if second_num:
            second_id = f"CVE-{year}-{second_num}"
            result += f"/[{second_id}](https://www.cve.org/CVERecord?id={second_id})"
        return result

    masked = _BARE_CVE.sub(_link, masked)

    for i, original in enumerate(protected):
        masked = masked.replace(f"\x00LINK{i}\x00", original)
    return masked


def sweep_changelog_entry(text: str) -> str:
    """Differs from the release-body sweep only in the "## [X] - date" header, which the
    changelog has and the release body does not. The per-CVE-bullet and severity-header
    passes are gone along with the CVE list itself; link_bare_cve_mentions stays as the net
    under a CVE named inline in prose, which the drafted summary is told not to do but can."""
    text = normalize_changelog_header(text)
    text = link_bare_cve_mentions(text)
    text = common.strip_em_dashes(text)
    text = normalize_quotes(text)
    text = normalize_inline_spacing(text)
    text = normalize_dividers(text)
    return text if text.endswith("\n") else text + "\n"


def sweep_release_body(text: str) -> str:
    text = normalize_newlines(text)
    text = link_bare_cve_mentions(text)
    text = common.strip_em_dashes(text)
    text = normalize_quotes(text)
    text = normalize_inline_spacing(text)
    text = normalize_dividers(text)
    return text if text.endswith("\n") else text + "\n"


def sweep_release_title(text: str) -> str:
    """The release name gets the same prose rules as the body, minus the block-level ones.

    It is edited in the same browser field and carries the same phone-keyboard artifacts:
    153.2.0's title is the reason normalize_quotes exists. No trailing newline - this is a
    single-line field, not a document.
    """
    return normalize_inline_spacing(normalize_quotes(common.strip_em_dashes(text))).strip()
