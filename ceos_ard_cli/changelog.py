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
from .utils.git import read_objects, run_git
from .utils.requirement import slugify
from .version import __version__

DEFAULT_GITHUB_REPO = "ceos-org/ceos-ard"
GITHUB_API_URL = "https://api.github.com"

# ordered from the lowest to the highest level
LEVELS = ["patch", "minor", "major"]

VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-draft)?$")
NEXT_LINK_PATTERN = re.compile(r'<([^>]+)>;\s*rel="next"')
TOP_LEVEL_KEY_PATTERN = re.compile(r"^[^\s#-]")

_RELEASE_CACHE = {}
_HISTORY_CACHE = {}


def parse_version(text):
    match = VERSION_PATTERN.match(str(text).strip())
    if not match:
        raise ValueError(f"Invalid version number '{text}', expected the format MAJOR.MINOR.PATCH")
    return tuple(int(part) for part in match.groups())


def format_version(version):
    return ".".join(str(part) for part in version)


def bump_version(version, level):
    major, minor, patch = version
    if level == "major":
        return (major + 1, 0, 0)
    elif level == "minor":
        return (major, minor + 1, 0)
    elif level == "patch":
        return (major, minor, patch + 1)
    raise ValueError(f"Invalid change level '{level}', expected one of {', '.join(LEVELS)}")


def highest_level(levels):
    levels = [level for level in levels if level in LEVELS]
    if not levels:
        return None
    return max(levels, key=LEVELS.index)


def get_github_token():
    return os.environ.get("GITHUB_TOKEN") or None


def _http_get(url, token=None, accept=None):
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
    """Get the published GitHub releases of the PFS, sorted from the oldest to the newest version."""
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


def parse_yaml(text):
    """Parse YAML without a schema (all scalars are strings)."""
    data = strictyaml.dirty_load(text, allow_flow_style=True).data
    return data if isinstance(data, dict) else {}


def _parse_top_level(text, key):
    # parsing only a top-level block is much faster than parsing the whole file
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(f"{key}:")), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if TOP_LEVEL_KEY_PATTERN.match(lines[i])), len(lines))
    try:
        return parse_yaml("\n".join(lines[start:end])).get(key)
    except Exception:
        try:
            return parse_yaml(text).get(key)
        except Exception:
            return None


def parse_changes(text):
    changes = _parse_top_level(text, "changes")
    return [c for c in changes if isinstance(c, dict)] if isinstance(changes, list) else []


def normalize_path(path):
    path = fix_path(path)
    while path.startswith("./"):
        path = path[2:]
    return path


def _add_refs(members, template, ids):
    if isinstance(ids, (str, dict)):
        ids = [ids]
    if not isinstance(ids, list):
        return
    for id in ids:
        if isinstance(id, dict):
            id = id.get("ref")
        if isinstance(id, str) and id:
            members.add(normalize_path(template.format(id=id)))


def _add_glossary_refs(members, data):
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "glossary":
                _add_refs(members, GLOSSARY_PATH, value)
            else:
                _add_glossary_refs(members, value)
    elif isinstance(data, list):
        for value in data:
            _add_glossary_refs(members, value)


def members_from_document(document, pfs):
    """Get the paths of the building blocks that are referenced by a (schema-less parsed) PFS document."""
    members = {f"pfs/{pfs}/document.yaml"}
    _add_refs(members, INTRODUCTION_PATH, document.get("introduction"))
    _add_refs(members, ANNEX_PATH, document.get("annexes"))
    blocks = document.get("requirements")
    if isinstance(blocks, list):
        for block in blocks:
            if isinstance(block, dict):
                _add_refs(members, REQUIREMENT_CATEGORY_PATH, block.get("category"))
                _add_refs(members, REQUIREMENT_PATH, block.get("requirements"))
    _add_glossary_refs(members, document)
    return members


def _change_key(change):
    return tuple(str(change.get(k) or "").strip() for k in ("date", "author", "level", "change", "reason"))


def _match_changes(previous, changes, first_seen, default):
    # match against the same change in the previous file version, then anywhere else (e.g. renamed files),
    # then an edited change in the previous file version (same date and author)
    keys = [_change_key(c) for c in changes]
    commits = [None] * len(keys)
    remaining = list(previous)

    def take(i, same):
        for j, (key, commit) in enumerate(remaining):
            if same(key, keys[i]):
                commits[i] = commit
                del remaining[j]
                return

    for i in range(len(keys)):
        take(i, lambda a, b: a == b)
    for i, key in enumerate(keys):
        if commits[i] is None and key in first_seen:
            commits[i] = first_seen[key]
    for i in range(len(keys)):
        if commits[i] is None:
            take(i, lambda a, b: a[:2] == b[:2])
    return [(key, commit if commit is not None else default) for key, commit in zip(keys, commits)]


