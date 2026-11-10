"""Tests that content can't run code or reach files outside of the content folder."""

import base64
import http.server
import os
import re
import shutil
import threading
from pathlib import Path

import pytest
import strictyaml

from ceos_ard_cli.generate import ORIGIN, local_file, run_pandoc, run_playwright
from ceos_ard_cli.links import resolve_titles
from ceos_ard_cli.schema import REFERENCE_PATH
from ceos_ard_cli.strictyaml.id_reference import IdReference
from ceos_ard_cli.utils.files import check_no_symlinks, content_file
from ceos_ard_cli.validate import validate

needs_pandoc = pytest.mark.skipif(
    not (shutil.which("pandoc") and shutil.which("pandoc-crossref")), reason="needs pandoc and pandoc-crossref"
)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestPaths:
    def test_content_file(self, tmp_path):
        assert content_file(tmp_path, "references/a.bib") == (tmp_path / "references" / "a.bib").resolve()
        for path in ["../a.bib", "references/../../a.bib", str(tmp_path.parent / "a.bib")]:
            with pytest.raises(ValueError):
                content_file(tmp_path, path)

    # The id is put into ./references/{id}.bib, so it takes two levels to get out
    @pytest.mark.parametrize("id", ["../../outside", "a/../../../outside"])
    def test_ids_must_stay_inside(self, tmp_path, id):
        write(tmp_path.parent / "outside.bib", "@misc{outside, title={Secret}}")
        with pytest.raises(strictyaml.YAMLValidationError, match="inside of the content folder"):
            strictyaml.load(f"- {id}", strictyaml.Seq(IdReference(REFERENCE_PATH, tmp_path)))

    def test_title_references_must_stay_inside(self, tmp_path):
        write(tmp_path.parent / "outside.yaml", "title: Secret\n")
        data = {"description": f"see @title:/{(tmp_path.parent / 'outside').as_posix().lstrip('/')}"}
        errors = resolve_titles(data, tmp_path)
        assert len(errors) == 1
        assert "Secret" not in data["description"]

    def test_symlinks_are_refused(self, tmp_path):
        write(tmp_path / "outside.txt", "secret")
        (tmp_path / "content" / "assets").mkdir(parents=True)
        try:
            os.symlink(tmp_path / "outside.txt", tmp_path / "content" / "assets" / "logo.png")
        except OSError:
            pytest.skip("can't create symlinks")
        with pytest.raises(ValueError, match="logo.png"):
            check_no_symlinks(tmp_path / "content")

    def test_validation_stops_at_symlinks(self, tmp_path, capsys):
        # A linked template would otherwise be read from outside of the input folder
        write(tmp_path / "outside.md", "~{ secret }~")
        (tmp_path / "content" / "templates").mkdir(parents=True)
        try:
            os.symlink(tmp_path / "outside.md", tmp_path / "content" / "templates" / "template.md")
        except OSError:
            pytest.skip("can't create symlinks")

        validate(tmp_path / "content")

        output = capsys.readouterr().out
        assert "Symbolic links are not supported" in output
        assert "Validating PFS template" not in output

    @pytest.mark.parametrize("link", ["assets", "governance/logo.png"])
    def test_symlinks_anywhere_in_the_input_folder_are_refused(self, tmp_path, link):
        # A content folder that is a link itself, or a link outside of the content folders that images can point to
        write(tmp_path / "outside" / "logo.png", "secret")
        (tmp_path / "content" / "governance").mkdir(parents=True)
        target = tmp_path / "outside" / ("logo.png" if link.endswith(".png") else "")
        try:
            os.symlink(target, tmp_path / "content" / link, target_is_directory=target.is_dir())
        except OSError:
            pytest.skip("can't create symlinks")
        with pytest.raises(ValueError, match=Path(link).name):
            check_no_symlinks(tmp_path / "content")

    def test_no_symlinks(self, tmp_path):
        write(tmp_path / "assets" / "logo.png", "")
        check_no_symlinks(tmp_path)


@pytest.fixture(scope="module")
def chromium():
    from playwright.sync_api import Error, sync_playwright

    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Error:
        pytest.skip("needs Chromium, see `pixi run install-browser`")


# A 1x1 pixel PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=="
)


def image_sizes(pdf):
    # Chromium also draws an image that it can't load, as a broken-image icon, so the size tells them apart
    images = re.findall(rb"<<(?:(?!>>).)*?/Subtype\s*/Image(?:(?!>>).)*?>>", pdf.read_bytes(), re.S)
    return {
        tuple(int(re.search(rb"/" + key + rb"\s+(\d+)", image).group(1)) for key in (b"Width", b"Height"))
        for image in images
    }


