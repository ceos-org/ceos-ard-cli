"""Tests for the document history (changelog) generation."""

from datetime import date

import pytest

from ceos_ard_cli import changelog
from ceos_ard_cli.changelog import (
    build_changelog,
    bump_version,
    collect_changes,
    fetch_releases,
    highest_level,
    members_from_document,
    parse_version,
)


def change(day, level, text="Changed something", reason="Because", author="Jane Doe"):
    return {"date": day, "level": level, "change": text, "reason": reason, "author": author}


def release(version, day, pfs="ST"):
    return {
        "version": version,
        "tuple": parse_version(version),
        "date": date.fromisoformat(day),
        "tag": f"{pfs}-v{version}",
        "url": f"https://github.com/ceos-org/ceos-ard/releases/tag/{pfs}-v{version}",
    }


def requirement(input_dir, rel_path, req_id, title, changes=(), uid=None):
    return {
        "id": req_id,
        "uid": uid or f"general-metadata-{req_id}",
        "title": title,
        "filepath": str(input_dir / f"requirements/{rel_path}.yaml"),
        "requirements": {},
        "changes": list(changes),
    }


def pfs_document(input_dir, version, changes=(), requirements=(), glossary=(), annexes=()):
    return {
        "id": "ST",
        "title": "Surface Temperature",
        "version": version,
        "changes": list(changes),
        "requirements": [
            {
                "category": {
                    "id": "general-metadata",
                    "title": "General Metadata",
                    "filepath": str(input_dir / "sections/requirement-categories/general-metadata.yaml"),
                    "changes": [],
                },
                "requirements": list(requirements),
            }
        ],
        "introduction": [],
        "annexes": list(annexes),
        "glossary": list(glossary),
    }


def versions(result):
    return [v["version"] for v in result["versions"]]


def entries(result, version):
    for v in result["versions"]:
        if v["version"] == version:
            return v["entries"]
    raise KeyError(version)


class TestVersions:
    def test_parse_version(self):
        assert parse_version("6.0.0") == (6, 0, 0)
        assert parse_version("6.0.0-draft") == (6, 0, 0)
        assert parse_version(" 10.2.13 ") == (10, 2, 13)

    def test_parse_invalid_version(self):
        with pytest.raises(ValueError):
            parse_version("v6.0.0")
        with pytest.raises(ValueError):
            parse_version("6.0")

    def test_bump_version(self):
        assert bump_version((5, 0, 1), "major") == (6, 0, 0)
        assert bump_version((5, 0, 1), "minor") == (5, 1, 0)
        assert bump_version((5, 0, 1), "patch") == (5, 0, 2)
        with pytest.raises(ValueError):
            bump_version((5, 0, 1), "huge")

    def test_highest_level(self):
        assert highest_level(["patch", "major", "minor"]) == "major"
        assert highest_level(["patch", "minor"]) == "minor"
        assert highest_level([]) is None


class TestFetchReleases:
    def test_filters_and_sorts_releases(self, monkeypatch):
        pages = {
            "https://api.github.com/repos/org/repo/releases?per_page=100": (
                [
                    {"tag_name": "ST-v5.0.1", "published_at": "2026-05-27T16:02:19Z", "html_url": "u1"},
                    {"tag_name": "SR-v5.0.2", "published_at": "2026-05-27T16:01:24Z", "html_url": "u2"},
                    {"tag_name": "ST-v6.0.0", "published_at": None, "draft": True, "html_url": "u3"},
                ],
                {"Link": '<https://api.github.com/page2>; rel="next"'},
            ),
            "https://api.github.com/page2": (
                [{"tag_name": "ST-v4.0.0", "published_at": "2025-01-01T00:00:00Z", "html_url": "u4"}],
                {},
            ),
        }

        def fake_get(url, token=None, accept=None):
            import json

            body, headers = pages[url]
            return json.dumps(body), headers

        monkeypatch.setattr(changelog, "_http_get", fake_get)
        monkeypatch.setattr(changelog, "_RELEASE_CACHE", {})

        releases = fetch_releases("org/repo", "ST")
        assert [r["version"] for r in releases] == ["4.0.0", "5.0.1"]
        assert releases[1]["date"] == date(2026, 5, 27)
        assert releases[1]["tag"] == "ST-v5.0.1"
        assert releases[1]["url"] == "u1"


