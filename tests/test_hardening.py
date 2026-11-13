"""Tests that content can't run code or reach files outside of the content folder."""

import base64
import http.server
import importlib.util
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

import pytest
import strictyaml

from ceos_ard_cli.generate import ORIGIN, local_file, run_pandoc, run_playwright
from ceos_ard_cli.links import resolve_titles
from ceos_ard_cli.schema import REFERENCE_PATH
from ceos_ard_cli.strictyaml.id_reference import IdReference
from ceos_ard_cli.utils import files
from ceos_ard_cli.utils.files import check_no_symlinks, content_file
from ceos_ard_cli.validate import check_content, validate

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
        with pytest.raises(strictyaml.YAMLValidationError, match="outside of the content folder"):
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

    @pytest.mark.parametrize(
        "link",
        [
            # a content folder that is a link itself, links outside and deep inside of the content folders
            "assets",
            "link.png",
            "governance/logo.png",
            "sections/document/draft.md",
            # only the top level is skipped: images can point to these
            "assets/.hidden/logo.png",
            "assets/node_modules/logo.png",
        ],
    )
    def test_symlinks_anywhere_in_the_input_folder_are_refused(self, tmp_path, link):
        write(tmp_path / "outside" / "logo.png", "secret")
        is_folder = "." not in Path(link).name
        target = tmp_path / "outside" / ("" if is_folder else "logo.png")
        (tmp_path / "content" / link).parent.mkdir(parents=True)
        try:
            os.symlink(target, tmp_path / "content" / link, target_is_directory=is_folder)
        except OSError:
            pytest.skip("can't create symlinks")
        with pytest.raises(ValueError, match=Path(link).name):
            check_no_symlinks(tmp_path / "content")

    @pytest.mark.parametrize("link", [".venv/bin/python", ".pixi/envs/default/bin/python", "node_modules/.bin/tool"])
    def test_symlinks_in_environments_are_ignored(self, tmp_path, link):
        # Environments are full of links, and nothing is read from them
        write(tmp_path / "outside", "")
        (tmp_path / "content" / link).parent.mkdir(parents=True)
        try:
            os.symlink(tmp_path / "outside", tmp_path / "content" / link)
        except OSError:
            pytest.skip("can't create symlinks")
        check_no_symlinks(tmp_path / "content")

    @pytest.mark.skipif(os.name != "nt", reason="junctions only exist on Windows")
    def test_junctions_are_refused(self, tmp_path, monkeypatch):
        # Python 3.11 has no os.path.isjunction
        monkeypatch.delattr(os.path, "isjunction", raising=False)
        (tmp_path / "outside").mkdir()
        (tmp_path / "content").mkdir()
        link, target = tmp_path / "content" / "assets", tmp_path / "outside"
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
        # A copy of the module that is loaded as on Python 3.11
        spec = importlib.util.spec_from_file_location("files_without_isjunction", files.__file__)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with pytest.raises(ValueError, match="assets"):
            module.check_no_symlinks(tmp_path / "content")

    def test_no_symlinks(self, tmp_path):
        write(tmp_path / "assets" / "logo.png", "")
        check_no_symlinks(tmp_path)


