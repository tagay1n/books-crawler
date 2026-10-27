import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import quote

import pymupdf
import requests
from typer.testing import CliRunner

from ingestion import core, miras
from ingestion.cli import app
from ingestion.config import Settings, load_settings
from ingestion.miras_session import run_cookie_probe
from ingestion.network import SourceAccessError
from ingestion.paging import CatalogChanged, PageRequest
from ingestion.state import Manifest


ROOT = miras.ARCHIVE_URL
BOOK = ROOT + "889-avyl-kyzy-.html"
ARABIC = ROOT + "807-arabic-book.html"
PDF = "https://miras.info/uploads/files/example.pdf"
ARABIC_PDF = "https://miras.info/uploads/files/arabic.pdf"
SECRET = "session-cookie-do-not-log"
AGENT = "browser-agent-do-not-log"


def card(url=BOOK, title="Авыл кызы / آول قزى", language="татарский"):
    language_html = f"<br>Язык: {language}" if language else ""
    return (f'<div class="book-card"><a href="{url}"><img src="cover.jpg"></a>'
            f'<a href="{url}">{title}</a><div>Автор: Г.Д.<br>Страниц: 62<br>'
            f'Год выпуска: 1912<br>Место издания: Казань<br>Тематика: литература{language_html}</div></div>')


def listing(cards=None, current=1, pages=(2, 3), active=None):
    cards = [card()] if cards is None else cards
    pagination = "".join(f'<a href="{ROOT}page/{n}/">{n}</a>' for n in pages)
    active = current if active is None else active
    return ('<html><head><title>Центр письменного наследия</title></head><body><div id="dle-content">'
            + "".join(cards) + f'<div class="navigation"><span class="current">{active}</span>'
            + pagination + "</div></div></body></html>")


def record(pdf=PDF, heading=False, extra=""):
    title = '<h2>Авыл кызы / آول قزى</h2>' if heading else '<div>Авыл кызы / آول قزى</div>'
    reader = (f'<iframe src="/pdf/web/viewer.html?file={quote(pdf, safe="")}"></iframe>'
              f'<a href="/pdf/web/viewer.html?file={quote(pdf, safe="")}">Открыть в новом окне</a>') if pdf else ""
    return ('<html><head><title>Центр письменного наследия</title></head><body>'
            '<a href="/footer.pdf">Unrelated footer file</a><div id="dle-content">'
            + title + '<p>Г.Д. Авыл кызы. Казан, 1912.</p><div>Автор: Г.Д.<br>Страниц: 62<br>'
            'Год выпуска: 1912<br>Тип: Книга</div>' + reader + extra + '</div></body></html>')


def pdf_bytes(pages=2):
    with pymupdf.open() as pdf:
        for _ in range(pages):
            pdf.new_page()
        return pdf.tobytes()


def settings(directory, **changes):
    values = dict(artifacts_root=Path(directory), archive_url=ROOT, max_pages=2, max_items=2,
                  max_download_bytes=2 * 1024 * 1024, max_file_bytes=1024 * 1024,
                  disk_reserve_bytes=1, soft_deadline_seconds=30, connect_timeout_seconds=1,
                  read_timeout_seconds=1, pacing_seconds=.00001, retry_attempts=1)
    values.update(changes)
    return Settings(**values)


class Body(io.BytesIO):
    def read(self, amount=-1, decode_content=False):
        return super().read(amount)


class Transport:
    """Replace the socket transport while retaining HTTP, cookies, and response hooks."""

    def __init__(self, resources):
        self.resources, self.calls, self.headers = resources, [], []

    def get(self, session, url, **kwargs):
        self.calls.append(url)
        self.headers.append(kwargs.get("headers", {}))
        value = self.resources[url]
        if isinstance(value, list):
            value = value.pop(0)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, (str, bytes)):
            value = {"body": value}
        body = value.get("body", b"")
        body = body.encode("utf-8") if isinstance(body, str) else body
        response = requests.Response()
        response.status_code = value.get("status", 200)
        response.url = value.get("url", url)
        response.headers.update({"Content-Type": value.get("mime", "application/octet-stream"),
                                 "Content-Length": str(len(body)), **value.get("headers", {})})
        response.raw = Body(body)
        for hook in session.hooks["response"]:
            response = hook(response) or response
        return response

    def install(self):
        transport = self

        def get(session, url, **kwargs):
            return transport.get(session, url, **kwargs)

        return patch.object(requests.Session, "get", get)