class TestMembers:
    def test_members_from_document(self):
        document = {
            "introduction": ["what-are-ceos-ard-products"],
            "annexes": "",
            "glossary": ["st"],
            "requirements": [
                {
                    "category": "general-metadata",
                    "requirements": ["metadata/time-st", {"ref": "metadata/crs-ar", "replace": {}}],
                },
                {"category": {"ref": "per-pixel-metadata"}, "requirements": ["per-pixel/nodata-st"]},
            ],
        }
        assert members_from_document(document, "ST") == {
            "pfs/ST/document.yaml",
            "sections/introduction/what-are-ceos-ard-products.yaml",
            "glossary/st.yaml",
            "sections/requirement-categories/general-metadata.yaml",
            "sections/requirement-categories/per-pixel-metadata.yaml",
            "requirements/metadata/time-st.yaml",
            "requirements/metadata/crs-ar.yaml",
            "requirements/per-pixel/nodata-st.yaml",
        }


class TestCollectChanges:
    def test_collects_and_attributes_entries(self, tmp_path):
        req = requirement(tmp_path, "metadata/time-st", "time-st", "Time", [change("2026-08-27", "minor")])
        term = {
            "term": "ST",
            "filepath": str(tmp_path / "glossary/st.yaml"),
            "changes": [change("2026-08-01", "patch")],
        }
        annex = {
            "id": "st-metadata-examples",
            "title": "Examples",
            "filepath": str(tmp_path / "sections/annexes/st-metadata-examples.yaml"),
            "changes": [change("2026-08-14", "patch")],
        }
        data = pfs_document(
            tmp_path,
            "6.0.0",
            changes=[change("2026-08-14", "major")],
            requirements=[req],
            glossary=[term],
            annexes=[annex],
        )
        result = collect_changes(data, tmp_path)
        by_path = {e["block"]["filepath"]: e for e in result}
        assert set(by_path) == {
            "pfs/ST/document.yaml",
            "requirements/metadata/time-st.yaml",
            "glossary/st.yaml",
            "sections/annexes/st-metadata-examples.yaml",
        }
        doc = by_path["pfs/ST/document.yaml"]
        assert doc["block"]["kind"] == "Document"
        assert doc["date"] == date(2026, 8, 14)
        assert doc["level"] == "major"
        assert by_path["requirements/metadata/time-st.yaml"]["block"]["anchor"] == "#sec:general-metadata-time-st"
        assert by_path["requirements/metadata/time-st.yaml"]["block"]["direct"] is True
        assert by_path["glossary/st.yaml"]["block"]["direct"] is False
        assert (
            by_path["sections/annexes/st-metadata-examples.yaml"]["block"]["anchor"]
            == "#sec:annex-st-metadata-examples"
        )

    def test_invalid_date(self, tmp_path):
        data = pfs_document(tmp_path, "6.0.0", changes=[change("2026-13-01", "major")])
        with pytest.raises(ValueError, match="2026-13-01"):
            collect_changes(data, tmp_path)


