import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import pymupdf
import requests

from ingestion import core, image_issues, kazanutlary, tatkniga
from ingestion.config import Settings
from ingestion.discovery import discover
from ingestion.network import Budget, BudgetStop, HTTP
from ingestion.state import Manifest
from ingestion.tatkniga_reader import UnsupportedReader, parse_configuration, read_pages


ROOT = tatkniga.ARCHIVE_URL
BOOK = ROOT + "book.html"
READER = "https://tatkniga.ru/upload/interactive_books/example/book.html"
CONFIG = "https://tatkniga.ru/upload/interactive_books/example/javascript/config.js"
READER_HTML = b'<script src="javascript/config.js"></script>'


def configuration(pages=None, count=None):
    pages = pages if pages is not None else [{"l": "files/page/1.jpg"}, {"n": "files/page/2.jpg"}]
    return ('\ufeffvar bookConfig={totalPagesCaption:"999",totalPageCount:'
            + str(len(pages) if count is None else count) + ',normalPath:"files/page/"};\n'
            + "var fliphtml5_pages=" + json.dumps(pages) + ";")


def product(language=None, links=None, product_id="123"):
    language_html = (f'<div class="propertyTable"><span class="propertyName">Язык</span>'
                     f'<span class="propertyValue">{language}</span></div>') if language else ""
    links = links if links is not None else [(READER, "Читать")]
    return (f'<div id="bx_1_{product_id}"><h1 class="changeName">Example book</h1>'
            f'<div id="catalogElement"><div id="browse">{language_html}</div>'
            + "".join(f'<a href="{url}">{label}</a>' for url, label in links) + "</div></div>")


def jpeg(color, size=(80, 110)):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format="JPEG")
    return output.getvalue()


def pdf_bytes():
    with pymupdf.open() as document:
        document.new_page()
        return document.tobytes()


def summary():
    return dict(pages=0, records=0, observations=0, downloaded=0, reused_blobs=0,
                not_modified=0, unchanged_downloads=0, skipped=0, requests=0,
                network_retries=0, stops=[], errors=[])


def settings(directory, **changes):
    defaults = dict(artifacts_root=Path(directory), archive_url=ROOT, max_pages=2, max_items=25,
                    max_download_bytes=20 * 1024 * 1024, max_file_bytes=5 * 1024 * 1024,
                    disk_reserve_bytes=1, soft_deadline_seconds=30,
                    connect_timeout_seconds=1, read_timeout_seconds=1, pacing_seconds=.001,
                    retry_attempts=1)
    defaults.update(changes)
    return Settings(**defaults)


class Body(io.BytesIO):
    def read(self, amount=-1, decode_content=False):
        return super().read(amount)