class ParserTests(unittest.TestCase):
    def test_moving_window_follows_next_page_not_highest_visible_number(self):
        first = miras.parse_listing(listing(pages=range(2, 12)), PageRequest(ROOT), ROOT)
        self.assertEqual(first.following[0].url, ROOT + "page/2/")
        second = miras.parse_listing(listing([card(ARABIC)], current=2, pages=[1, *range(3, 13)]),
                                     first.following[0], ROOT)
        self.assertEqual(second.following[0].url, ROOT + "page/3/")
        self.assertEqual(first.entries, 1)
        self.assertIsNone(first.advertised)

    def test_terminal_page_and_short_final_batch(self):
        request = PageRequest(ROOT + "page/3/", context={"page_size": 10})
        page = miras.parse_listing(listing(current=3, pages=(1, 2)), request, ROOT)
        self.assertEqual(page.following, [])
        self.assertEqual(len(page.records), 1)

    def test_thumbnail_and_title_links_are_one_book_with_catalog_metadata(self):
        page = miras.parse_listing(listing(), PageRequest(ROOT), ROOT)
        self.assertEqual(page.records, [BOOK])
        metadata = page.record_context[BOOK]
        self.assertEqual(metadata["label_raw"], "Авыл кызы / آول قزى")
        self.assertEqual(metadata["language_raw"], "татарский")
        self.assertEqual(metadata["publication_place_raw"], "Казань")

    def test_all_languages_and_missing_labels_are_eligible(self):
        for language in ("татарский", "арабский", "татарский, арабский", None):
            with self.subTest(language=language):
                page = miras.parse_listing(listing([card(language=language)], pages=()), PageRequest(ROOT), ROOT)
                metadata, assets = miras.record(record(), BOOK)
                metadata["catalog_context"] = [page.record_context[BOOK]]
                metadata, assets = miras.resolve_record(None, metadata, assets)
                self.assertEqual(metadata["title"], "Авыл кызы / آول قزى")
                self.assertIsNone(assets[0]["unsupported_reason"])
                self.assertNotIn("language_selection", metadata)

    def test_wrong_page_missing_pagination_and_skipped_next_page_fail(self):
        for html in (listing(active=2), listing(pages=(3,)), listing(cards=[]),
                     listing().replace('class="navigation"', 'class="unknown"').replace(
                         f'<a href="{ROOT}page/2/">2</a><a href="{ROOT}page/3/">3</a>', "")):
            with self.subTest(html=html), self.assertRaises(ValueError):
                miras.parse_listing(html, PageRequest(ROOT), ROOT)
        with self.assertRaises(CatalogChanged):
            miras.parse_listing(listing(current=2, pages=(1, 3)),
                                PageRequest(ROOT + "page/2/", context={"page_size": 10}), ROOT)

    def test_catalog_rejects_filters_external_books_and_outside_routes(self):
        for url in (ROOT + "?lang=tatar", ROOT + "page/0/", "https://other.test/books/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                miras.page_number(url)
        with self.assertRaises(ValueError):
            miras.parse_listing(listing([card(BOOK.replace("miras.info", "other.test"))]), PageRequest(ROOT), ROOT)

    def test_viewer_direct_duplicate_multiple_and_external_pdf_references(self):
        extra = f'<a href="{PDF}">PDF</a><a href="{ARABIC_PDF}">Part 2</a>'
        extra += '<a href="https://other.test/other.pdf">External</a><a href="/book.epub">EPUB</a>'
        metadata, assets = miras.record(record(extra=extra, heading=True), BOOK)
        self.assertEqual(len(assets), 4)
        self.assertEqual([a["url"] for a in assets[:2]], [PDF, ARABIC_PDF])
        self.assertTrue(all(a["unsupported_reason"] is None for a in assets[:2]))
        self.assertEqual(assets[2]["unsupported_code"], "external_origin")
        self.assertEqual(assets[3]["unsupported_code"], "format_unsupported")
        self.assertNotIn("https://miras.info/footer.pdf", [a["url"] for a in assets])
        self.assertEqual(metadata["pages_raw"], "62")
        self.assertEqual(metadata["type_raw"], "Книга")

    def test_metadata_only_record_and_unknown_reader_remain_visible(self):
        metadata, assets = miras.record(record(pdf=None, heading=True), BOOK)
        self.assertEqual(assets, [])
        self.assertEqual(metadata["title"], "Авыл кызы / آول قزى")
        _, assets = miras.record(record(pdf=None, extra='<iframe src="/unknown-reader/"></iframe>'), BOOK)
        self.assertEqual(assets[0]["unsupported_code"], "format_unsupported")

    def test_sparse_records_and_same_origin_pdf_paths_are_supported(self):
        for body in ('<h2>Book title</h2>', '<a href="/documents/book.pdf">PDF</a>'):
            with self.subTest(body=body):
                metadata, assets = miras.record('<main>' + body + '</main>', BOOK)
                if assets:
                    self.assertEqual(assets[0]["url"], "https://miras.info/documents/book.pdf")
                    self.assertIsNone(assets[0]["unsupported_reason"])
                else:
                    self.assertEqual(metadata["title"], "Book title")

    def test_primary_content_precedes_outer_main_with_unrelated_heading_and_files(self):
        html = '<main><h1>Website heading</h1><a href="/footer.pdf">Footer</a>'
        html += '<div id="dle-content"><h2>Actual book</h2><a href="/original.pdf">PDF</a></div></main>'
        metadata, assets = miras.record(html, BOOK)
        self.assertEqual(metadata["title"], "Actual book")
        self.assertEqual([a["url"] for a in assets], ["https://miras.info/original.pdf"])

    def test_native_identity_survives_renamed_url_and_website_title_is_not_book_title(self):
        metadata, assets = miras.record(record(), ROOT + "889-renamed.html")
        self.assertEqual(miras.record_key(metadata), "book:889")
        self.assertNotIn("title", metadata)
        with self.assertRaises(ValueError):
            miras.resolve_record(None, metadata, assets)
        metadata["catalog_context"] = [{"label_raw": "Авыл кызы / آول قزى"}]
        metadata, _ = miras.resolve_record(None, metadata, assets)
        self.assertEqual(metadata["title"], "Авыл кызы / آول قزى")
        self.assertEqual(metadata["description"], "Г.Д. Авыл кызы. Казан, 1912.")

    def test_challenge_html_stops_instead_of_becoming_a_bad_record(self):
        for html in ('<title id="slg-title"></title>', '<title>SafeLine</title>',
                     '<title>Just a moment...</title><div id="challenge-running"></div>'):
            with self.subTest(html=html), self.assertRaises(SourceAccessError):
                miras.record(html, BOOK)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.settings = settings(self.directory)
        self.session = self.directory / "miras-session.json"
        self.export = {"format": "miras-session-v1", "origin": "https://miras.info", "user_agent": AGENT,
                       "cookies": [{"name": "session", "value": SECRET, "domain": "miras.info",
                                    "path": "/", "secure": True, "expirationDate": time.time() + 3600}]}
        self.session.write_text(json.dumps(self.export))
        self.resources = {ROOT: listing(pages=(2,)), ROOT + "page/2/": listing(
            [card(ARABIC, "Arabic book", "арабский")], current=2, pages=(1,)),
            BOOK: record(), ARABIC: record(ARABIC_PDF), PDF: pdf_bytes(2), ARABIC_PDF: pdf_bytes(3)}

    def run_command(self, command="run", *, resources=None, settings=None, recheck=False):
        transport = Transport(self.resources if resources is None else resources)
        with transport.install():
            result = core.run(settings or self.settings, "miras", command, session_file=self.session,
                              recheck=recheck, log=lambda _: None)
        return result, transport

    @property
    def manifest(self):
        return Manifest(self.directory / "miras", "miras")

    def test_full_two_page_run_downloads_all_languages_and_validates_actual_pdf_pages(self):
        report, _ = self.run_command()
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["records"], 2)
        self.assertEqual(report["downloaded"], 2)
        self.assertTrue(report["discovery_complete"])
        assets = list(self.manifest.data["assets"].values())
        self.assertEqual([a["results"][-1]["pages"] for a in assets], [2, 3])
        book = self.manifest.data["records"]["book:889"]["observations"][-1]["metadata"]
        self.assertEqual(book["pages_raw"], "62")
        self.assertEqual(book["catalog_context"][0]["language_raw"], "татарский")
        serialized = json.dumps(report) + self.manifest.path.read_text()
        self.assertNotIn(SECRET, serialized)
        self.assertNotIn(AGENT, serialized)
        report, transport = self.run_command("download", resources={})
        self.assertEqual(report["skipped"], 2)
        self.assertEqual(transport.calls, [])

    def test_page_cap_resumes_without_reinspecting_successful_records(self):
        report, _ = self.run_command("discover", settings=settings(self.directory, max_pages=1))
        self.assertFalse(report["discovery_complete"])
        self.assertEqual(report["records"], 1)
        report, transport = self.run_command("discover", settings=settings(self.directory, max_pages=1))
        self.assertTrue(report["discovery_complete"])
        self.assertNotIn(ROOT, transport.calls)
        self.assertNotIn(BOOK, transport.calls)

    def test_repeated_page_and_record_failure_leave_discovery_incomplete(self):
        self.resources[ROOT + "page/2/"] = listing(current=2, pages=(1,))
        report, _ = self.run_command("discover")
        self.assertFalse(report["discovery_complete"])
        self.assertIn("repeated", report["errors"][-1]["error"])
        self.resources[ROOT + "page/2/"] = listing([card(ARABIC)], current=2, pages=(1,))
        self.resources[ARABIC] = {"status": 404}
        report, _ = self.run_command("discover")
        self.assertFalse(report["discovery_complete"])
        self.assertEqual(self.manifest.data["discovery_scan"]["pending_records"], [ARABIC])
        self.resources[ARABIC] = record(ARABIC_PDF)
        report, transport = self.run_command("discover")
        self.assertTrue(report["discovery_complete"])
        self.assertEqual(transport.calls, [ARABIC])

    def test_expired_access_stops_after_one_request_and_retains_checkpoint(self):
        for rejection in ({"status": 468}, '<title id="slg-title"></title>'):
            with self.subTest(rejection=rejection):
                report, transport = self.run_command("run", resources={ROOT: rejection})
                self.assertEqual(transport.calls, [ROOT])
                self.assertEqual(report["errors"][0]["stage"], "access")
                self.assertFalse(report["discovery_complete"])
                self.assertEqual(report["network_retries"], 0)
                self.assertEqual(len(self.manifest.data["discovery_scan"]["frontier"]), 1)
        report, _ = self.run_command()
        self.assertTrue(report["discovery_complete"])

    def test_access_rejection_during_record_inspection_keeps_it_pending(self):
        self.resources[BOOK] = {"status": 403}
        report, transport = self.run_command("discover")
        self.assertEqual(report["errors"][0]["stage"], "access")
        self.assertEqual(transport.calls, [ROOT, BOOK])
        self.assertIn(BOOK, self.manifest.data["discovery_scan"]["pending_records"])

    def test_recheck_304_then_changed_pdf_preserves_history(self):
        self.resources[PDF] = {"body": pdf_bytes(), "headers": {"ETag": "original"}}
        self.run_command()
        self.resources[PDF] = {"status": 304, "mime": "text/html"}
        self.resources[ARABIC_PDF] = {"status": 304}
        report, transport = self.run_command("download", recheck=True)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["not_modified"], 2)
        self.assertEqual(transport.headers[0]["If-None-Match"], "original")
        self.resources[PDF] = pdf_bytes(4)
        report, _ = self.run_command("download", recheck=True)
        asset = next(a for a in self.manifest.data["assets"].values() if a["url"] == PDF)
        self.assertEqual(len(asset["results"]), 2)
        self.assertEqual(asset["results"][-1]["pages"], 4)
        self.assertTrue((self.manifest.directory / asset["results"][0]["path"]).is_file())

    def test_pdf_access_failure_stops_without_replacing_previous_success(self):
        self.run_command()
        self.resources[PDF] = {"body": "<html>Security check</html>", "mime": "text/html"}
        report, transport = self.run_command("download", recheck=True)
        self.assertEqual(transport.calls, [PDF])
        self.assertEqual(report["errors"][0]["stage"], "access")
        asset = next(a for a in self.manifest.data["assets"].values() if a["url"] == PDF)
        self.assertEqual(len(asset["results"]), 1)
        self.assertTrue((self.manifest.directory / asset["results"][0]["path"]).is_file())

    def test_download_access_failure_does_not_invalidate_finished_catalog_coverage(self):
        self.resources[PDF] = {"status": 468}
        report, _ = self.run_command()
        self.assertEqual(report["errors"][0]["stage"], "access")
        self.assertTrue(report["discovery_complete"])
        self.assertTrue(self.manifest.data["discovery"]["complete"])

    def test_mislabeled_challenge_stops_before_next_pdf_and_removes_partial_bytes(self):
        self.resources[PDF] = b'<html><title id="slg-title"></title><body>Security check</body></html>'
        report, transport = self.run_command()
        self.assertEqual(report["errors"][0]["stage"], "access")
        self.assertNotIn(ARABIC_PDF, transport.calls)
        self.assertTrue(report["discovery_complete"])
        self.assertEqual(self.manifest.status()["current_assets"]["pending"], 2)
        self.assertEqual(list((self.manifest.directory / ".tmp").glob("**/*.part")), [])

    def test_invalid_pdf_is_failed_without_publishing_and_can_be_retried(self):
        self.resources[PDF] = b"%PDF- invalid truncated document"
        report, _ = self.run_command()
        self.assertEqual(report["downloaded"], 1)
        self.assertEqual(self.manifest.status()["current_assets"]["failed"], 1)
        self.resources[PDF] = pdf_bytes()
        report, transport = self.run_command("download")
        self.assertEqual(report["errors"], [])
        self.assertEqual(transport.calls, [PDF])

    def test_file_and_byte_caps_preserve_pending_work(self):
        report, _ = self.run_command(settings=settings(self.directory, max_items=1))
        self.assertEqual(report["downloaded"], 1)
        self.assertIn("download item cap", report["stops"])
        report, _ = self.run_command("download", settings=settings(self.directory, max_download_bytes=1))
        self.assertIn("download byte cap", report["stops"])
        self.assertEqual(self.manifest.status()["current_assets"]["pending"], 1)
        self.assertEqual(list((self.manifest.directory / ".tmp").glob("**/*.part")), [])

    def test_missing_bad_or_expired_exports_are_actionable_without_logging_values(self):
        with self.assertRaisesRegex(ValueError, "session-file"):
            core.run(self.settings, "miras", "discover")
        for export in ({"format": SECRET}, {**self.export, "cookies": []},
                       {**self.export, "cookies": [{**self.export["cookies"][0], "expirationDate": 1}]},
                       {**self.export, "cookies": [{**self.export["cookies"][0], "domain": "other.test"}]}):
            self.session.write_text(json.dumps(export))
            report, transport = self.run_command("discover", resources={})
            self.assertEqual(report["errors"][0]["stage"], "access")
            self.assertEqual(transport.calls, [])
            self.assertNotIn(SECRET, json.dumps(report))
        self.session.write_text("invalid json " + SECRET)
        report, _ = self.run_command("discover", resources={})
        self.assertNotIn(SECRET, json.dumps(report))

    def test_status_needs_no_session_and_writes_nothing(self):
        self.run_command("discover")
        before = self.manifest.path.read_bytes()
        status = core.run(self.settings, "miras", "status")
        self.assertEqual(status["records"], 2)
        self.assertEqual(self.manifest.path.read_bytes(), before)

    def test_existing_probe_and_separate_artifacts_remain_compatible(self):
        self.run_command("discover")
        before = self.manifest.path.read_bytes()
        transport = Transport(self.resources)
        with transport.install():
            result = run_cookie_probe(self.settings, self.session, log=lambda _: None)
        self.assertTrue(result["success"])
        self.assertEqual(result["sample_result"]["pages"], 2)
        self.assertEqual(transport.calls[0], ROOT)
        self.assertTrue((self.directory / "miras/pilot/manifest.json").is_file())
        self.assertEqual(self.manifest.path.read_bytes(), before)


