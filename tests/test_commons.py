import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ingestion import commons, core
from ingestion.config import Settings
from ingestion.network import Budget, HTTP, SourceAccessError
from ingestion.paging import CatalogChanged
from ingestion.state import Manifest


ROOT = commons.initial_request(commons.ARCHIVE_URL)


def member(page_id=100, title="File:Book.pdf", ns=6):
    return {"pageid": page_id, "title": title, "ns": ns}


def category(members=(), page_id=commons.ROOT_CATEGORY_ID, cursor=None):
    result = {"query": {"pages": [{"pageid": page_id, "ns": 14}], "categorymembers": list(members)}}
    if cursor is not None:
        result["continue"] = {"cmcontinue": cursor, "continue": "-||"}
    return result


def book(page_id=100, title="File:Book.pdf", mime="application/pdf", tracking="first"):
    return {"query": {"pages": [{"pageid": page_id, "ns": 6, "title": title, "imageinfo": [{
        "url": "https://upload.wikimedia.org/book.pdf?utm_source=" + tracking,
        "descriptionurl": "https://commons.wikimedia.org/wiki/" + title,
        "mime": mime, "size": 1000, "pagecount": 93, "sha1": "a" * 40,
        "timestamp": "2020-01-01T00:00:00Z", "extmetadata": {
            "ImageDescription": {"value": {"tt": "Китап", "en": "Book"}, "source": "commons-desc-page"},
            "LicenseShortName": {"value": "Public domain"}, "FutureField": {"value": "preserved"}}}]}]}}


class CommonsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.settings = Settings(self.directory, commons.ARCHIVE_URL, 1, 1, 1000000, 1000000,
                                 1, 30, 1, 1, .001, 1)

    @property
    def manifest(self):
        return Manifest(self.directory / "commons", "commons")

    def run_discovery(self, resources):
        calls = []

        def text(http, url, **kwargs):
            commons.parameters(url)
            calls.append(url)
            value = resources[url]
            if isinstance(value, Exception):
                raise value
            return json.dumps(value)

        with patch.object(HTTP, "text", autospec=True, side_effect=text):
            report = core.run(self.settings, "commons", "discover", log=lambda _: None)
        return report, calls

    def test_images_are_skipped_without_lookup_or_persisted_metadata(self):
        report, calls = self.run_discovery({ROOT.url: category([
            member(998, "File:Cover.jpg"), member(999, "File:Title page.png")])})
        self.assertTrue(report["discovery_complete"])
        self.assertEqual(calls, [ROOT.url])
        self.assertEqual(self.manifest.data["records"], {})
        self.assertEqual(self.manifest.data["assets"], {})
        self.assertNotIn("Cover.jpg", self.manifest.path.read_text())
        self.assertNotIn("Title page.png", self.manifest.path.read_text())
        self.assertFalse((self.manifest.directory / "files").exists())

    def test_shared_categories_cycles_and_duplicate_files_are_deduplicated(self):
        child = commons.category_request(200)
        resources = {ROOT.url: category([member(), member(200, "Category:Child", 14)]),
                     commons.file_request(100): book(),
                     child.url: category([member(), member(commons.ROOT_CATEGORY_ID, "Category:Root", 14)], 200)}
        report, _ = self.run_discovery(resources)
        self.assertFalse(report["discovery_complete"])
        report, calls = self.run_discovery(resources)
        self.assertTrue(report["discovery_complete"])
        self.assertEqual(calls, [child.url])
        self.assertEqual(len(self.manifest.data["records"]), 1)
        self.assertEqual(len(self.manifest.data["records"]["file:100"]["observations"]), 1)

    def test_continuation_resumes_after_page_cap_without_reloading_records(self):
        cursor = {"cmcontinue": "next", "continue": "-||"}
        next_page = commons.category_request(commons.ROOT_CATEGORY_ID, cursor)
        resources = {ROOT.url: category([member()], cursor="next"), commons.file_request(100): book(),
                     next_page.url: category([member(101, "File:Other.pdf")]), commons.file_request(101): book(101, "File:Other.pdf")}
        report, _ = self.run_discovery(resources)
        self.assertFalse(report["discovery_complete"])
        report, calls = self.run_discovery(resources)
        self.assertTrue(report["discovery_complete"])
        self.assertEqual(calls, [next_page.url, commons.file_request(101)])

    def test_empty_batches_can_advance_and_empty_categories_can_finish(self):
        first = commons.parse_listing(json.dumps(category(cursor="a")), ROOT, commons.ARCHIVE_URL)
        second = commons.parse_listing(json.dumps(category(cursor="b")), first.following[0], commons.ARCHIVE_URL)
        last = commons.parse_listing(json.dumps(category()), second.following[0], commons.ARCHIVE_URL)
        self.assertEqual(last.following, [])
        self.assertFalse(first.detect_repeats)
        report, _ = self.run_discovery({ROOT.url: category()})
        self.assertTrue(report["discovery_complete"])

    def test_continuation_can_omit_properties_already_completed_by_mediawiki(self):
        first = commons.parse_listing(json.dumps(category(cursor="a")), ROOT, commons.ARCHIVE_URL)
        response = category([member()])
        del response["query"]["pages"]
        second = commons.parse_listing(json.dumps(response), first.following[0], commons.ARCHIVE_URL)
        self.assertEqual(second.records, [commons.file_request(100)])
        with self.assertRaises(ValueError):
            commons.parse_listing(json.dumps(response), ROOT, commons.ARCHIVE_URL)

    def test_cyclic_and_invalidated_cursors_restart_without_erasing_records(self):
        first = commons.parse_listing(json.dumps(category(cursor="a")), ROOT, commons.ARCHIVE_URL)
        second = commons.parse_listing(json.dumps(category(cursor="b")), first.following[0], commons.ARCHIVE_URL)
        with self.assertRaises(CatalogChanged):
            commons.parse_listing(json.dumps(category(cursor="a")), second.following[0], commons.ARCHIVE_URL)
        report, _ = self.run_discovery({ROOT.url: {"error": {"code": "badcontinue"}}})
        self.assertFalse(report["discovery_complete"])
        self.assertTrue(self.manifest.data["discovery_scan"]["restart_required"])
        report, _ = self.run_discovery({ROOT.url: category()})
        self.assertTrue(report["discovery_complete"])

    def test_api_errors_missing_categories_and_malformed_responses_do_not_complete(self):
        missing = category(); missing["query"]["pages"][0]["missing"] = True
        for response in ({"error": {"code": "maxlag"}}, {"query": {}}, missing, []):
            with self.subTest(response=response):
                report, _ = self.run_discovery({ROOT.url: response})
                self.assertFalse(report["discovery_complete"])
                self.assertTrue(report["errors"])

    def test_metadata_preserves_multilingual_and_unknown_fields_but_cleans_tracking(self):
        metadata, assets = commons.record(json.dumps(book()), commons.file_request(100))
        self.assertEqual(commons.record_key(metadata), "file:100")
        info = metadata["upstream"]["imageinfo"][0]
        self.assertEqual(info["extmetadata"]["FutureField"]["value"], "preserved")
        self.assertEqual(info["extmetadata"]["ImageDescription"]["value"]["tt"], "Китап")
        self.assertEqual(assets[0]["url"], "https://upload.wikimedia.org/book.pdf")
        self.assertEqual(assets[0]["source_page_count"], 93)
        self.assertNotIn("expected_pages", metadata)
        self.assertNotIn("sha256", assets[0])

    def test_unchanged_rescan_and_tracking_changes_do_not_duplicate_observations(self):
        resources = {ROOT.url: category([member()]), commons.file_request(100): book()}
        self.run_discovery(resources)
        resources[commons.file_request(100)] = book(tracking="changed")
        report, _ = self.run_discovery(resources)
        self.assertEqual(report["observations"], 0)
        resources[commons.file_request(100)]["query"]["pages"][0]["imageinfo"][0]["timestamp"] = "2021-01-01T00:00:00Z"
        report, _ = self.run_discovery(resources)
        self.assertEqual(report["observations"], 1)
        self.assertEqual(len(self.manifest.data["assets"]), 1)

    def test_renamed_file_keeps_native_record_and_representation_identity(self):
        resources = {ROOT.url: category([member()]), commons.file_request(100): book()}
        self.run_discovery(resources)
        asset_id = next(iter(self.manifest.data["assets"]))
        resources[commons.file_request(100)] = book(title="File:Renamed.pdf")
        self.run_discovery(resources)
        self.assertEqual(list(self.manifest.data["records"]), ["file:100"])
        self.assertEqual(list(self.manifest.data["assets"]), [asset_id])

    def test_missing_and_unavailable_originals_remain_metadata_only(self):
        for page in ({"pageid": 100, "missing": True}, {"pageid": 100, "ns": 6, "title": "File:Book.pdf"}):
            with self.subTest(page=page):
                report, _ = self.run_discovery({ROOT.url: category([member()]),
                    commons.file_request(100): {"query": {"pages": [page]}}})
                self.assertTrue(report["discovery_complete"])
                self.assertEqual(self.manifest.status()["records_without_attachments"], 1)

    def test_inconsistent_mime_retains_pending_work_without_creating_an_image_record(self):
        report, _ = self.run_discovery({ROOT.url: category([member()]), commons.file_request(100): book(mime="image/jpeg")})
        self.assertFalse(report["discovery_complete"])
        self.assertEqual(self.manifest.data["records"], {})
        self.assertEqual(len(self.manifest.data["discovery_scan"]["pending_records"]), 1)

    def test_download_and_run_are_rejected_before_requests_or_writes(self):
        for command in ("download", "run"):
            with self.subTest(command=command), patch.object(HTTP, "request") as request:
                with self.assertRaisesRegex(ValueError, "supports only"):
                    core.run(self.settings, "commons", command)
                request.assert_not_called()
                self.assertFalse((self.directory / "commons").exists())

    def test_api_guard_prevents_original_requests_and_redirects(self):
        http = HTTP(self.settings, Budget(self.settings), {"requests": 0})
        self.addCleanup(http.close)
        commons.prepare_http(http, None)
        with patch.object(http.session, "get") as get:
            for url in ("https://upload.wikimedia.org/book.pdf", commons.ARCHIVE_URL,
                        commons.API_URL + "?action=edit"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    http.get(url)
            get.assert_not_called()
        import requests
        response = requests.Response(); response.url = commons.API_URL + "?action=query"
        response.raw = io.BytesIO()
        response.status_code = 302; response.headers["Location"] = "https://upload.wikimedia.org/book.pdf"
        with self.assertRaises(SourceAccessError):
            http.session.hooks["response"][0](response)


if __name__ == "__main__":
    unittest.main()
