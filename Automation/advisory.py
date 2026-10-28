from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests
import yaml

GITHUB_API_BASE = "https://api.github.com/repos/mozilla/foundation-security-advisories"
ADVISORIES_INDEX_URL = "https://www.mozilla.org/en-US/security/advisories/"


class AdvisoryError(Exception):
    """Neither the structured YAML source nor the mozilla.org fallback could give a
    definitive answer. Never guessed at - the caller must halt, per Phase 6's whole reason
    for existing: an LLM must never be left to invent a CVE list."""


@dataclass
class Advisory:
    mfsa_number: str | None
    mfsa_url: str | None
    announced_date: str | None
    cves: list = field(default_factory=list)  # [{id, impact}] - see _advisory_from_yaml

    @classmethod
    def empty(cls) -> "Advisory":
        return cls(mfsa_number=None, mfsa_url=None, announced_date=None, cves=[])


def _fixed_in_candidates(version) -> list:
    """The strings Mozilla's own `fixed_in` uses for this release, most specific first.

    Two-component versions ("153.0") are the first release of a new ESR line, and upstream
    labels those differently: the ESR ships the same code as the matching rapid release on
    that day, so the advisory's fixed_in tends to say "Firefox 153" rather than
    "Firefox ESR 153.0". Later releases on the line ("153.1.0") go back to the ordinary
    "Firefox ESR x.y.z" form. Only the two-component case gets the plain-Firefox
    candidates - offering them for a point release would let an unrelated rapid-release
    advisory match.

    The x.y.0 release of a line is often labelled "Firefox ESR x.y" (MFSA 2026-108 says
    "Firefox ESR 153.5"), so that form is a candidate for x.y.0 only. Offering it for
    x.y.1 and later made 153.5.1 match the 153.5.0 advisory and ship its CVE list.
    """
    parts = version.split(".")
    candidates = [f"Firefox ESR {version}"]
    if len(parts) == 3:
        if parts[2] == "0":
            candidates.append(f"Firefox ESR {parts[0]}.{parts[1]}")
    else:
        candidates.append(f"Firefox {version}")
        candidates.append(f"Firefox {parts[0]}")
    return candidates


def _matches_version(fixed_in_list, version) -> bool:
    candidates = set(_fixed_in_candidates(version))
    return any((entry or "").strip() in candidates for entry in (fixed_in_list or []))


def _list_advisory_files(year, timeout=30):
    """Returns [(filename, download_url), ...] for that year's mfsa*.yml files, or []
    if the year directory doesn't exist yet (e.g. checking next year too early)."""
    url = f"{GITHUB_API_BASE}/contents/announce/{year}"
    r = requests.get(url, timeout=timeout)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return [
        (entry["name"], entry["download_url"])
        for entry in r.json()
        if entry["name"].startswith("mfsa") and entry["name"].endswith(".yml")
    ]


def _fetch_yaml(download_url, timeout=30):
    r = requests.get(download_url, timeout=timeout)
    r.raise_for_status()
    return yaml.safe_load(r.text)


def _non_windows_marker(details, markers):
    """The marker that scopes this advisory to a platform we don't build for, or None.

    Matches against title and description together, because upstream puts the scoping in
    whichever of the two it feels like on the day ("... in Firefox for Android" in a title,
    "Note: this bug only affects Android" in a description). Returns the matched marker
    rather than a bool so the caller can log WHY something was dropped.
    """
    if not markers:
        return None
    haystack = " ".join([
        (details or {}).get("title", "") or "",
        (details or {}).get("description", "") or "",
    ]).lower()
    for marker in markers:
        if marker.lower() in haystack:
            return marker
    return None


def _advisory_from_yaml(filename, data, non_windows_markers=(), logger=None) -> Advisory:
    mfsa_number = filename.removeprefix("mfsa").removesuffix(".yml")  # "mfsa2026-13.yml" -> "2026-13"
    cves = []
    dropped = []
    for cve_id, details in (data.get("advisories") or {}).items():
        marker = _non_windows_marker(details, non_windows_markers)
        if marker:
            dropped.append((cve_id, marker))
            continue
        # id and impact only. The per-CVE title and cve.org URL used to feed the severity
        # listing in the release notes; nothing renders individual CVEs any more, so parsing
        # them just carried dead fields (and a strip_em_dashes call) through every release.
        # The full detail stays one click away, at mfsa_url.
        cves.append({
            "id": cve_id,
            "impact": (details or {}).get("impact", "").lower(),
        })
    if dropped and logger:
        # Logged individually and by name: a reader of this log has to be able to
        # reconstruct exactly which upstream CVEs were left out of a shipped release.
        logger.info("advisory %s: keeping %d of %d CVEs, dropped %d as non-Windows",
                    mfsa_number, len(cves), len(cves) + len(dropped), len(dropped))
        for cve_id, marker in dropped:
            logger.info("  dropped %s (matched %r)", cve_id, marker)
    return Advisory(
        mfsa_number=mfsa_number,
        mfsa_url=f"https://www.mozilla.org/en-US/security/advisories/mfsa{mfsa_number}/",
        announced_date=data.get("announced"),
        cves=cves,
    )