class CLITests(unittest.TestCase):
    def test_session_option_is_forwarded_for_network_commands(self):
        runner = CliRunner()
        for command in ("discover", "download", "run"):
            with self.subTest(command=command), patch("ingestion.cli.load_settings"), \
                    patch("ingestion.cli.restricted_settings"), patch("ingestion.cli.run", return_value={}) as run:
                result = runner.invoke(app, [command, "--source", "miras", "--session-file", "session.json"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertEqual(run.call_args.kwargs["session_file"], Path("session.json"))

    def test_miras_is_listed_and_other_sources_reject_session_files(self):
        runner = CliRunner()
        self.assertIn("miras", runner.invoke(app, ["sources"]).output)
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "only for Miras"):
            core.run(settings(directory), "tatkniga", "discover", session_file=Path("session.json"))

    def test_existing_yaml_archive_url_variants_are_accepted(self):
        import yaml

        with tempfile.TemporaryDirectory() as directory:
            for url in (ROOT, ROOT.rstrip("/")):
                config = yaml.safe_load(Path("ingestion.example.yaml").read_text())
                config["sources"]["miras"]["archive_url"] = url
                path = Path(directory) / "ingestion.yaml"
                path.write_text(yaml.safe_dump(config))
                self.assertEqual(load_settings(path, "miras").archive_url, ROOT)


if __name__ == "__main__":
    unittest.main()
