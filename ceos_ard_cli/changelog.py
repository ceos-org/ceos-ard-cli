"""
Compile the document history of a PFS.

The document history is derived from the `changes` entries of the PFS document
and of all building blocks that are used by the PFS. The entries are grouped by
release, using the GitHub releases of the repository (tags `<PFS>-v<major>.<minor>.<patch>`).
Changes that are newer than the latest release are listed for the upcoming version.
"""

import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

import strictyaml

from .schema import ANNEX_PATH, GLOSSARY_PATH, INTRODUCTION_PATH, REQUIREMENT_CATEGORY_PATH, REQUIREMENT_PATH
from .utils.deprecation import describe_kind
from .utils.files import fix_path, read_file
from .utils.requirement import slugify
from .version import __version__

DEFAULT_GITHUB_REPO = "ceos-org/ceos-ard"
GITHUB_API_URL = "https://api.github.com"
GITHUB_RAW_URL = "https://raw.githubusercontent.com"

# ordered from the lowest to the highest level
LEVELS = ["patch", "minor", "major"]

VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)")
NEXT_LINK_PATTERN = re.compile(r'<([^>]+)>;\s*rel="next"')

# caches to avoid repeated HTTP requests within a single run
_RELEASE_CACHE = {}
_MEMBER_CACHE = {}


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


def parse_version(text):
    """Parse a SemVer version string (a `-draft` suffix is ignored) into a tuple of ints."""
    match = VERSION_PATTERN.match(str(text).strip())
    if not match:
        raise ValueError(f"Invalid version number '{text}', expected the format MAJOR.MINOR.PATCH")
    return tuple(int(part) for part in match.groups())


def format_version(version):
    return ".".join(str(part) for part in version)


def bump_version(version, level):
    """Compute the next version number for the given change level."""
    major, minor, patch = version
    if level == "major":
        return (major + 1, 0, 0)
    elif level == "minor":
        return (major, minor + 1, 0)
    elif level == "patch":
        return (major, minor, patch + 1)
    raise ValueError(f"Invalid change level '{level}', expected one of {', '.join(LEVELS)}")


def highest_level(levels):
    """Return the highest change level of the given levels, or None if empty."""
    levels = [level for level in levels if level in LEVELS]
    if not levels:
        return None
    return max(levels, key=LEVELS.index)


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------


def get_github_token():
    return os.environ.get("GITHUB_TOKEN") or None