class GitHistory:
    """
    Releases are always created from main, so a change is part of a release if the commit
    that merged it into main (the first commit in the first-parent history of HEAD that
    contains the change) is an ancestor of the release tag.
    """

    def __init__(self, input_dir):
        self.cwd = Path(input_dir).resolve()
        self.files = {}
        self.first_seen = {}
        self._ancestors = {}
        self._renames = {}
        try:
            shallow = self._git("rev-parse", "--is-shallow-repository").strip() == "true"
        except (ValueError, OSError) as e:
            raise ValueError(f"The document history requires a git checkout of the repository: {e}") from e
        if shallow:
            raise ValueError(
                "The document history requires the full git history, e.g. use `fetch-depth: 0` for actions/checkout"
            )
        self.prefix = self._git("rev-parse", "--show-prefix").strip()

        log = self._git(
            "-c",
            "core.quotePath=false",
            "log",
            "--first-parent",
            "--diff-merges=first-parent",
            "--reverse",
            "--no-renames",
            "--raw",
            "--no-abbrev",
            "--relative",
            "--format=%x00%H",
            "HEAD",
            "--",
            ".",
        )
        commits = []
        for chunk in log.split("\x00")[1:]:
            lines = chunk.strip().splitlines()
            files = []
            for line in lines[1:]:
                meta, _, path = line.partition("\t")
                meta = meta.split()
                if path.endswith(".yaml") and len(meta) >= 5:
                    files.append((path, meta[3], meta[4]))
            commits.append((lines[0].strip(), files))

        blobs = sorted({sha for _, files in commits for _, sha, status in files if not status.startswith("D")})
        parsed = {sha: parse_changes(text or "") for sha, text in read_objects(blobs, self.cwd).items()}

        for commit, files in commits:
            for path, sha, status in files:
                if status.startswith("D"):
                    self.files.pop(path, None)
                    continue
                matched = _match_changes(self.files.get(path, []), parsed.get(sha, []), self.first_seen, commit)
                self.files[path] = matched
                for key, first in matched:
                    self.first_seen.setdefault(key, first)

    @classmethod
    def load(cls, input_dir):
        key = Path(input_dir).resolve()
        if key not in _HISTORY_CACHE:
            _HISTORY_CACHE[key] = cls(key)
        return _HISTORY_CACHE[key]

    def _git(self, *args):
        return run_git(list(args), self.cwd)

    def merge_commits(self, filepath, changes):
        """Get the commits that merged the given changes of a file, None for changes that are not merged yet."""
        return [commit for _, commit in _match_changes(self.files.get(filepath, []), changes, self.first_seen, None)]

    def contains(self, tag, commit):
        if commit is None:
            return False
        if tag not in self._ancestors:
            try:
                self._ancestors[tag] = set(self._git("rev-list", f"{tag}^{{commit}}").split())
            except ValueError as e:
                raise ValueError(f"The release tag {tag} is not available, run `git fetch --tags`") from e
        return commit in self._ancestors[tag]

    def read_files(self, tag, paths):
        objects = read_objects([f"{tag}:{self.prefix}{path}" for path in paths], self.cwd)
        return {path: objects[f"{tag}:{self.prefix}{path}"] for path in paths}

    def renames(self, tag):
        if tag not in self._renames:
            output = self._git("diff", "-M", "--name-status", "--diff-filter=R", "--relative", tag, "HEAD")
            renames = {}
            for line in output.splitlines():
                parts = line.split("\t")
                if len(parts) == 3:
                    renames[parts[1]] = parts[2]
            self._renames[tag] = renames
        return self._renames[tag]

    def members(self, tag, pfs):
        """Get the building blocks that were part of the PFS in the release, with their current paths."""
        path = f"pfs/{pfs}/document.yaml"
        text = self.read_files(tag, [path])[path]
        if text is None:
            print(f"WARNING [{pfs}]: Can't determine the building blocks of release {tag}")
            return None
        members = members_from_document(parse_yaml(text), pfs)
        # glossary terms that are referenced by the building blocks
        for content in self.read_files(tag, sorted(members)).values():
            if content:
                _add_refs(members, GLOSSARY_PATH, _parse_top_level(content, "glossary"))
        renames = self.renames(tag)
        return {renames.get(member, member) for member in members}

    def read_file(self, tag, path):
        return self.read_files(tag, [path])[path]

    def head_versions(self, pfs):
        pattern = re.compile(rf"^{re.escape(pfs)}-v(\d+\.\d+\.\d+)$")
        tags = self._git("tag", "--points-at", "HEAD").split()
        return [match.group(1) for match in map(pattern.match, tags) if match]