class FakeHTTP(HTTP):
    """Exercise the real text reader, retry policy, downloader, and byte budget."""

    def __init__(self, settings, resources, report=None):
        super().__init__(settings, Budget(settings), report if report is not None else summary())
        self.resources, self.calls = resources, []

    def request(self, method, url, *, headers=None, data=None):
        self.budget.check()
        self.calls.append(url)
        self.summary["requests"] += 1
        resource = self.resources[url]
        if isinstance(resource, list):
            resource = resource.pop(0)
        if isinstance(resource, Exception):
            raise resource
        if isinstance(resource, (bytes, str)):
            resource = {"body": resource}
        body = resource.get("body", b"")
        if isinstance(body, str):
            body = body.encode("utf-8")
        response = requests.Response()
        response.status_code = resource.get("status", 200)
        response.url = resource.get("url", url)
        response.headers.update({"Content-Type": resource.get("mime", "application/octet-stream"),
                                 "Content-Length": str(len(body))})
        response.raw = Body(body)
        response.raise_for_status()
        return response


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.settings = settings(self.temporary.name)

    def http(self, resources):
        http = FakeHTTP(self.settings, resources)
        self.addCleanup(http.close)
        return http

    def resolve(self, language=None, links=None, resources=None):
        metadata, assets = tatkniga.record(product(language, links), BOOK)
        http = self.http(resources or {READER: READER_HTML, CONFIG: configuration()})
        return (*tatkniga.resolve_record(http, metadata, assets), http)

    def test_uses_explicit_list_order_large_images_and_normal_fallback(self):
        pages = parse_configuration(configuration([
            {"l": "files/large/10.jpg", "n": "files/page/10.jpg", "t": "files/thumb/10.jpg"},
            {"l": "", "n": "files/page/2.jpg"}]), READER)
        self.assertTrue(pages[0]["url"].endswith("/files/large/10.jpg"))
        self.assertTrue(pages[1]["url"].endswith("/files/page/2.jpg"))
        self.assertEqual([p["page_index"] for p in pages], [0, 1])

    def test_repeated_images_remain_distinct_pages(self):
        pages = parse_configuration(configuration([{"l": "blank.jpg"}] * 2), READER)
        self.assertEqual(pages[0]["url"], pages[1]["url"])
        self.assertNotEqual(pages[0]["source_asset_key"], pages[1]["source_asset_key"])

    def test_rejects_invalid_counts_descriptors_and_non_json(self):
        for config in (configuration(count=1), configuration([], 0), configuration(count=10001),
                       configuration([None]), configuration([{"t": "thumb.jpg"}]),
                       configuration([{"l": 10}]), 'totalPageCount:1, fliphtml5_pages=[danger()];'):
            with self.subTest(config=config), self.assertRaises(ValueError):
                parse_configuration(config, READER)

    def test_unknown_formats_and_external_images_remain_unsupported(self):
        for config in ("var otherReader = {};", configuration([{"l": "https://other.test/p.jpg"}]),
                       configuration([{"l": "http://tatkniga.ru/p.jpg"}]),
                       configuration([{"l": "files/page/1.png"}])):
            with self.subTest(config=config), self.assertRaises(UnsupportedReader):
                parse_configuration(config, READER)

    def test_missing_label_is_allowed_without_inventing_language(self):
        metadata, assets, _ = self.resolve()
        self.assertEqual(metadata["language_selection"], "review")
        self.assertNotIn("language_raw", metadata)
        self.assertEqual(metadata["reader_language_selection"], "missing_label_allowed")
        self.assertEqual(metadata["expected_pages"], 2)
        self.assertEqual(len(assets), 2)
        self.assertTrue(all(a["kind"] == "page_image" for a in assets))

    def test_language_rules_are_applied_before_fetching(self):
        for language, code in (("рус", "language_excluded"), ("Unknown", "language_unknown")):
            with self.subTest(language=language):
                metadata, assets, http = self.resolve(language)
                self.assertEqual(assets[0]["unsupported_code"], code)
                self.assertNotIn("expected_pages", metadata)
                self.assertEqual(http.calls, [])
        metadata, _, _ = self.resolve("тат / рус")
        self.assertEqual(metadata["reader_language_selection"], "selected")

    def test_direct_pdf_is_preferred_only_when_eligible(self):
        links = [(READER, "Читать"), ("/native.pdf", "Скачать")]
        metadata, assets, http = self.resolve("тат", links)
        self.assertEqual(assets[0]["unsupported_code"], "reader_superseded")
        self.assertIsNone(assets[1]["unsupported_reason"])
        self.assertNotIn("expected_pages", metadata)
        self.assertEqual(http.calls, [])
        metadata, assets, _ = self.resolve(None, links)
        self.assertEqual(metadata["expected_pages"], 2)
        self.assertEqual(assets[0]["unsupported_code"], "language_unknown")

    def test_distinct_readers_require_review_and_repeated_links_collapse(self):
        _, assets, http = self.resolve(links=[(READER, "Читать"), (READER + "?other=1", "Читать")])
        self.assertTrue(all(a["unsupported_code"] == "reader_ambiguous" for a in assets))
        self.assertEqual(http.calls, [])
        metadata, assets, _ = self.resolve(links=[(READER, "Читать"), (READER, "Читать")])
        self.assertEqual(metadata["expected_pages"], 2)
        self.assertEqual(len(assets), 2)

    def test_unknown_reader_and_legacy_reader_are_retained(self):
        metadata, assets, _ = self.resolve(resources={READER: "<html>Unknown reader</html>"})
        self.assertEqual(assets[0]["unsupported_code"], "reader_unsupported")
        self.assertNotIn("expected_pages", metadata)
        _, assets, http = self.resolve(links=[("/reader/default2.php?baseurl=old", "Читать")])
        self.assertEqual(assets[0]["unsupported_code"], "reader_deferred")
        self.assertEqual(http.calls, [])

    def test_upgrading_reader_descriptors_preserves_observation_history(self):
        metadata, old_assets = tatkniga.record(product(), BOOK)
        manifest = Manifest(Path(self.temporary.name) / "tatkniga", "tatkniga")
        manifest.observe(metadata, old_assets, 1, record_key="product:123")
        old_id = next(iter(manifest.data["assets"]))
        metadata, pages, _ = self.resolve()
        manifest.observe(metadata, pages, tatkniga.PARSER_VERSION, record_key="product:123")
        self.assertEqual(len(manifest.data["records"]["product:123"]["observations"]), 2)
        self.assertFalse(manifest.data["assets"][old_id]["current"])
        self.assertEqual(manifest.status()["current_assets"]["pending"], 2)
        self.assertNotIn("unsupported_reasons", manifest.status())

    def test_relative_references_follow_final_reader_url(self):
        final = READER.replace("example/", "moved/")
        config = CONFIG.replace("example/", "moved/")
        http = self.http({READER: {"body": READER_HTML, "url": final}, config: configuration()})
        metadata, assets = read_pages(http, READER)
        self.assertEqual(metadata["reader_final_url"], final)
        self.assertEqual(metadata["reader_configuration_url"], config)
        self.assertIn("/moved/files/page/", assets[0]["url"])

    def test_pagespeed_scripts_resolve_explicit_original_without_evaluating_bundle(self):
        for suffix in (".pagespeed.jm.hash_123.js", "+LoadingJS.js.pagespeed.jc.hash_123.js"):
            with self.subTest(suffix=suffix):
                html = f'<script src="javascript/config.js{suffix}"></script><script>eval(bundle)</script>'
                metadata, assets, http = self.resolve(resources={READER: html, CONFIG: configuration()})
                self.assertEqual(metadata["expected_pages"], 2)
                self.assertEqual(http.calls, [READER, CONFIG])

    def test_external_reader_configuration_and_redirect_are_rejected(self):
        with self.assertRaises(ValueError):
            self.http({}).text_response("https://other.test/reader", origin=ROOT)
        http = self.http({READER: {"body": READER_HTML, "url": "https://other.test/reader"}})
        with self.assertRaises(ValueError):
            read_pages(http, READER)
        http = self.http({READER: '<script src="https://other.test/javascript/config.js"></script>'})
        with self.assertRaises(ValueError):
            read_pages(http, READER)
        self.assertEqual(http.calls, [READER])

    def test_config_fetch_failure_leaves_discovery_pending_while_other_records_proceed(self):
        other = ROOT + "other.html"
        cards = "".join(f'<div class="item product sku" id="bx_1_{i}">'
                        f'<a class="name" href="{url}">Book {i}</a></div>'
                        for i, url in enumerate((BOOK, other), 1))
        listing = ('<h1>Library</h1><div id="catalogSection"><div class="items productList">'
                   + cards + '</div></div><div class="bx-pagination"><span class="bx-active">1</span></div>'
                   '<div class="countElements"><span class="dropDownSelected">30</span></div>')
        resources = {ROOT: listing, BOOK: product(), READER: READER_HTML,
                     CONFIG: requests.ConnectionError("interrupted configuration"),
                     other: product("тат", [("/native.pdf", "Скачать")], "456")}
        http = self.http(resources)
        manifest = Manifest(Path(self.temporary.name) / "tatkniga", "tatkniga")
        discover(http, manifest, tatkniga, http.summary, lambda _: None)
        self.assertFalse(manifest.data["discovery"]["complete"])
        self.assertEqual(manifest.data["discovery_scan"]["pending_records"], [BOOK])
        self.assertIn("product:456", manifest.data["records"])
        resources[CONFIG] = configuration()
        http = self.http(resources)
        discover(http, manifest, tatkniga, http.summary, lambda _: None)
        self.assertTrue(manifest.data["discovery"]["complete"])
        self.assertEqual(manifest.data["discovery_scan"]["adapter_version"], 2)
        self.assertNotIn(other, http.calls)
        self.assertEqual(manifest.status()["pdf_books"]["incomplete"], 1)


class AssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.settings = settings(self.directory)
        self.manifest = Manifest(self.directory / "tatkniga", "tatkniga")
        self.pages = parse_configuration(configuration(), READER)
        self.metadata = {"url": BOOK, "title": "Example", "expected_pages": 2,
                         "attachments": [{k: a[k] for k in ("url", "page_index")} for a in self.pages]}
        self.manifest.observe(self.metadata, self.pages, 2, record_key="product:123")
        self.resources = {self.pages[0]["url"]: jpeg("red"), self.pages[1]["url"]: jpeg("blue")}

    def download(self, *, recheck=False, settings=None, source="tatkniga"):
        http = FakeHTTP(settings or self.settings, self.resources)
        self.addCleanup(http.close)
        if source == "tatkniga":
            tatkniga.download(http, self.manifest, http.summary, lambda _: None, recheck)
        else:
            image_issues.download(http, self.manifest, http.summary, lambda _: None, recheck)
        return http

    @property
    def record(self):
        return self.manifest.data["records"]["product:123"]

    @property
    def pdf(self):
        return self.directory / "tatkniga" / self.record["pdf"]["results"][-1]["path"]

    def test_assembly_preserves_order_dimensions_and_reuses_pdf(self):
        http = self.download(settings=settings(self.directory, max_items=1))
        self.assertEqual(http.budget.items, 1)
        self.assertEqual(http.summary["pdf_assembled"], 1)
        with pymupdf.open(self.pdf) as document:
            self.assertEqual(document.page_count, 2)
            for i, dominant in ((0, 0), (1, 2)):
                pixmap = document[i].get_pixmap()
                rgb = pixmap.pixel(10, 10)
                self.assertEqual(rgb.index(max(rgb)), dominant)
                self.assertAlmostEqual(document[i].rect.width / document[i].rect.height, 80 / 110)
        http = self.download()
        self.assertEqual(http.calls, [])
        self.assertEqual(http.budget.items, 0)
        self.assertEqual(http.summary["pdf_reused"], 1)
        self.assertEqual(self.manifest.status()["pdf_books"]["complete"], 1)

    def test_failed_page_preserves_other_images_and_resumes(self):
        self.resources[self.pages[1]["url"]] = requests.ConnectionError("missing page")
        http = self.download()
        self.assertEqual(http.summary["downloaded"], 1)
        self.assertEqual(self.record["pdf"]["status"], "incomplete")
        self.assertEqual(self.record["pdf"]["results"], [])
        self.resources[self.pages[1]["url"]] = jpeg("blue")
        http = self.download()
        self.assertEqual(http.calls, [self.pages[1]["url"]])
        self.assertEqual(self.record["pdf"]["status"], "complete")

    def test_corrupt_image_never_produces_pdf(self):
        self.resources[self.pages[1]["url"]] = b"not an image"
        self.download()
        self.assertEqual(self.record["pdf"]["results"], [])
        self.assertEqual(self.manifest.status()["current_assets"]["failed"], 1)
        self.assertEqual(list((self.directory / "tatkniga" / ".tmp").glob("**/*.part")), [])

    def test_missing_and_damaged_pdf_rebuild_from_verified_images(self):
        self.download()
        self.pdf.unlink()
        http = self.download()
        self.assertEqual(http.calls, [])
        self.assertEqual(http.summary["pdf_assembled"], 1)
        self.pdf.write_bytes(b"damaged")
        http = self.download()
        self.assertEqual(http.calls, [])
        self.assertEqual(http.summary["pdf_assembled"], 1)
        self.assertEqual(self.record["pdf"]["status"], "complete")

    def test_changed_page_recheck_creates_new_pdf_and_failed_recheck_is_unresolved(self):
        self.download()
        original = self.pdf
        self.resources[self.pages[1]["url"]] = jpeg("green")
        self.download(recheck=True)
        self.assertNotEqual(self.pdf, original)
        self.assertTrue(original.is_file())
        self.assertEqual(len(self.record["pdf"]["results"]), 2)
        self.resources[self.pages[0]["url"]] = requests.ConnectionError("offline")
        self.download(recheck=True)
        self.assertEqual(self.record["pdf"]["status"], "incomplete")
        self.assertTrue(self.pdf.is_file())

    def test_byte_identical_recheck_reuses_existing_pdf_result(self):
        self.download()
        http = self.download(recheck=True)
        self.assertEqual(http.summary["unchanged_downloads"], 2)
        self.assertEqual(http.summary["pdf_reused"], 1)
        self.assertEqual(len(self.record["pdf"]["results"]), 1)

    def test_damaged_local_image_is_downloaded_again(self):
        self.download()
        asset = next(iter(self.manifest.data["assets"].values()))
        (self.manifest.directory / asset["results"][-1]["path"]).write_bytes(b"damaged")
        http = self.download()
        self.assertEqual(http.calls, [asset["url"]])
        self.assertEqual(self.record["pdf"]["status"], "complete")

    def test_changed_image_url_is_pending_even_with_same_page_index(self):
        self.download()
        pages = parse_configuration(configuration([{"l": "files/page/new.jpg"}, {"n": "files/page/2.jpg"}]), READER)
        self.resources[pages[0]["url"]] = jpeg("green")
        self.manifest.observe({**self.metadata, "attachments": pages}, pages, 2, record_key="product:123")
        http = self.download()
        self.assertEqual(http.calls, [pages[0]["url"]])
        self.assertEqual(http.summary["pdf_assembled"], 1)

    def test_byte_limit_interrupts_and_resumes_without_publishing_partial_pdf(self):
        cap = len(self.resources[self.pages[0]["url"]])
        http = FakeHTTP(settings(self.directory, max_download_bytes=cap), self.resources)
        self.addCleanup(http.close)
        with self.assertRaises(BudgetStop):
            tatkniga.download(http, self.manifest, http.summary, lambda _: None, False)
        self.assertEqual(self.record["pdf"]["status"], "incomplete")
        self.assertEqual(self.record["pdf"]["results"], [])
        http = self.download()
        self.assertEqual(http.calls, [self.pages[1]["url"]])
        self.assertEqual(self.record["pdf"]["status"], "complete")

    def test_item_limit_is_shared_between_direct_files_and_whole_books(self):
        url = "https://tatkniga.ru/native.pdf"
        self.resources[url] = pdf_bytes()
        metadata = {"url": ROOT + "direct.html", "title": "Direct", "attachments": [{"url": url}]}
        self.manifest.observe(metadata, [{"url": url, "label": "PDF", "extension": ".pdf",
                                          "unsupported_reason": None}], 2)
        http = FakeHTTP(settings(self.directory, max_items=1), self.resources)
        self.addCleanup(http.close)
        with self.assertRaises(BudgetStop):
            tatkniga.download(http, self.manifest, http.summary, lambda _: None, False)
        self.assertEqual(http.calls, [url])
        http = self.download(settings=settings(self.directory, max_items=1))
        self.assertEqual(http.budget.items, 1)
        self.assertEqual(http.calls, [p["url"] for p in self.pages])
        self.assertEqual(self.record["pdf"]["status"], "complete")

    def test_missing_descriptor_fails_without_fetching_or_publishing(self):
        list(self.manifest.data["assets"].values())[-1]["current"] = False
        http = self.download()
        self.assertEqual(http.calls, [])
        self.assertEqual(self.record["pdf"]["status"], "failed")
        self.assertEqual(self.record["pdf"]["results"], [])

    def test_pdf_size_cap_and_disk_reserve_prevent_publication(self):
        self.download(settings=settings(self.directory, max_file_bytes=2000))
        self.assertEqual(self.record["pdf"]["status"], "failed")
        self.assertEqual(self.record["pdf"]["results"], [])
        with patch("ingestion.core.shutil.disk_usage", return_value=type("Disk", (), {"free": 0})()):
            with self.assertRaises(OSError):
                self.download()
        self.assertEqual(self.record["pdf"]["results"], [])

    def test_deadline_stops_before_requests(self):
        http = FakeHTTP(self.settings, self.resources)
        self.addCleanup(http.close)
        http.budget.deadline = 0
        with self.assertRaises(BudgetStop):
            tatkniga.download(http, self.manifest, http.summary, lambda _: None, False)
        self.assertEqual(http.calls, [])

    def test_existing_kazanutlary_assembly_and_status_are_preserved(self):
        html = '''<div class="journal__single"><h1 class="single-page__title">Issue</h1>
        <div id="lightgallery"><img src="/images/uploads/j-archive/example/000.jpg"></div>
        <script>let journal = 'example'; let count = 2;
        for (let index=0; index <= count; index++) {
          let image = "/images/uploads/j-archive/" + journal + "/" + zeroPad(index, 3) + ".jpg";
        }</script></div>'''
        url = "https://kazanutlary.ru/j-archive/journals/example"
        metadata, pages = kazanutlary.record(html, url)
        self.manifest = Manifest(self.directory / "kazanutlary", "kazanutlary")
        self.manifest.observe(metadata, pages)
        self.resources = {pages[0]["url"]: jpeg("red"), pages[1]["url"]: jpeg("blue")}
        http = self.download(settings=settings(self.directory, archive_url=kazanutlary.ARCHIVE_URL), source="kazanutlary")
        self.assertEqual(http.summary["download_unit"], "issue")
        self.assertEqual(http.summary["pdf_assembled"], 1)
        self.assertEqual(self.manifest.status()["pdf_issues"]["complete"], 1)


if __name__ == "__main__":
    unittest.main()