class TestBuildChangelog:
    def test_no_previous_release_first_version(self, tmp_path):
        data = pfs_document(tmp_path, "1.0.0", changes=[change("2026-08-14", "major")])
        result = build_changelog(data, [], {}, tmp_path)
        assert result["versions"] == []
        assert result["first_release"] is True

        # the release of the current version itself is not a previous release
        result = build_changelog(data, [release("1.0.0", "2026-09-01")], {}, tmp_path)
        assert result["versions"] == []
        assert result["first_release"] is True

    def test_no_previous_release_higher_version(self, tmp_path):
        data = pfs_document(tmp_path, "1.1.0", changes=[change("2026-08-14", "minor")])
        result = build_changelog(data, [], {}, tmp_path)
        assert result["versions"] == []
        assert result["first_release"] is False

    def test_buckets_by_release_date(self, tmp_path, capsys):
        req = requirement(tmp_path, "per-pixel/surface-st", "surface-st", "Surface", [change("2026-07-31", "major")])
        data = pfs_document(
            tmp_path,
            "6.0.0-draft",
            changes=[change("2026-08-14", "major", "Big update"), change("2026-03-26", "patch", "Migration")],
            requirements=[req],
        )
        result = build_changelog(data, [release("5.0.1", "2026-05-27")], {}, tmp_path)

        assert versions(result) == ["6.0.0-draft", "5.0.1"]
        assert result["latest_release"] == "5.0.1"
        assert result["oldest_version"] == "5.0.1"
        assert result["truncated"] is False
        assert result["first_release"] is False

        draft = result["versions"][0]
        assert draft["released"] is False
        assert draft["date"] is None
        assert draft["level"] == "major"
        assert draft["breaking"] is True
        assert draft["proposed_version"] == "6.0.0"
        assert draft["proposed_level"] == "major"
        # newest first, the document entry comes first on the same date
        assert [(str(e["date"]), e["block"]["kind"]) for e in draft["entries"]] == [
            ("2026-08-14", "Document"),
            ("2026-07-31", "Requirement"),
        ]

        old = result["versions"][1]
        assert old["released"] is True
        assert old["date"] == date(2026, 5, 27)
        assert old["level"] == "patch"
        assert old["breaking"] is False
        assert old["proposed_version"] is None
        assert [e["change"] for e in old["entries"]] == ["Migration"]

        assert "WARNING" not in capsys.readouterr().out

    def test_proposed_version_mismatch_warning(self, tmp_path, capsys):
        data = pfs_document(tmp_path, "6.0.0", changes=[change("2026-08-14", "patch")])
        result = build_changelog(data, [release("5.0.1", "2026-05-27")], {}, tmp_path)
        draft = result["versions"][0]
        assert draft["proposed_version"] == "5.0.2"
        assert draft["proposed_level"] == "patch"
        out = capsys.readouterr().out
        assert "WARNING [ST]" in out
        assert "declares version 6.0.0" in out
        assert "suggest version 5.0.2 (patch)" in out

    def test_no_unreleased_changes(self, tmp_path):
        data = pfs_document(tmp_path, "6.0.0", changes=[change("2026-03-26", "patch")])
        result = build_changelog(data, [release("5.0.1", "2026-05-27")], {}, tmp_path)
        draft = result["versions"][0]
        assert draft["entries"] == []
        assert draft["level"] is None
        assert draft["proposed_version"] is None

    def test_window_one_major_version_back(self, tmp_path):
        data = pfs_document(
            tmp_path,
            "6.0.0",
            changes=[change("2024-01-01", "major"), change("2025-01-01", "major"), change("2026-08-01", "major")],
        )
        releases = [
            release("3.0.0", "2024-02-01"),
            release("4.0.0", "2025-02-01"),
            release("5.0.1", "2026-05-27"),
        ]
        result = build_changelog(data, releases, {}, tmp_path)
        # 6.x lists the changes back to 5.0.0 only
        assert versions(result) == ["6.0.0", "5.0.1"]
        assert result["truncated"] is True
        assert result["oldest_version"] == "5.0.1"
        assert len(entries(result, "6.0.0")) == 1
        assert entries(result, "5.0.1") == []

    def test_membership_filter(self, tmp_path):
        # the requirement was changed before the 5.0.1 release, but only added to the PFS afterwards
        req = requirement(tmp_path, "metadata/crs-ar", "crs-ar", "CRS", [change("2026-04-13", "minor")])
        # glossary terms can't be checked, they are always kept
        term = {
            "term": "ST",
            "filepath": str(tmp_path / "glossary/st.yaml"),
            "changes": [change("2026-04-01", "patch")],
        }
        data = pfs_document(
            tmp_path, "6.0.0", changes=[change("2026-03-26", "patch")], requirements=[req], glossary=[term]
        )
        members = {"5.0.1": {"pfs/ST/document.yaml", "requirements/metadata/time-st.yaml"}}
        result = build_changelog(data, [release("5.0.1", "2026-05-27")], members, tmp_path)
        old = entries(result, "5.0.1")
        assert {e["block"]["filepath"] for e in old} == {"pfs/ST/document.yaml", "glossary/st.yaml"}

    def test_membership_without_filter(self, tmp_path):
        req = requirement(tmp_path, "metadata/crs-ar", "crs-ar", "CRS", [change("2026-04-13", "minor")])
        data = pfs_document(tmp_path, "6.0.0", requirements=[req])
        # None means the membership could not be determined
        result = build_changelog(data, [release("5.0.1", "2026-05-27")], {"5.0.1": None}, tmp_path)
        assert len(entries(result, "5.0.1")) == 1

    def test_former_member(self, tmp_path):
        # a requirement that was part of 5.0.1 but has been removed since
        former = tmp_path / "requirements/per-pixel/snow-ice-sr.yaml"
        former.parent.mkdir(parents=True)
        former.write_text(
            "id: snow-ice-sr\n"
            "title: Snow/Ice\n"
            "requirements:\n"
            "  threshold:\n"
            "    description: Test\n"
            "changes:\n"
            "  - date: 2026-04-01\n"
            "    author: Jane Doe\n"
            "    level: minor\n"
            "    change: Old change\n"
            "    reason: Test\n"
            "  - date: 2026-08-01\n"
            "    author: Jane Doe\n"
            "    level: major\n"
            "    change: Change for another PFS\n"
            "    reason: Test\n",
            encoding="utf-8",
        )
        data = pfs_document(tmp_path, "6.0.0", changes=[change("2026-08-14", "major")])
        members = {"5.0.1": {"pfs/ST/document.yaml", "requirements/per-pixel/snow-ice-sr.yaml"}}
        result = build_changelog(data, [release("5.0.1", "2026-05-27")], members, tmp_path)

        old = entries(result, "5.0.1")
        assert [(e["change"], e["block"]["kind"], e["block"]["title"]) for e in old] == [
            ("Old change", "Requirement", "Snow/Ice")
        ]
        # the newer change is not part of the current PFS anymore
        assert [e["change"] for e in entries(result, "6.0.0")] != ["Change for another PFS"]
        assert all(
            e["block"]["filepath"] != "requirements/per-pixel/snow-ice-sr.yaml" for e in entries(result, "6.0.0")
        )

    def test_deleted_former_member_is_skipped(self, tmp_path):
        data = pfs_document(tmp_path, "6.0.0", changes=[change("2026-08-14", "major")])
        members = {"5.0.1": {"pfs/ST/document.yaml", "requirements/gone.yaml"}}
        result = build_changelog(data, [release("5.0.1", "2026-05-27")], members, tmp_path)
        assert entries(result, "5.0.1") == []

    def test_change_dated_after_released_current_version(self, tmp_path, capsys):
        data = pfs_document(tmp_path, "6.0.0", changes=[change("2026-09-10", "patch")])
        releases = [release("5.0.1", "2026-05-27"), release("6.0.0", "2026-09-01")]
        result = build_changelog(data, releases, {}, tmp_path)
        assert versions(result) == ["6.0.0", "5.0.1"]
        current = result["versions"][0]
        assert current["released"] is True
        assert current["date"] == date(2026, 9, 1)
        assert len(current["entries"]) == 1
        assert current["proposed_version"] is None
        assert "is dated 2026-09-10" in capsys.readouterr().out

    def test_releases_newer_than_current_are_ignored(self, tmp_path):
        data = pfs_document(tmp_path, "6.0.0", changes=[change("2026-08-14", "major")])
        releases = [release("5.0.1", "2026-05-27"), release("7.0.0", "2027-01-01")]
        result = build_changelog(data, releases, {}, tmp_path)
        assert versions(result) == ["6.0.0", "5.0.1"]