class TestChromium:
    # A # would start a fragment and a % an escape if the file name wasn't encoded in the URL
    @pytest.mark.parametrize("name", ["doc", "report#draft 100%"])
    def test_prints_pdfs_with_the_files_of_the_output_folder(self, tmp_path, chromium, name):
        out = tmp_path / "out"
        (out / "assets").mkdir(parents=True)
        (out / "assets" / "logo.png").write_bytes(PNG)
        write(out / f"{name}.html", '<img src="assets/logo.png"><img src="https://example.com/remote.png">')

        run_playwright(out / name, tmp_path)

        assert (1, 1) in image_sizes(out / f"{name}.pdf")

    # Self-contained HTML embeds images as data: URLs, which Chromium loads without a request to the route
    def test_prints_pdfs_with_embedded_images(self, tmp_path, chromium):
        data_url = "data:image/png;base64," + base64.b64encode(PNG).decode()
        write(tmp_path / "doc.html", f'<img src="{data_url}">')

        run_playwright(tmp_path / "doc", tmp_path)

        assert image_sizes(tmp_path / "doc.pdf") == {(1, 1)}

    def test_runs_no_scripts(self, tmp_path, chromium):
        (tmp_path / "assets").mkdir()
        (tmp_path / "assets" / "logo.png").write_bytes(PNG)
        # The script would replace the text with the image
        write(
            tmp_path / "doc.html",
            "<p>Text</p><script>document.body.innerHTML = '<img src=\"assets/logo.png\">'</script>",
        )

        run_playwright(tmp_path / "doc", tmp_path)

        assert (1, 1) not in image_sizes(tmp_path / "doc.pdf")

    def test_loads_nothing_from_outside_of_the_output_folder(self, tmp_path, chromium, monkeypatch):
        from playwright.sync_api import Route

        # What the route does with each request; Chromium itself already blocks some of them (e.g. to 127.0.0.1)
        handled = []
        for action in ("abort", "continue_", "fallback", "fulfill"):
            original = getattr(Route, action)

            def record(route, *args, _action=action, _original=original, **kwargs):
                handled.append((_action, route.request.url))
                return _original(route, *args, **kwargs)

            monkeypatch.setattr(Route, action, record)
        requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.end_headers()
                self.wfile.write(PNG)

            def log_message(self, *args):
                pass

        (tmp_path / "outside.png").write_bytes(PNG)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{server.server_port}"
            write(
                tmp_path / "out" / "doc.html",
                f'<link rel="stylesheet" href="{url}/style.css"><img src="{url}/image.png">'
                f'<img src="{(tmp_path / "outside.png").as_uri()}"><img src="../outside.png">'
                '<img src="https://example.com/image.png">',
            )
            run_playwright(tmp_path / "out" / "doc", tmp_path)
        finally:
            server.shutdown()
            server.server_close()

        assert requests == []
        assert (1, 1) not in image_sizes(tmp_path / "out" / "doc.pdf")
        outside = [(action, url) for action, url in handled if url != f"{ORIGIN}/doc.html"]
        assert ("abort", "https://example.com/image.png") in outside
        assert all(action == "abort" for action, _ in outside)

    def test_serves_files_of_the_output_folder(self, tmp_path):
        write(tmp_path / "assets" / "logo.png", "")
        assert (
            local_file(tmp_path.resolve(), f"{ORIGIN}/assets/logo.png") == (tmp_path / "assets" / "logo.png").resolve()
        )

    @pytest.mark.parametrize(
        "url",
        [
            f"{ORIGIN}/../outside.txt",
            f"{ORIGIN}/%2e%2e/outside.txt",
            f"{ORIGIN}/out/missing.txt",
            "file:///etc/passwd",
            "https://example.com/outside.txt",
            f"{ORIGIN}.example.com/outside.txt",
        ],
    )
    def test_refuses_everything_else(self, tmp_path, url):
        write(tmp_path / "outside.txt", "secret")
        assert local_file((tmp_path / "out").resolve(), url) is None


@needs_pandoc
class TestPandoc:
    def build(self, tmp_path, markdown):
        write(tmp_path / "templates" / "template.html", "$body$")
        write(tmp_path / "out" / "doc.md", markdown)
        write(tmp_path / "out" / "doc.bib", "")
        write(tmp_path / "assets" / "logo.png", "")
        write(tmp_path / "outside.png", "secret")
        run_pandoc(tmp_path / "out" / "doc", "html", tmp_path, self_contained=False)
        return (tmp_path / "out" / "doc.html").read_text(encoding="utf-8")

    def test_ignores_lua_filters_of_the_input_directory(self, tmp_path):
        write(tmp_path / "templates" / "pagebreak.lua", "error('content code ran')")
        write(tmp_path / "templates" / "toc.lua", "error('content code ran')")
        assert "Title" in self.build(tmp_path, "# Title\n")