def _http_get(url, token=None, accept=None):
    """Fetch a URL and return the body (as string) and the response headers."""
    headers = {"User-Agent": f"ceos-ard-cli/{__version__}"}
    if accept:
        headers["Accept"] = accept
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8"), response.headers
    except urllib.error.HTTPError as e:
        raise ValueError(f"Failed to fetch {url}: HTTP {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise ValueError(f"Failed to fetch {url}: {e.reason}") from e


def _next_link(link_header):
    if not link_header:
        return None
    match = NEXT_LINK_PATTERN.search(link_header)
    return match.group(1) if match else None


def _fetch_all_releases(repo, token=None):
    """Fetch all GitHub releases of the repository (cached per run)."""
    if repo in _RELEASE_CACHE:
        return _RELEASE_CACHE[repo]

    releases = []
    url = f"{GITHUB_API_URL}/repos/{repo}/releases?per_page=100"
    while url:
        body, headers = _http_get(url, token, accept="application/vnd.github+json")
        page = json.loads(body)
        if not isinstance(page, list):
            raise ValueError(f"Unexpected response from {url}")
        releases.extend(page)
        url = _next_link(headers.get("Link"))

    _RELEASE_CACHE[repo] = releases
    return releases


def fetch_releases(repo, pfs, token=None):
    """
    Get the published GitHub releases for the given PFS, sorted from the oldest to the newest version.

    Each release is a dict with the keys `version` (str), `tuple`, `date` (published date), `tag` and `url`.
    """
    token = token or get_github_token()
    pattern = re.compile(rf"^{re.escape(pfs)}-v(\d+\.\d+\.\d+)$")
    releases = []
    for release in _fetch_all_releases(repo, token):
        if release.get("draft"):
            continue
        match = pattern.match(release.get("tag_name") or "")
        published = release.get("published_at")
        if not match or not published:
            continue
        releases.append(
            {
                "version": match.group(1),
                "tuple": parse_version(match.group(1)),
                "date": datetime.fromisoformat(published).date(),
                "tag": release["tag_name"],
                "url": release.get("html_url"),
            }
        )
    releases.sort(key=lambda r: r["tuple"])
    return releases


def normalize_path(path):
    """Normalize a building block path template result to a `folder/id.yaml` style path."""
    path = fix_path(path)
    while path.startswith("./"):
        path = path[2:]
    return path


def members_from_document(document, pfs):
    """
    Get the (input directory relative) file paths of the building blocks that
    are directly referenced by a (schema-less parsed) PFS document.
    """
    members = {f"pfs/{pfs}/document.yaml"}

    def add(template, ids):
        if isinstance(ids, (str, dict)):
            ids = [ids]
        if not isinstance(ids, list):
            return
        for id in ids:
            if isinstance(id, dict):
                id = id.get("ref")
            if isinstance(id, str) and id:
                members.add(normalize_path(template.format(id=id)))

    add(INTRODUCTION_PATH, document.get("introduction"))
    add(ANNEX_PATH, document.get("annexes"))
    add(GLOSSARY_PATH, document.get("glossary"))
    blocks = document.get("requirements")
    if isinstance(blocks, list):
        for block in blocks:
            if isinstance(block, dict):
                add(REQUIREMENT_CATEGORY_PATH, block.get("category"))
                add(REQUIREMENT_PATH, block.get("requirements"))
    return members


def fetch_release_members(repo, tag, pfs):
    """
    Get the building blocks that were part of the PFS in the given release,
    by fetching the PFS document at the release tag from GitHub.

    Returns None if the document can't be retrieved or parsed.
    """
    key = (repo, tag, pfs)
    if key in _MEMBER_CACHE:
        return _MEMBER_CACHE[key]

    url = f"{GITHUB_RAW_URL}/{repo}/{tag}/pfs/{pfs}/document.yaml"
    members = None
    try:
        body, _ = _http_get(url)
        document = parse_yaml(body)
        members = members_from_document(document, pfs)
    except Exception as e:
        print(f"WARNING [{pfs}]: Can't determine the building blocks of release {tag}, {e}")

    _MEMBER_CACHE[key] = members
    return members


def parse_yaml(text):
    """Parse YAML without a schema (all scalars are strings)."""
    data = strictyaml.dirty_load(text, allow_flow_style=True).data
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Collecting changes
# ---------------------------------------------------------------------------


def relative_filepath(filepath, input_dir):
    """Make the absolute file path of a building block relative to the input directory."""
    try:
        return fix_path(Path(filepath).relative_to(Path(input_dir).resolve()))
    except ValueError:
        return normalize_path(filepath)


def parse_date(value, where):
    try:
        return date.fromisoformat(str(value))
    except ValueError as e:
        raise ValueError(f"Invalid date '{value}' in the changes of {where}: {e}") from e


def make_entries(changes, block):
    """Create the changelog entries for the given block from its `changes` list."""
    entries = []
    if not isinstance(changes, list):
        return entries
    for change in changes:
        if not isinstance(change, dict):
            continue
        entries.append(
            {
                "date": parse_date(change.get("date"), block["filepath"]),
                "level": change.get("level"),
                "change": (change.get("change") or "").rstrip(),
                "reason": (change.get("reason") or "").rstrip(),
                "author": (change.get("author") or "").rstrip(),
                "block": block,
            }
        )
    return entries


def make_block(kind, title, filepath, anchor="", direct=True):
    return {
        "kind": kind,
        "title": (title or "").strip(),
        "filepath": filepath,
        "anchor": anchor,
        # direct: the block is referenced directly in the PFS document,
        # so that its membership in a release can be checked
        "direct": direct,
    }


def collect_changes(data, input_dir, pfs=None):
    """
    Collect the changelog entries of the PFS document and of all building blocks that are used by the PFS.

    Returns a list of entries, each a dict with the keys `date`, `level`, `change`, `reason`, `author` and `block`.
    """
    pfs = pfs or data.get("id")
    seen = set()
    entries = []

    def add(container, block):
        if block["filepath"] in seen:
            return
        seen.add(block["filepath"])
        entries.extend(make_entries(container.get("changes"), block))

    # PFS document
    add(data, make_block("Document", data.get("title"), f"pfs/{pfs}/document.yaml"))

    # requirement categories and requirements
    for block in data.get("requirements") or []:
        category = block.get("category") or {}
        if category.get("filepath"):
            add(
                category,
                make_block(
                    "Requirement category",
                    category.get("title"),
                    relative_filepath(category["filepath"], input_dir),
                    f"#sec:{category['id']}" if category.get("id") else "",
                ),
            )
        for req in block.get("requirements") or []:
            if req.get("filepath"):
                add(
                    req,
                    make_block(
                        "Requirement",
                        req.get("title"),
                        relative_filepath(req["filepath"], input_dir),
                        f"#sec:{req['uid']}" if req.get("uid") else "",
                    ),
                )

    # introduction and annexes
    for kind, key, prefix in (("Introduction", "introduction", "intro-"), ("Annex", "annexes", "annex-")):
        for section in data.get(key) or []:
            if section.get("filepath"):
                add(
                    section,
                    make_block(
                        kind,
                        section.get("title"),
                        relative_filepath(section["filepath"], input_dir),
                        f"#sec:{prefix}{slugify(section['id'])}" if section.get("id") else "",
                    ),
                )

    # glossary terms (both the ones listed in the PFS document and the ones
    # referenced by building blocks are bubbled up to the top-level)
    for term in data.get("glossary") or []:
        if term.get("filepath"):
            add(
                term,
                make_block(
                    "Glossary term",
                    term.get("term"),
                    relative_filepath(term["filepath"], input_dir),
                    direct=False,
                ),
            )

    # any other building block with changes that is nested somewhere in the document
    _collect_nested(data, input_dir, add)

    return entries


def _collect_nested(data, input_dir, add):
    if isinstance(data, dict):
        if data.get("filepath") and data.get("changes"):
            kind, name = describe_kind(data)
            add(data, make_block(kind.capitalize(), name, relative_filepath(data["filepath"], input_dir), direct=False))
        for value in data.values():
            _collect_nested(value, input_dir, add)
    elif isinstance(data, list):
        for value in data:
            _collect_nested(value, input_dir, add)


def collect_former_members(members_by_version, current_members, input_dir):
    """
    Collect the changelog entries of building blocks that were part of a previous
    release, but are not part of the PFS anymore. Blocks that don't exist on disk
    anymore are skipped.
    """
    input_dir = Path(input_dir).resolve()
    former = set()
    for members in members_by_version.values():
        if members:
            former.update(members)
    former -= current_members

    entries = []
    for filepath in sorted(former):
        file = input_dir / filepath
        if not file.is_file():
            continue
        try:
            content = parse_yaml(read_file(file))
        except Exception as e:
            print(f"WARNING: Can't read the changes of the former building block {filepath}: {e}")
            continue
        kind, name = describe_kind(content)
        block = make_block(kind.capitalize(), name, filepath)
        entries.extend(make_entries(content.get("changes"), block))
    return entries


# ---------------------------------------------------------------------------
# Building the changelog
# ---------------------------------------------------------------------------


def window_min_major(current):
    """The oldest major version that is listed in the history for the given version (one major version back)."""
    return max(current[0] - 1, 0)


def build_changelog(data, releases, members_by_version=None, input_dir=".", pfs=None):
    """
    Build the document history for the given (resolved) PFS document.

    Args:
        data: The resolved PFS document (after resolve_refs, bubble_up and resolve_links).
        releases: The published releases of the PFS, see `fetch_releases`.
        members_by_version: Optional dict of version -> set of building block file paths
                            (relative to the input directory) that were part of the PFS
                            in that version. Versions without an entry aren't filtered.
        input_dir: The input directory.
        pfs: The PFS identifier (folder name), defaults to the id in data.

    Returns a dict for the template with the keys `versions`, `first_release`,
    `truncated`, `oldest_version`, `latest_release` and `current`.
    """
    pfs = pfs or data.get("id")
    members_by_version = dict(members_by_version or {})
    current = parse_version(data["version"])
    current_label = str(data["version"])

    previous = [r for r in releases if r["tuple"] < current]
    result = {
        "versions": [],
        "first_release": False,
        "truncated": False,
        "oldest_version": None,
        "latest_release": None,
        "current": current_label,
    }
    if not previous:
        # no previous release exists on GitHub, don't generate the history
        result["first_release"] = current == (1, 0, 0)
        return result

    latest = previous[-1]
    result["latest_release"] = latest["version"]

    # collect the entries of the current PFS and the blocks that were removed from the PFS
    entries = collect_changes(data, input_dir, pfs)
    current_members = {e["block"]["filepath"] for e in entries if e["block"]["direct"]}
    entries += collect_former_members(members_by_version, current_members, input_dir)

    # create a bucket for each release (up to the current version) and one for the upcoming version
    buckets = []
    for release in releases:
        if release["tuple"] <= current:
            buckets.append(_make_bucket(release["version"], release["tuple"], release["date"], True, release["url"]))
    unreleased = None
    if not any(b["tuple"] == current for b in buckets):
        unreleased = _make_bucket(current_label, current, None, False, None)
        buckets.append(unreleased)
    buckets.sort(key=lambda b: b["tuple"])

    # the current version always consists of the building blocks that are currently in the PFS
    for bucket in buckets:
        if bucket["tuple"] == current and bucket["version"] not in members_by_version:
            members_by_version[bucket["version"]] = current_members

    # assign the entries to the buckets
    for entry in entries:
        bucket = next((b for b in buckets if b["released"] and entry["date"] <= b["date"]), None)
        if bucket is None:
            if unreleased is not None:
                bucket = unreleased
            else:
                bucket = buckets[-1]
                print(
                    f"WARNING [{pfs}]: A change in {entry['block']['filepath']} is dated {entry['date']}, "
                    f"which is after the release of version {bucket['version']} ({bucket['date']})"
                )
        members = members_by_version.get(bucket["version"])
        if members is not None and entry["block"]["direct"] and entry["block"]["filepath"] not in members:
            # the building block was not part of the PFS in this version
            continue
        bucket["entries"].append(entry)

    # only keep the recent versions
    min_major = window_min_major(current)
    result["truncated"] = any(b["tuple"][0] < min_major for b in buckets)
    buckets = [b for b in buckets if b["tuple"][0] >= min_major]

    # sort and summarize
    kind_order = {"Document": 0}
    for bucket in buckets:
        bucket["entries"].sort(key=lambda e: (e["date"], -kind_order.get(e["block"]["kind"], 1)), reverse=True)
        bucket["level"] = highest_level(e["level"] for e in bucket["entries"])
        bucket["breaking"] = bucket["level"] == "major"
        bucket["proposed_version"] = None
        bucket["proposed_level"] = None
    buckets.sort(key=lambda b: b["tuple"], reverse=True)

    # propose the next version number for the upcoming release based on the changes
    if unreleased is not None and unreleased["level"]:
        proposed = bump_version(latest["tuple"], unreleased["level"])
        unreleased["proposed_version"] = format_version(proposed)
        unreleased["proposed_level"] = unreleased["level"]
        if proposed != current:
            print(
                f"WARNING [{pfs}]: The PFS document declares version {current_label}, "
                f"but the changes since version {latest['version']} suggest version "
                f"{unreleased['proposed_version']} ({unreleased['level']})"
            )

    result["versions"] = buckets
    if buckets:
        result["oldest_version"] = buckets[-1]["version"]
    return result


def _make_bucket(version, version_tuple, released_date, released, url):
    return {
        "version": version,
        "tuple": version_tuple,
        "date": released_date,
        "released": released,
        "url": url,
        "entries": [],
    }


def compile_changelog(data, input_dir, pfs, repo=DEFAULT_GITHUB_REPO):
    """
    Compile the document history for the given (resolved) PFS document,
    retrieving the releases and the building blocks of the previous releases from GitHub.
    """
    releases = fetch_releases(repo, pfs)
    current = parse_version(data["version"])
    min_major = window_min_major(current)
    members_by_version = {}
    for release in releases:
        if release["tuple"] <= current and release["tuple"][0] >= min_major:
            members_by_version[release["version"]] = fetch_release_members(repo, release["tag"], pfs)
    return build_changelog(data, releases, members_by_version, input_dir, pfs)
