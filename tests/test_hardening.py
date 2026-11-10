"""Tests that content can't run code or reach files outside of the content folder."""

import base64
import http.server
import re
import shutil
import threading

import pytest

from ceos_ard_cli.generate import ORIGIN, local_file, run_pandoc, run_playwright

needs_pandoc = pytest.mark.skipif(
    not (shutil.which("pandoc") and shutil.which("pandoc-crossref")), reason="needs pandoc and pandoc-crossref"
)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