@pytest.mark.skipif(not shutil.which("pandoc"), reason="needs pandoc")
class TestContent:
    @pytest.fixture
    def folder(self, tmp_path):
        write(tmp_path / "assets" / "logo.png", "")
        return tmp_path

    @pytest.mark.parametrize(
        "text",
        [
            "## <!-- edit:sections/document/status.md -->Status\n\n<!-- edit:glossary/a.yaml -->\nTerm",
            '<!-- a < b -->\n\nText <!-- example: <img src="logo.png"> --> and <!--\nmore\nlines\n-->.',
            "Plain text with **bold** and a [link](https://ceos.org) and <https://ceos.org>.",
            "Less than: a < b and 5<6.",
            "```xml\n<band name='x'>\n```",
            "~~~\n<script>\n~~~",
            "Inline `<b>` code.",
            "    <band name='x'>",
            "Some code:\n\n    <band name='x'>\n\n    </band>\n\nAnd text.",
            "A [heading](#x){.unnumbered} and a [span]{.note}.",
            "![x](assets/logo.png){#fig:x width=50% height=2cm}",
            "## A {#sec:a label=x}",
            "::: {.changelog columns=a|b widths=0.5|0.5}\nx\n:::",
        ],
    )
    def test_allowed(self, folder, text):
        assert check_content(text, folder) == []

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            ("<script>alert(1)</script>", "Raw html is not allowed"),
            ("## A <script>alert(1)</script> title", "Raw html is not allowed"),
            ("An <iframe src='file:///etc/passwd'>", "Raw html is not allowed"),
            ("<img src=x onerror=alert(1)/>", "Raw html is not allowed"),
            ("<!-- x --><script>alert(1)</script>", "Raw html is not allowed"),
            ("Text <!-- x --><b>y</b><!-- z -->", "Raw html is not allowed: <b>"),
            ("<!-- a --> <img src=../secret.png> <!-- b -->", "Raw html is not allowed: <img"),
            # Raw fences and inlines keep their text as is, so it can continue after the first comment
            ("```{=html}\n<!-- a --><img src=../secret.png><!-- b -->\n```", "Raw html is not allowed: <!-- a -->"),
            ("`<!-- a --><img src=../secret.png><!-- b -->`{=html}", "Raw html is not allowed: <!-- a -->"),
            ("`<!-- a --!><img src=../secret.png> -->`{=html}", "Raw html is not allowed: <!-- a --!>"),
            ("`<!--><img src=../secret.png>-->`{=html}", "Raw html is not allowed: <!--><img"),
            ("`<!---><img src=../secret.png>-->`{=html}", "Raw html is not allowed: <!---><img"),
            ("```{=html}\n<b>x</b>\n```", "Raw html is not allowed"),
            ("`<b>x</b>`{=html}", "Raw html is not allowed"),
            ("Text\n    <b>continued paragraph, not code</b>", "Raw html is not allowed"),
            ('[click]{onclick="alert(1)"}', "The attribute 'onclick' is not allowed"),
            ("[x]{style='background: url(/etc/passwd)'}", "The attribute 'style' is not allowed"),
            ("::: {data-src=/etc/passwd}\nx\n:::", "The attribute 'data-src' is not allowed"),
            ("![v](assets/logo.png){poster=../secret}", "The attribute 'poster' is not allowed"),
            ("[x]{lang=de}", "The attribute 'lang' is not allowed"),
            ("[x]{custom-style=Quote}", "The attribute 'custom-style' is not allowed"),
            ("---\ncss: /etc/passwd\n---\n\nx", "The metadata 'css' is not allowed"),
            ("---\nheader-includes: x\n---\n\nx", "The metadata 'header-includes' is not allowed"),
            ("---\nhighlighting-css: x\n---\n\nx", "The metadata 'highlighting-css' is not allowed"),
            ("---\ncsl: ../x.csl\n---\n\nx", "The metadata 'csl' is not allowed"),
        ],
    )
    def test_refused(self, folder, text, message):
        assert any(message in problem for problem in check_content(text, folder))

    def test_reports_all_problems_with_their_building_blocks(self, folder):
        markdown = (
            "## <!-- edit:requirements/a.yaml -->A {onclick=x}\n\n<b>x</b> [x](htps://x.org)\n\n"
            "<!-- edit:glossary/b.yaml -->\nTerm\n:   ![x](../outside.png)\n"
        )
        assert check_content(markdown, folder) == [
            "requirements/a.yaml: The attribute 'onclick' is not allowed",
            "requirements/a.yaml: Raw html is not allowed: <b>",
            "requirements/a.yaml: Raw html is not allowed: </b>",
            "requirements/a.yaml: Links must use one of the schemes http, https, mailto, ftp, ftps, sftp, s3, "
            "found 'htps://x.org'",
            "glossary/b.yaml: Images must be files in the assets folder, found '../outside.png'",
        ]

    def test_allows_the_metadata_of_the_template(self, folder):
        markdown = "---\ntitle: T\nnocite: '@*'\nsubtitle: S\n---\n\nx"
        assert check_content(markdown, folder) == ["The metadata 'subtitle' is not allowed"]
        write(folder / "templates" / "template.md", "---\ntitle: x\n# a comment\nsubtitle: >-\n  y\n---\n\nz")
        assert check_content(markdown, folder) == ["The metadata 'nocite' is not allowed"]

    def test_allows_quoted_metadata_keys_of_the_template(self, folder):
        write(folder / "templates" / "template.md", "---\n'title': x\n\"nocite\": y\n'it''s': z\n---\n\nz")
        markdown = "---\ntitle: T\nnocite: '@*'\nit's: S\n---\n\nx"
        assert check_content(markdown, folder) == []

    def test_refused_metadata_never_reaches_citeproc(self, folder):
        # citeproc would fail to read the style, or fetch it from a URL
        markdown = "---\ncsl: missing.csl\nnocite: '@*'\n---\n\nSee [@a].\n"
        assert check_content(markdown, folder, "@misc{a, title={A}}\n") == ["The metadata 'csl' is not allowed"]

    def test_content_cant_add_problems_of_its_own(self, folder):
        markdown = "---\nceos-ard-problems: [fake]\n---\n\nx"
        assert check_content(markdown, folder) == ["The metadata 'ceos-ard-problems' is not allowed"]

    def test_lists_its_problems_with_the_ones_of_the_links(self, folder):
        markdown = "## <!-- edit:a.yaml -->A\n\n[x]{style=x} ![y](../outside.png) <b>z</b>\n"
        assert check_content(markdown, folder) == [
            "a.yaml: The attribute 'style' is not allowed",
            "a.yaml: Raw html is not allowed: <b>",
            "a.yaml: Raw html is not allowed: </b>",
            "a.yaml: Images must be files in the assets folder, found '../outside.png'",
        ]


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
@pytest.mark.parametrize("csp", [True, False])
def test_html_runs_no_scripts_in_browsers(tmp_path, chromium, csp):
    from playwright.sync_api import sync_playwright

    # With this class, --embed-resources puts the SVG markup into the HTML, including its scripts and event handlers
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><script>document.title = "ran"</script><rect onload="x()"/></svg>'
    write(tmp_path / "assets" / "logo.svg", svg)
    write(tmp_path / "out" / "doc.md", "---\ntitle: Doc\n---\n\n![logo](assets/logo.svg){.inline-svg}\n")
    write(tmp_path / "out" / "doc.bib", "")
    if not csp:
        # The control: a template without the policy runs the script
        write(
            tmp_path / "templates" / "template.html",
            "<html><head><title>$title$</title></head><body>$body$</body></html>",
        )
    run_pandoc(tmp_path / "out" / "doc", "html", tmp_path, self_contained=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto((tmp_path / "out" / "doc.html").as_uri())
        title = page.title()
        browser.close()

    assert title == ("Doc" if csp else "ran")


@needs_pandoc
class TestPandoc:
    def build(self, tmp_path, markdown, bibtex=""):
        write(tmp_path / "templates" / "template.html", "$body$")
        write(tmp_path / "out" / "doc.md", markdown)
        write(tmp_path / "out" / "doc.bib", bibtex)
        write(tmp_path / "assets" / "logo.png", "")
        write(tmp_path / "outside.png", "secret")
        run_pandoc(tmp_path / "out" / "doc", "html", tmp_path, self_contained=False)
        return (tmp_path / "out" / "doc.html").read_text(encoding="utf-8")

    def test_ignores_lua_filters_of_the_input_directory(self, tmp_path):
        write(tmp_path / "templates" / "pagebreak.lua", "error('content code ran')")
        write(tmp_path / "templates" / "toc.lua", "error('content code ran')")
        assert "Title" in self.build(tmp_path, "# Title\n")

    def test_lists_all_problems(self, tmp_path):
        with pytest.raises(ValueError) as error:
            self.build(tmp_path, "<!-- edit:a.yaml -->\n\n[x]{style=x} [y]{onclick=y} ![z](../outside.png)\n")
        assert str(error.value) == (
            "Generating the html file failed:\n"
            "- a.yaml: The attribute 'style' is not allowed\n"
            "- a.yaml: The attribute 'onclick' is not allowed\n"
            "- a.yaml: Images must be files in the assets folder, found '../outside.png'"
        )

    def test_keeps_editor_comments_and_local_images(self, tmp_path):
        html = self.build(tmp_path, "<!-- edit:requirements/a.yaml -->\n\n# Title\n\n![logo](assets/logo.png)\n")
        assert "<!-- edit:requirements/a.yaml -->" in html
        assert 'src="assets/logo.png"' in html

    def test_problems_belong_to_the_file_of_a_field_marker(self, tmp_path):
        with pytest.raises(ValueError) as error:
            self.build(tmp_path, "## <!-- edit:pfs/SR/document.yaml#/background -->Background\n\n[x]{style=x}\n")
        assert str(error.value).endswith(" pfs/SR/document.yaml: The attribute 'style' is not allowed")

    def test_marks_the_entries_of_the_bibliography(self, tmp_path):
        bibtex = "@misc{smith2020, title={A}}\n@misc{doe2021, title={B}}\n"
        html = self.build(tmp_path, "---\nnocite: '@*'\n---\n\n::: {#refs}\n:::\n", bibtex)
        for key in ["smith2020", "doe2021"]:
            assert re.search(rf'<div id="ref-{key}"[^>]*>\s*<!-- edit:references/{key}.bib -->', html)

    @pytest.mark.parametrize(
        ("markdown", "message"),
        [
            ("<script>alert(1)</script>", "Raw html is not allowed"),
            ("Text <iframe src='/etc/passwd'></iframe>", "Raw html is not allowed"),
            ("```{=html}\n<b>x</b>\n```", "Raw html is not allowed"),
            ("<!-- x --><script>alert(1)</script>", "Raw html is not allowed"),
            ("---\ntitle: <script>alert(1)</script>\n---\n\nx", "Raw html is not allowed"),
            ("![v](assets/logo.png){poster=../outside.png}", "The attribute 'poster' is not allowed"),
            ("---\ncss: /etc/passwd\n---\n\nx", "The metadata 'css' is not allowed"),
            (
                "---\nheader-includes: <script>alert(1)</script>\n---\n\nx",
                "The metadata 'header-includes' is not allowed",
            ),
            ("[x]{style='background: url(/etc/passwd)'}", "The attribute 'style' is not allowed"),
            ('[click]{onclick="alert(1)"}', "The attribute 'onclick' is not allowed"),
            ("::: {data-src=/etc/passwd}\nx\n:::", "The attribute 'data-src' is not allowed"),
        ],
    )
    def test_refuses(self, tmp_path, markdown, message):
        with pytest.raises(ValueError, match="html file failed") as error:
            self.build(tmp_path, markdown)
        assert message in str(error.value)