def _candidate_years():
    now = datetime.now(timezone.utc)
    return [now.year, now.year - 1]


def _try_yaml_search(version, non_windows_markers=(), logger=None):
    """Returns (Advisory_or_None, error_or_None). None/None means the source was reachable
    and searched completely but genuinely has nothing for this version."""
    try:
        for year in _candidate_years():
            for name, download_url in _list_advisory_files(year):
                data = _fetch_yaml(download_url)
                if data and _matches_version(data.get("fixed_in", []), version):
                    if logger:
                        logger.info("found %s for %s via structured YAML", name, version)
                    return _advisory_from_yaml(name, data, non_windows_markers, logger), None
        return None, None
    except (requests.RequestException, yaml.YAMLError) as exc:
        if logger:
            logger.warning("YAML advisory search failed: %s", exc)
        return None, exc


def _try_scrape_search(version, logger=None):
    """Fallback: confirms an MFSA exists and its number/URL, nothing more - the index page
    doesn't carry CVE-level detail, so this can never be used to build a full CVE list."""
    try:
        r = requests.get(ADVISORIES_INDEX_URL, timeout=30)
        r.raise_for_status()
    except requests.RequestException as exc:
        if logger:
            logger.warning("advisories index scrape failed: %s", exc)
        return None, exc

    candidates = _fixed_in_candidates(version)
    # A bare substring test would let "Firefox ESR 153.5" match a 153.5.1 line and
    # "Firefox ESR 153.5.1" match 153.5.10, so a candidate must stand alone as a version.
    patterns = [re.compile(rf"(?<![\w.]){re.escape(c)}(?!\w|\.\d)") for c in candidates]
    for line in r.text.splitlines():
        if any(p.search(line) for p in patterns):
            match = re.search(r"mfsa(\d{4}-\d+)", line, re.IGNORECASE)
            if match:
                mfsa_number = match.group(1)
                if logger:
                    logger.info("found MFSA %s for %s via mozilla.org fallback scrape", mfsa_number, version)
                return {
                    "mfsa_number": mfsa_number,
                    "mfsa_url": f"https://www.mozilla.org/en-US/security/advisories/mfsa{mfsa_number}/",
                }, None
    return None, None


def _nothing_found(version, allow_no_advisory, detail, logger):
    """Both sources came back without an advisory for `version`. That is indistinguishable
    from Mozilla not having published it yet (the YAML repo can lag the release), and a
    release shipped on that guess carries no security section at all. So it halts unless
    the version was explicitly declared to have no security content."""
    if allow_no_advisory:
        if logger:
            logger.warning("no advisory found for %s (%s); proceeding because the version is "
                           "listed in [advisory] no_security_versions", version, detail)
        return Advisory.empty()
    raise AdvisoryError(
        f"no advisory found for {version} ({detail}). Mozilla may not have published it yet: "
        f"rerun with --resume once it appears. If this release genuinely has no security "
        f"content, add \"{version}\" to [advisory] no_security_versions in config.toml."
    )


def resolve_advisory(version, non_windows_markers=(), logger=None, allow_no_advisory=False) -> Advisory:
    """Resolves the MFSA/CVE data for `version` (e.g. "140.14.0"). Returns Advisory.empty()
    only when allow_no_advisory is set (the version is listed in [advisory]
    no_security_versions) and no advisory exists. It raises AdvisoryError when neither
    source could give a definitive answer, when they disagree, or when nothing is found
    for a version not declared to have no security content.

    non_windows_markers drops CVEs upstream scopes to platforms ducksteps doesn't build
    for (see [advisory] in config.toml). It only ever filters the CVE list; it never
    affects whether an MFSA is considered found, so an advisory whose every CVE is
    Android-only still resolves and still reports its MFSA number rather than
    masquerading as "no security content".
    """
    yaml_advisory, yaml_error = _try_yaml_search(version, non_windows_markers, logger=logger)
    if yaml_advisory is not None:
        return yaml_advisory

    scrape_hit, scrape_error = _try_scrape_search(version, logger=logger)

    if yaml_error is None and scrape_error is None:
        if scrape_hit is None:
            return _nothing_found(version, allow_no_advisory, "both sources searched", logger)
        raise AdvisoryError(
            f"mozilla.org shows {scrape_hit['mfsa_number']} for {version} but the structured "
            f"YAML repo doesn't - sources disagree, halting rather than guessing CVE details."
        )

    if scrape_hit is not None:
        raise AdvisoryError(
            f"MFSA {scrape_hit['mfsa_number']} confirmed for {version} via the mozilla.org "
            f"fallback, but the structured YAML source errored ({yaml_error}) - cannot build "
            f"a reliable CVE list from a scrape alone."
        )

    if yaml_error is not None and scrape_error is not None:
        raise AdvisoryError(
            f"neither advisory source could be reached for {version}: YAML={yaml_error}, scrape={scrape_error}"
        )

    return _nothing_found(
        version, allow_no_advisory,
        f"one source errored (yaml={yaml_error}, scrape={scrape_error}), the other found nothing",
        logger,
    )
