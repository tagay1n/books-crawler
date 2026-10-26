import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import yaml
from typer.testing import CliRunner

from ingestion import tatarica
from ingestion.cli import app
from ingestion.config import load_settings
from ingestion.core import run
from ingestion.network import BudgetStop
from ingestion.paging import PageRequest
from ingestion.state import Manifest
from test_ingestion import PDF, ROOT, Response


CATALOG = tatarica.ARCHIVE_URL
ENDPOINT = "https://tatarica.org/chapter/get_more_articles"


def url(number):
    prefix = "biblioteka-tatarika" if number % 2 else "tatarika-kitaphanse"
    return f"https://tatarica.org/tat/razdely/{prefix}/books/book-{number}"


def cards(numbers):
    return ''.join(f'<div class="tat-grid-block"><a href="{url(n)}">Китап {n}</a></div>' for n in numbers)


def catalog(numbers=(1, 2), count=11):
    return (f'<script>var CCM_CID = 27043; var count = \'{count}\';</script>'
            f'<div id="articles">{cards(numbers)}</div>'
            '<aside><div class="tat-grid-block"><a href="/tat/elsewhere">Unrelated</a></div></aside>')


def book(number, files=None, title=None):
    files = [(51, "Татарча басма"), (52, "Рус телендәге басма")] if files is None else files
    paragraphs = ''.join(f'<p>{label}: <a href="https://tatarica.org/download_file/view/{file_id}">{label}</a>. Казан, 2021.</p>'
                         for file_id, label in files)
    return (f'<script>var CCM_CID = {number};</script>'
            f'<h1 class="inner-page-top__title">{title or f"Китап {number}"}</h1>'
            '<div class="inner-page-content"><div class="copy-content">'
            f'<p>Чыганак тасвирламасы</p>{paragraphs}</div></div>'
            '<aside><a href="/download_file/view/9999">Other book</a></aside>')


class TataricaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.settings = replace(load_settings(ROOT / "ingestion.example.yaml", "tatarica"),
                                artifacts_root=self.directory, disk_reserve_bytes=1, pacing_seconds=0.001)

    def manifest(self):
        return Manifest(self.directory / "tatarica", "tatarica")

    def execute(self, *, settings=None, command="discover", count=11, changed_count=None,
                batch=None, missing=None, budget_url=None):
        calls = {"get": [], "post": []}

        def get(target, **kwargs):
            calls["get"].append((target, kwargs))
            if target == budget_url:
                raise BudgetStop("soft deadline")
            if target == CATALOG:
                current = changed_count if changed_count is not None and len([x for x, _ in calls["get"] if x == CATALOG]) > 1 else count
                return Response(target, catalog(count=current))
            if target == missing:
                return Response(target, status=404)
            if "/download_file/view/" in target:
                return Response("https://tatarica.org/application/files/actual.pdf", PDF)
            number = int(target.rsplit("-", 1)[-1])
            return Response(target, book(number))

        def post(target, **kwargs):
            calls["post"].append((target, kwargs))
            offset = int(kwargs["data"]["offset"])
            numbers = list(range(offset + 1, min(offset + 10, count + 1)))
            return Response(target, cards(batch if batch is not None else numbers))

        with mock.patch("requests.Session.get", side_effect=get), mock.patch("requests.Session.post", side_effect=post), mock.patch("time.sleep"):
            summary = run(settings or self.settings, "tatarica", command, log=lambda _message: None)
        return summary, calls

    def test_initial_cards_and_native_pagination(self):
        page = tatarica.parse_listing(catalog(), PageRequest(CATALOG), CATALOG)
        self.assertEqual([url(1), url(2)], page.records)
        self.assertEqual(11, page.advertised)
        request = page.following[0]
        self.assertEqual("POST", request.method)
        self.assertEqual({"cID": 27043, "offset": 2, "limit": 9}, request.data)
        second = tatarica.parse_listing(cards(range(3, 12)), request, CATALOG)
        self.assertEqual(9, second.entries)
        self.assertEqual([], second.following)

    def test_invalid_catalog_missing_count_short_batch_and_outside_scope(self):
        for html in ('<html>Login</html>', '<div id="articles"></div>', catalog(numbers=(), count=11)):
            with self.subTest(html=html), self.assertRaises(ValueError):
                tatarica.parse_listing(html, PageRequest(CATALOG), CATALOG)
        request = tatarica.parse_listing(catalog(), PageRequest(CATALOG), CATALOG).following[0]
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            tatarica.parse_listing(cards([3]), request, CATALOG)
        with self.assertRaisesRegex(ValueError, "Unexpected record"):
            tatarica.parse_listing(catalog().replace(url(1), "https://example.org/file"), PageRequest(CATALOG), CATALOG)

    def test_all_editions_and_bibliographic_context_without_language_placeholder(self):
        metadata, assets = tatarica.record(book(10), url(10))
        self.assertEqual("10", metadata["cms_page_id"])
        self.assertEqual("cms:10", tatarica.record_key(metadata))
        self.assertEqual(2, len(assets))
        self.assertEqual(["file:51", "file:52"], [a["source_asset_key"] for a in assets])
        self.assertTrue(all(a["extension"] == "" for a in assets))
        self.assertIn("Рус телендәге", assets[1]["context"])
        self.assertEqual(2, len(metadata["bibliography_raw"]))
        self.assertNotIn("language_claim", metadata)
        self.assertNotIn("date_raw", metadata)
        self.assertNotIn("9999", json.dumps(assets))

    def test_record_without_files_and_url_identity_fallback(self):
        html = book(1, files=[]).replace('<script>var CCM_CID = 1;</script>', '')
        metadata, assets = tatarica.record(html, url(1))
        self.assertEqual([], assets)
        self.assertEqual(url(1), tatarica.record_key(metadata))
        with self.assertRaisesRegex(ValueError, "structure"):
            tatarica.record('<html>Login</html>', url(1))

    def test_native_identity_survives_record_and_download_route_aliases(self):
        manifest = self.manifest()
        metadata, assets = tatarica.record(book(1), url(1))
        manifest.observe(metadata, assets, record_key=tatarica.record_key(metadata))
        ids = set(manifest.data["assets"])
        changed_url = url(1) + "-renamed"
        html = book(1, title="Changed title").replace("/view/51", "/view/51/1234")
        metadata, assets = tatarica.record(html, changed_url)
        manifest.observe(metadata, assets, record_key=tatarica.record_key(metadata))
        self.assertEqual(["cms:1"], list(manifest.data["records"]))
        self.assertEqual(ids, set(manifest.data["assets"]))
        self.assertEqual([url(1), changed_url], manifest.data["records"]["cms:1"]["origin_urls"])
        self.assertEqual(2, len(manifest.data["records"]["cms:1"]["observations"]))

    def test_resume_listing_cap_then_verify_count_without_restarting(self):
        settings = replace(self.settings, max_pages=1)
        first, first_calls = self.execute(settings=settings)
        self.assertFalse(first["discovery_complete"])
        self.assertEqual(2, first["coverage"]["record_urls_inspected"])
        self.assertEqual([], first_calls["post"])
        scan_id = first["coverage"]["scan_id"]
        second, second_calls = self.execute(settings=settings)
        self.assertNotIn(CATALOG, [target for target, _ in second_calls["get"]])
        self.assertEqual(1, len(second_calls["post"]))
        self.assertEqual(11, second["coverage"]["record_urls_inspected"])
        self.assertFalse(second["discovery_complete"])
        third, third_calls = self.execute(settings=settings)
        self.assertTrue(third["discovery_complete"])
        self.assertEqual(scan_id, third["coverage"]["scan_id"])
        self.assertEqual([CATALOG], [target for target, _ in third_calls["get"]])
        self.assertEqual([], third_calls["post"])
        self.assertEqual(11, len(self.manifest().data["records"]))
        self.assertTrue(all(len(r["observations"]) == 1 for r in self.manifest().data["records"].values()))

    def test_interrupted_record_stays_pending_and_resume_does_not_repeat_listing(self):
        first, _ = self.execute(budget_url=url(2))
        self.assertFalse(first["discovery_complete"])
        self.assertEqual([url(2)], self.manifest().data["discovery_scan"]["pending_records"])
        second, calls = self.execute()
        self.assertTrue(second["discovery_complete"])
        self.assertEqual(url(2), calls["get"][0][0])
        self.assertEqual(1, len(self.manifest().data["records"]["cms:1"]["observations"]))

    def test_failed_record_retries_on_next_discovery(self):
        first, _ = self.execute(missing=url(1))
        self.assertFalse(first["discovery_complete"])
        self.assertEqual(1, first["coverage"]["remaining_record_urls"])
        self.assertTrue(first["errors"])
        second, calls = self.execute()
        self.assertTrue(second["discovery_complete"])
        self.assertEqual(url(1), calls["get"][0][0])
        self.assertEqual({}, self.manifest().data["discovery_errors"])

    def test_early_empty_batch_is_not_complete_and_can_resume(self):
        first, _ = self.execute(batch=[])
        self.assertFalse(first["discovery_complete"])
        self.assertIn("Incomplete", first["errors"][0]["error"])
        second, calls = self.execute()
        self.assertTrue(second["discovery_complete"])
        self.assertEqual(1, len(calls["post"]))

    def test_repeated_batch_is_detected(self):
        summary, _ = self.execute(count=20, batch=list(range(3, 12)))
        self.assertFalse(summary["discovery_complete"])
        self.assertIn("repeated pagination batch", summary["errors"][0]["error"])
        self.assertEqual(11, summary["coverage"]["record_urls_inspected"])

    def test_changed_catalog_count_requires_new_scan(self):
        first, _ = self.execute(changed_count=12)
        self.assertFalse(first["discovery_complete"])
        self.assertTrue(first["coverage"]["restart_required"])
        second, _ = self.execute()
        self.assertNotEqual(first["coverage"]["scan_id"], second["coverage"]["scan_id"])
        self.assertTrue(second["discovery_complete"])

    def test_extensionless_editions_reuse_shared_downloader_and_file_store(self):
        manifest = self.manifest()
        metadata, assets = tatarica.record(book(1), url(1))
        manifest.observe(metadata, assets, record_key=tatarica.record_key(metadata))
        summary, _ = self.execute(command="download")
        self.assertEqual(2, summary["downloaded"])
        self.assertEqual(1, summary["reused_blobs"])
        self.assertEqual(1, len(list((self.directory / "tatarica" / "files").iterdir())))
        for asset in self.manifest().data["assets"].values():
            result = asset["results"][0]
            self.assertEqual("application/pdf", result["mime"])
            self.assertTrue(result["path"].endswith(".pdf"))

    def test_selected_source_configuration_and_read_only_cli_status(self):
        data = yaml.safe_load((ROOT / "ingestion.example.yaml").read_text())
        del data["sources"]["magarif"]
        data["artifacts_root"] = str(self.directory / "not-created")
        path = self.directory / "config.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        self.assertEqual(CATALOG, load_settings(path, "tatarica").archive_url)
        with self.assertRaisesRegex(ValueError, "sources.magarif"):
            load_settings(path, "magarif")
        with mock.patch("requests.Session.get", side_effect=AssertionError("unexpected network")):
            result = CliRunner().invoke(app, ["--config", str(path), "status", "--source", "tatarica"])
        self.assertEqual(0, result.exit_code, result.output)
        self.assertFalse((self.directory / "not-created").exists())


if __name__ == "__main__":
    unittest.main()
