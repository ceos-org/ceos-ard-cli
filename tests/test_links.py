"""Tests for the @title: soft references."""

from ceos_ard_cli.links import resolve_titles


def write_yaml(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestResolveTitles:
    def test_resolves_titles(self, tmp_path):
        write_yaml(
            tmp_path / "sections" / "annexes" / "topo.yaml",
            "title: Topographic phase removal\ndescription: Test\n",
        )
        write_yaml(tmp_path / "glossary" / "dem.yaml", "term: DEM\ndescription: Test\n")
        data = {
            "description": 'see annex "@title:sections/annexes/topo" in the applicable PFS',
            "notes": ["uses a @title:glossary/dem."],
        }
        errors = resolve_titles(data, tmp_path)
        assert errors == []
        assert data["description"] == 'see annex "Topographic phase removal" in the applicable PFS'
        # the full stop at the end is not part of the reference
        assert data["notes"] == ["uses a DEM."]

    def test_missing_file_errors(self, tmp_path):
        data = {"description": "see @title:sections/annexes/does-not-exist"}
        errors = resolve_titles(data, tmp_path)
        assert len(errors) == 1
        assert "does-not-exist" in errors[0]
        # the reference is kept as-is
        assert data["description"] == "see @title:sections/annexes/does-not-exist"

    def test_missing_title_errors(self, tmp_path):
        write_yaml(tmp_path / "sections" / "no-title.yaml", "description: Test\n")
        data = {"description": "see @title:sections/no-title"}
        errors = resolve_titles(data, tmp_path)
        assert len(errors) == 1
        assert "no title" in errors[0]
