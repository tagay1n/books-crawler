import hashlib
import io
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import requests
from typer.testing import CliRunner
from urllib3.response import HTTPResponse

from ingestion import core, isxaki
from ingestion.cli import app
from ingestion.config import Settings, load_settings
from ingestion.network import Budget, HTTP, InvalidDocument
from ingestion.paging import PageRequest
from ingestion.state import Manifest


PDF = b"%PDF-1.7\nLocal original fixture\n%%EOF\n"
FILE_URL = "https://isxaki.com/wp-content/uploads/book.pdf"


def card(title="Book", href="http://isxaki.com/wp-content/uploads/book.pdf", description="Kazan, 1911"):
    link = f'<a href="{href}">Укырга</a>' if href else '<span>Укырга</span>'
    return f'''<div class="elementor-column"><div class="elementor-widget-image-box">
        <h3 class="elementor-image-box-title">{title}</h3>
        <p class="elementor-image-box-description">{description}</p></div>
        <div class="elementor-button-wrapper">{link}</div></div>'''


def collection(cards=None):
    return ('<header><a href="/wp-content/uploads/banner.pdf">Banner</a></header>'
            '<h2>Оригиналь басмалар</h2><div data-elementor-type="wp-page">'
            + (card() if cards is None else cards) + '<p>Source footnote</p></div>'
            '<footer><a href="/wp-content/uploads/footer.pdf">Footer</a></footer>')


def root():
    paths = list(isxaki.COLLECTION_PATHS)
    paths[1] = "/tt/ijat/asarlar/"
    paths[2] = "/tt/asarlar-1908-1918-ellar/"
    return '<h1>Иҗат</h1>' + ''.join(f'<a href="http://isxaki.com{path}">Section</a>' for path in paths)


def response(url, body=PDF, status=200, mime="application/pdf"):
    value = requests.Response()
    value.status_code, value.url = status, url
    value.headers.update({"Content-Type": mime, "Content-Length": str(len(body))})
    value.raw = HTTPResponse(body=io.BytesIO(body), preload_content=False)
    return value


class IsxakiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.settings = Settings(self.directory, isxaki.ARCHIVE_URL, 25, 25, 1000000, 1000000,
                                 1, 30, 1, 1, .001, 1)
        self.urls = ["https://isxaki.com" + path for path in isxaki.COLLECTION_PATHS]

    @property
    def manifest(self):
        return Manifest(self.directory / "isxaki", "isxaki")

    def discover(self, resources=None, settings=None):
        resources = resources if resources is not None else {
            isxaki.ARCHIVE_URL: root(), **{url: collection() for url in self.urls}}
        calls = []

        def text(http, url, **kwargs):
            calls.append(url)
            value = resources[url]
            if isinstance(value, Exception):
                raise value
            return value

        with patch.object(HTTP, "text", autospec=True, side_effect=text):
            report = core.run(settings or self.settings, "isxaki", "discover", log=lambda _: None)
        return report, calls

    def test_entry_point_has_exactly_five_normalized_collections(self):
        page = isxaki.parse_listing(root(), PageRequest(isxaki.ARCHIVE_URL), isxaki.ARCHIVE_URL)
        self.assertEqual([r.url for r in page.following], self.urls)
        self.assertEqual(page.records, [])
        for url in self.urls:
            self.assertEqual(isxaki.parse_listing(collection(), PageRequest(url), isxaki.ARCHIVE_URL).records, [url])

    def test_missing_structure_is_an_error_instead_of_an_empty_catalog(self):
        for html in ('<html>Login</html>', '<h1>Иҗат</h1>', '<h1>Not the catalog</h1>' + root()):
            with self.subTest(html=html), self.assertRaises(ValueError):
                isxaki.parse_listing(html, PageRequest(isxaki.ARCHIVE_URL), isxaki.ARCHIVE_URL)
        for html in ('<h2>Books</h2>', '<h2>Books</h2><div data-elementor-type="wp-page"></div>'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                isxaki.record(html, self.urls[0])

    def test_preserves_cards_footnotes_and_original_links_without_inferred_facts(self):
        metadata, assets = isxaki.record(collection(card("Бай углы") + card("No file", None)), self.urls[0])
        self.assertEqual(metadata["cards"][0]["title_raw"], "Бай углы")
        self.assertEqual(metadata["cards"][0]["description_raw"], "Kazan, 1911")
        self.assertTrue(metadata["cards"][0]["links"][0]["original_url"].startswith("http:"))
        self.assertEqual(metadata["cards"][1]["links"], [])
        self.assertIn("Source footnote", metadata["description"])
        self.assertNotIn("language", metadata)
        self.assertNotIn("publication_year", metadata)
        self.assertEqual([a["url"] for a in assets], [FILE_URL])

    def test_duplicate_cards_and_alias_links_share_one_asset(self):
        html = collection(card() + card("Second title", FILE_URL + "#page=3"))
        metadata, assets = isxaki.record(html, self.urls[0])
        self.assertEqual(len(metadata["cards"]), 2)
        self.assertTrue(metadata["cards"][1]["links"][0]["original_url"].endswith("#page=3"))
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["card_titles"], ["Book", "Second title"])

    def test_only_supported_document_links_from_cards_are_eligible(self):
        html = collection(card("Outside", "https://other.test/book.pdf")
                          + card("Cover", "/cover.jpg") + card("HTML text", "/story.html")
                          + card("Ordinary page", "/story/") + card("DjVu", "/book.djvu"))
        metadata, assets = isxaki.record(html, self.urls[0])
        self.assertEqual(len(metadata["cards"]), 5)
        self.assertEqual(len(assets), 2)
        self.assertIsNotNone(assets[0]["unsupported_reason"])
        self.assertIsNone(assets[1]["unsupported_reason"])
        self.assertEqual(assets[1]["extension"], ".djvu")

    def test_unicode_document_links_are_encoded_and_malformed_paths_are_not_repaired(self):
        url = isxaki.normalize_url("/wp-content/uploads/Китап.pdf", self.urls[0])
        self.assertIn("%D0", url)
        _, assets = isxaki.record(collection(card(href="/26-hatin.pdf/22-oigataba.pdf")), self.urls[0])
        self.assertEqual(assets[0]["url"], "https://isxaki.com/26-hatin.pdf/22-oigataba.pdf")

    def test_bounded_discovery_resumes_and_unchanged_rescan_keeps_observations(self):
        settings = replace(self.settings, max_pages=1)
        report, _ = self.discover(settings=settings)
        self.assertFalse(report["discovery_complete"])
        self.assertEqual(len(self.manifest.data["discovery_scan"]["frontier"]), 5)
        for index in range(5):
            report, calls = self.discover(settings=settings)
            self.assertNotIn(isxaki.ARCHIVE_URL, calls)
            self.assertEqual(report["discovery_complete"], index == 4)
        self.assertEqual(len(self.manifest.data["records"]), 5)
        self.discover()
        self.assertTrue(all(len(r["observations"]) == 1 for r in self.manifest.data["records"].values()))

    def test_failed_record_stays_pending_and_other_collections_continue(self):
        resources = {isxaki.ARCHIVE_URL: root(), **{url: collection() for url in self.urls}}
        count = 0

        def text(http, url, **kwargs):
            nonlocal count
            if url == self.urls[0]:
                count += 1
                if count == 2:
                    raise requests.ConnectionError("Interrupted record fetch")
            return resources[url]

        with patch.object(HTTP, "text", autospec=True, side_effect=text):
            report = core.run(self.settings, "isxaki", "discover", log=lambda _: None)
        self.assertFalse(report["discovery_complete"])
        self.assertEqual(len(self.manifest.data["records"]), 4)
        self.assertEqual(self.manifest.data["discovery_scan"]["pending_records"], [self.urls[0]])
        report, calls = self.discover()
        self.assertEqual(calls, [self.urls[0]])
        self.assertTrue(report["discovery_complete"])

    def test_shared_pipeline_download_deduplicates_bytes_and_skips_verified_files(self):
        self.discover()
        with patch.object(HTTP, "get", autospec=True, side_effect=lambda http, url, **kw: response(url)):
            report = core.run(self.settings, "isxaki", "download", log=lambda _: None)
        self.assertEqual(report["downloaded"], 5)
        self.assertEqual(report["reused_blobs"], 4)
        results = [a["results"][0] for a in self.manifest.data["assets"].values()]
        self.assertEqual(len({r["path"] for r in results}), 1)
        for result in results:
            self.assertEqual(result["sha256"], hashlib.sha256(PDF).hexdigest())
            self.assertEqual(result["md5"], hashlib.md5(PDF).hexdigest())
            self.assertEqual(result["size"], len(PDF))
            self.assertTrue(result["observation_id"])
        with patch.object(HTTP, "get") as get:
            report = core.run(self.settings, "isxaki", "download", log=lambda _: None)
        get.assert_not_called()
        self.assertEqual(report["skipped"], 5)

    def test_bad_downloads_do_not_prevent_independent_success(self):
        manifest = self.manifest
        html = collection(card("Login", "/login.pdf") + card("Broken", "/broken.pdf") + card("Good"))
        metadata, assets = isxaki.record(html, self.urls[0])
        manifest.observe(metadata, assets, isxaki.PARSER_VERSION)

        def get(http, url, **kwargs):
            if url.endswith("login.pdf"):
                return response(url, b"<html>Login</html>", mime="text/html")
            if url.endswith("broken.pdf"):
                return response(url, b"missing", status=404)
            return response(url)

        with patch.object(HTTP, "get", autospec=True, side_effect=get):
            report = core.run(self.settings, "isxaki", "download", log=lambda _: None)
        self.assertEqual(report["downloaded"], 1)
        self.assertEqual(len(report["errors"]), 2)
        self.assertEqual(self.manifest.status()["current_assets"]["failed"], 2)

    def test_run_honors_item_cap_and_download_recovers_damaged_local_file(self):
        resources = {isxaki.ARCHIVE_URL: root(), **{url: collection() for url in self.urls}}
        settings = replace(self.settings, max_items=1)
        with patch.object(HTTP, "text", autospec=True, side_effect=lambda http, url, **kw: resources[url]), \
                patch.object(HTTP, "get", autospec=True, side_effect=lambda http, url, **kw: response(url)):
            report = core.run(settings, "isxaki", "run", log=lambda _: None)
        self.assertTrue(report["discovery_complete"])
        self.assertEqual(report["downloaded"], 1)
        self.assertIn("download item cap", report["stops"])
        self.assertEqual(self.manifest.status()["current_assets"]["pending"], 4)
        asset = next(a for a in self.manifest.data["assets"].values() if a["results"])
        path = self.manifest.directory / asset["results"][0]["path"]
        path.write_bytes(b"damaged")
        with patch.object(HTTP, "get", autospec=True, side_effect=lambda http, url, **kw: response(url)):
            report = core.run(settings, "isxaki", "download", log=lambda _: None)
        self.assertEqual(path.read_bytes(), PDF)
        self.assertEqual(report["started_items"], 1)
        self.assertEqual(report["unchanged_downloads"], 1)

    def test_https_origin_guard_rejects_writes_and_external_redirects(self):
        http = HTTP(self.settings, Budget(self.settings), {"requests": 0})
        self.addCleanup(http.close)
        isxaki.prepare_http(http, None)
        with patch.object(http.session, "get") as get:
            for url in ("https://other.test/book.pdf", "http://isxaki.com/book.pdf"):
                with self.assertRaises(ValueError):
                    http.get(url)
            get.assert_not_called()
        with self.assertRaises(ValueError):
            http.request("POST", isxaki.ARCHIVE_URL)
        redirect = response(isxaki.ARCHIVE_URL, b"", 302)
        redirect.headers["Location"] = "https://other.test/catalog/"
        with self.assertRaises(InvalidDocument):
            http.session.hooks["response"][0](redirect)

    def test_cli_lists_source_and_example_config_can_select_it(self):
        self.assertIn("isxaki", CliRunner().invoke(app, ["sources"]).stdout)
        settings = load_settings(Path(__file__).resolve().parents[1] / "ingestion.example.yaml", "isxaki")
        self.assertEqual(settings.archive_url, isxaki.ARCHIVE_URL)

    def test_status_does_not_request_or_write(self):
        with patch.object(HTTP, "request") as request:
            report = core.run(self.settings, "isxaki", "status")
        request.assert_not_called()
        self.assertEqual(report["records"], 0)
        self.assertFalse(self.manifest.directory.exists())


if __name__ == "__main__":
    unittest.main()