class TestRows:
    def test_merges_and_orders_rows(self, tmp_path):
        req_a = requirement(tmp_path, "metadata/time-st", "time-st", "Time", [change("2026-08-27", "minor", "Second")])
        req_b = requirement(
            tmp_path,
            "per-pixel/cloud-st",
            "cloud-st",
            "Cloud",
            [change("2026-08-27", "major", "Newer"), change("2026-07-31", "minor", "Older")],
        )
        term = {
            "term": "TIR",
            "filepath": str(tmp_path / "glossary/tir.yaml"),
            "changes": [change("2026-08-01", "patch")],
        }
        term2 = {
            "term": "LST",
            "filepath": str(tmp_path / "glossary/lst.yaml"),
            "changes": [change("2026-08-01", "patch")],
        }
        annex = {
            "id": "examples",
            "title": "Examples",
            "filepath": str(tmp_path / "sections/annexes/examples.yaml"),
            "changes": [change("2026-08-14", "patch")],
        }
        intro = {
            "id": "what",
            "title": "What",
            "filepath": str(tmp_path / "sections/introduction/what.yaml"),
            "changes": [change("2026-08-14", "patch")],
        }
        data = pfs_document(
            tmp_path,
            "6.0.0",
            changes=[change("2026-08-14", "major")],
            requirements=[req_a, req_b],
            glossary=[term, term2],
            annexes=[annex],
        )
        data["introduction"] = [intro]
        data["requirements"][0]["category"]["changes"] = [change("2026-08-14", "patch")]

        result = build_changelog(data, [release("5.0.1", "2026-05-27")], {}, tmp_path)
        rows = result["versions"][0]["rows"]
        assert [(r["block"]["kind"], r["block"]["title"]) for r in rows] == [
            ("Document", "Surface Temperature"),
            ("Introduction", "What"),
            ("Requirement category", "General Metadata"),
            ("Annex", "Examples"),
            ("Requirement", "Time"),
            ("Requirement", "Cloud"),
            ("Glossary term", "LST"),
            ("Glossary term", "TIR"),
        ]
        cloud = rows[5]
        # oldest first, highest level
        assert [e["change"] for e in cloud["changes"]] == ["Older", "Newer"]
        assert cloud["level"] == "major"
        assert rows[4]["level"] == "minor"

    def test_former_members_are_listed_last(self, tmp_path):
        former = tmp_path / "requirements/per-pixel/aaa.yaml"
        former.parent.mkdir(parents=True)
        former.write_text(
            "id: aaa\ntitle: AAA\nrequirements:\n  threshold:\n    description: Test\nchanges:\n"
            "  - date: 2026-04-01\n    author: Jane Doe\n    level: minor\n    change: Old change\n    reason: Test\n",
            encoding="utf-8",
        )
        req = requirement(tmp_path, "metadata/zzz", "zzz", "ZZZ", [change("2026-04-02", "minor")])
        data = pfs_document(tmp_path, "6.0.0", changes=[change("2026-03-26", "patch")], requirements=[req])
        members = {
            "5.0.1": {"pfs/ST/document.yaml", "requirements/per-pixel/aaa.yaml", "requirements/metadata/zzz.yaml"}
        }
        result = build_changelog(data, [release("5.0.1", "2026-05-27")], members, tmp_path)
        rows = entries(result, "5.0.1")  # entries still available
        assert len(rows) == 3
        titles = [r["block"]["title"] for r in result["versions"][1]["rows"]]
        assert titles == ["Surface Temperature", "ZZZ", "AAA"]


class TestEditors:
    def test_editors_sorted_by_count(self, tmp_path):
        req = requirement(
            tmp_path,
            "metadata/time-st",
            "time-st",
            "Time",
            [change("2026-08-27", "minor", author="Bob"), change("2026-08-28", "minor", author="Alice")],
        )
        data = pfs_document(
            tmp_path,
            "6.0.0",
            changes=[change("2026-08-14", "major", author="Bob"), change("2026-03-26", "patch", author="Carol")],
            requirements=[req],
        )
        result = build_changelog(data, [release("5.0.1", "2026-05-27")], {}, tmp_path)
        assert result["versions"][0]["editors"] == [{"name": "Bob", "count": 2}, {"name": "Alice", "count": 1}]
        assert result["versions"][1]["editors"] == [{"name": "Carol", "count": 1}]