def relative_filepath(filepath, input_dir):
    try:
        return fix_path(Path(filepath).relative_to(Path(input_dir).resolve()))
    except ValueError:
        return normalize_path(filepath)


def parse_date(value, where):
    try:
        return date.fromisoformat(str(value))
    except ValueError as e:
        raise ValueError(f"Invalid date '{value}' in the changes of {where}: {e}") from e


def make_entries(changes, block, history):
    if not isinstance(changes, list):
        return []
    changes = [change for change in changes if isinstance(change, dict)]
    commits = history.merge_commits(block["filepath"], changes)
    return [
        {
            "date": parse_date(change.get("date"), block["filepath"]),
            "level": change.get("level"),
            "change": (change.get("change") or "").rstrip(),
            "reason": (change.get("reason") or "").rstrip(),
            "author": (change.get("author") or "").rstrip(),
            "commit": commit,
            "block": block,
        }
        for change, commit in zip(changes, commits)
    ]


# the order of the building blocks in the document history
GROUP_DOCUMENT = 0
GROUP_SECTION = 1
GROUP_REQUIREMENT = 2
GROUP_GLOSSARY = 3
KIND_GROUPS = {
    "Document": GROUP_DOCUMENT,
    "PFS": GROUP_DOCUMENT,
    "Introduction": GROUP_SECTION,
    "Requirement category": GROUP_SECTION,
    "Annex": GROUP_SECTION,
    "Section": GROUP_SECTION,
    "Requirement": GROUP_REQUIREMENT,
    "Glossary term": GROUP_GLOSSARY,
}


def make_block(kind, title, filepath, anchor="", order=None):
    return {
        "kind": kind,
        "title": (title or "").strip(),
        "filepath": filepath,
        "anchor": anchor,
        "group": KIND_GROUPS.get(kind, GROUP_SECTION),
        # blocks without an order are listed after the ordered blocks of their group
        "order": order,
    }


def block_sort_key(block):
    order = block.get("order")
    return (block.get("group", GROUP_SECTION), order is None, order or 0, block.get("title", "").lower())


def collect_changes(data, input_dir, history, pfs=None):
    """Collect the changes of the PFS document and of all building blocks that are used by the PFS."""
    pfs = pfs or data.get("id")
    seen = set()
    entries = []
    counters = {}

    def add(container, block, ordered=True):
        if block["filepath"] in seen:
            return
        seen.add(block["filepath"])
        if ordered and block["order"] is None:
            block["order"] = counters.get(block["group"], 0)
            counters[block["group"]] = block["order"] + 1
        entries.extend(make_entries(container.get("changes"), block, history))

    def add_section(kind, section, prefix):
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

    add(data, make_block("Document", data.get("title"), f"pfs/{pfs}/document.yaml"))

    for section in data.get("introduction") or []:
        add_section("Introduction", section, "intro-")
    for block in data.get("requirements") or []:
        add_section("Requirement category", block.get("category") or {}, "")
    for section in data.get("annexes") or []:
        add_section("Annex", section, "annex-")

    for block in data.get("requirements") or []:
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

    # the glossary terms of all building blocks have been bubbled up to the top-level
    terms = [t for t in data.get("glossary") or [] if t.get("filepath")]
    terms.sort(key=lambda t: (t.get("term") or "").lower())
    for order, term in enumerate(terms):
        add(
            term,
            make_block("Glossary term", term.get("term"), relative_filepath(term["filepath"], input_dir), order=order),
        )

    _collect_nested(data, input_dir, add)

    return entries


def _collect_nested(data, input_dir, add):
    if isinstance(data, dict):
        if data.get("filepath") and data.get("changes"):
            kind, name = describe_kind(data)
            add(
                data, make_block(kind.capitalize(), name, relative_filepath(data["filepath"], input_dir)), ordered=False
            )
        for value in data.values():
            _collect_nested(value, input_dir, add)
    elif isinstance(data, list):
        for value in data:
            _collect_nested(value, input_dir, add)


def collect_former_members(releases, members_by_version, current_members, input_dir, history):
    """Collect the changes of building blocks that were part of a release, but are not part of the PFS anymore."""
    input_dir = Path(input_dir).resolve()
    # the newest release that contained the building block, to read deleted files from
    former = {}
    for release in releases:
        for filepath in members_by_version.get(release["version"]) or []:
            if filepath not in current_members:
                former[filepath] = release["tag"]

    entries = []
    for filepath, tag in sorted(former.items()):
        file = input_dir / filepath
        text = read_file(file) if file.is_file() else history.read_file(tag, filepath)
        if text is None:
            continue
        try:
            content = parse_yaml(text)
        except Exception as e:
            print(f"WARNING: Can't read the changes of the former building block {filepath}: {e}")
            continue
        kind, name = describe_kind(content)
        entries.extend(make_entries(content.get("changes"), make_block(kind.capitalize(), name, filepath), history))
    return entries


def merge_entries(entries):
    """Merge the entries into one row per building block, in the order of the building blocks in the document."""
    rows = {}
    for entry in entries:
        row = rows.setdefault(entry["block"]["filepath"], {"block": entry["block"], "changes": [], "level": None})
        row["changes"].append(entry)
    for row in rows.values():
        row["changes"].sort(key=lambda e: e["date"])
        row["level"] = highest_level(e["level"] for e in row["changes"])
    return sorted(rows.values(), key=lambda row: block_sort_key(row["block"]))


def collect_editors(entries):
    counts = {}
    for entry in entries:
        name = entry["author"]
        if name:
            counts[name] = counts.get(name, 0) + 1
    editors = [{"name": name, "count": count} for name, count in counts.items()]
    editors.sort(key=lambda e: (-e["count"], e["name"].lower()))
    return editors


def window_min_major(current):
    # list the history back to the previous major version
    return max(current[0] - 1, 0)


def build_changelog(data, releases, history, input_dir=".", pfs=None):
    """
    Build the document history for the given (resolved) PFS document.

    `history` assigns the changes to the releases and provides the building blocks of the releases, see `GitHistory`.
    """
    pfs = pfs or data.get("id")
    current = parse_version(data["version"])
    current_label = str(data["version"])

    result = {
        "versions": [],
        "first_release": False,
        "truncated": False,
        "oldest_version": None,
        "latest_release": None,
        "current": current_label,
    }
    if not any(r["tuple"] < current for r in releases):
        # no previous release exists on GitHub, don't generate the history
        result["first_release"] = current == (1, 0, 0)
        return result

    released = [r for r in releases if r["tuple"] <= current]
    latest = released[-1]
    result["latest_release"] = latest["version"]
    min_major = window_min_major(current)
    members_by_version = {r["version"]: history.members(r["tag"], pfs) for r in released if r["tuple"][0] >= min_major}

    entries = collect_changes(data, input_dir, history, pfs)
    current_members = {e["block"]["filepath"] for e in entries}
    entries += collect_former_members(released, members_by_version, current_members, input_dir, history)

    buckets = [_make_bucket(r["version"], r["tuple"], r["date"], r["tag"], r["url"]) for r in released]
    # changes that are not part of any release, also if the current version has been released already
    unreleased = _make_bucket(current_label, current)
    for entry in entries:
        bucket = next((b for b in buckets if history.contains(b["tag"], entry["commit"])), unreleased)
        members = members_by_version.get(bucket["version"]) if bucket["released"] else current_members
        if members is not None and entry["block"]["filepath"] not in members:
            # the building block was not part of the PFS in this version
            continue
        bucket["entries"].append(entry)
    if latest["tuple"] != current or unreleased["entries"]:
        buckets.append(unreleased)

    result["truncated"] = any(b["tuple"][0] < min_major for b in buckets)
    buckets = [b for b in buckets if b["tuple"][0] >= min_major]
    buckets.sort(key=lambda b: (b["tuple"], not b["released"]), reverse=True)

    for bucket in buckets:
        bucket["rows"] = merge_entries(bucket["entries"])
        bucket["editors"] = collect_editors(bucket["entries"])
        bucket["level"] = highest_level(e["level"] for e in bucket["entries"])
        bucket["proposed_version"] = None
        bucket["proposed_level"] = None

    if unreleased.get("level"):
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


def _make_bucket(version, version_tuple, released_date=None, tag=None, url=None):
    return {
        "version": version,
        "tuple": version_tuple,
        "date": released_date,
        "released": tag is not None,
        "tag": tag,
        "url": url,
        "entries": [],
    }


def compile_changelog(data, input_dir, pfs, repo=DEFAULT_GITHUB_REPO):
    history = GitHistory.load(input_dir)
    current = parse_version(data["version"])
    for version in history.head_versions(pfs):
        if parse_version(version) != current:
            raise ValueError(
                f"The release tag {pfs}-v{version} doesn't match the version {data['version']} of the PFS document"
            )
    releases = fetch_releases(repo, pfs)
    return build_changelog(data, releases, history, input_dir, pfs)
