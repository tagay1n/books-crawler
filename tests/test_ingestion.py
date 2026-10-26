import hashlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import requests
import yaml
from typer.testing import CliRunner

from ingestion import magarif
from ingestion.cli import app
from ingestion.config import load_settings
from ingestion.core import HTTP, restricted_settings, run
from ingestion.network import BudgetStop
from ingestion.state import Manifest, atomic_json, source_lock


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = "https://magarif-uku.ru/documents"
RECORD = ARCHIVE + "/issue"
PDF_URL = "https://magarif-uku.ru/files/issue.pdf"
PDF = b"%PDF-1.7\nlocal test original\n%%EOF\n"


def listing(records, pages=()):
    return ('<h1 class="page__title">Архив</h1><ul class="news-list__list">'
            + ''.join(f'<a class="news-list__link" href="{url}">Issue</a>' for url in records)
            + '</ul>' + ''.join(f'<a class="pagination__link" href="{url}">Page</a>' for url in pages))


def detail(title="Мәгариф. Татар теле", urls=(PDF_URL,), description="Татарча текст"):
    return (f'<section><h1 class="single-page__title">{title}</h1>'
            '<time>04 сентябрь 2026</time>'
            f'<div class="single-page__content"><p>{description}</p></div>'
            '<ul class="ul_hidden-default-styles">'
            + ''.join(f'<li><a href="{url}">Original</a></li>' for url in urls)
            + '</ul></section><aside><a href="/banner.pdf">Banner</a></aside>'
            '<footer><a href="https://tatmedia.ru/policy.pdf">Policy</a></footer>')


class Raw(io.BytesIO):
    def read(self, size=-1, decode_content=False):
        return super().read(size)


class Interrupted(Raw):
    def __init__(self):
        super().__init__(PDF)
        self.first = True

    def read(self, size=-1, decode_content=False):
        if self.first:
            self.first = False
            return super().read(8)
        raise requests.ConnectionError("interrupted body")


class Response:
    def __init__(self, url, body=b"", status=200, headers=None, raw=None):
        if isinstance(body, str):
            body = body.encode()
        self.url, self.status_code = url, status
        self.headers = headers if headers is not None else {"Content-Type": "application/pdf", "Content-Length": str(len(body))}
        self.raw = raw if raw is not None else Raw(body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.settings = replace(load_settings(ROOT / "ingestion.example.yaml"), artifacts_root=self.directory,
                                pacing_seconds=0.001, disk_reserve_bytes=1)
        self.logs = []

    def manifest(self):
        return Manifest(self.directory / "magarif")

    def seed(self, urls=(PDF_URL,), title="Issue", record_url=RECORD):
        manifest = self.manifest()
        metadata, assets = magarif.record(detail(title=title, urls=urls), record_url)
        manifest.observe(metadata, assets)
        return manifest

    def execute(self, responses, command="download", recheck=False, settings=None):
        def get(url, **kwargs):
            response = responses[url]
            return response.pop(0) if isinstance(response, list) else response()
        with mock.patch("requests.Session.get", side_effect=get) as request, mock.patch("time.sleep"):
            result = run(settings or self.settings, "magarif", command, recheck=recheck, log=self.logs.append)
        return result, request

    def test_parser_ignores_banner_and_footer_and_retains_unsupported(self):
        metadata, assets = magarif.record(detail(urls=("/files/issue.pdf#page=2", "/files/package.zip")), RECORD)
        self.assertEqual([PDF_URL, "https://magarif-uku.ru/files/package.zip"], [a["url"] for a in assets])
        self.assertIsNotNone(assets[1]["unsupported_reason"])
        self.assertEqual("04 сентябрь 2026", metadata["date_raw"])
        self.assertNotIn("language_claim", metadata)
        self.assertEqual(2, len(metadata["attachments"]))

    def test_parser_supports_body_documents_and_no_attachment_record(self):
        html = detail(urls=()).replace("Татарча текст", '<a href="/files/lesson.pptx">Скачать</a>')
        _, assets = magarif.record(html, RECORD)
        self.assertEqual(".pptx", assets[0]["extension"])
        _, empty = magarif.record(detail(urls=()), RECORD)
        self.assertEqual([], empty)
        with self.assertRaisesRegex(ValueError, "structure"):
            magarif.record("<html>Login</html>", RECORD)

    def test_listing_restricts_scope_and_deduplicates(self):
        html = listing([RECORD, RECORD + "#top", "https://example.org/documents/a"],
                       [ARCHIVE + "/page/2", ARCHIVE, "https://example.org/documents/page/3"])
        records, pages = magarif.listing(html, ARCHIVE, ARCHIVE)
        self.assertEqual([RECORD], records)
        self.assertEqual([ARCHIVE + "/page/2", ARCHIVE], pages)
        with self.assertRaisesRegex(ValueError, "structure"):
            magarif.listing("<html>Login</html>", ARCHIVE, ARCHIVE)

    def test_metadata_history_includes_reversions_and_attachment_changes(self):
        self.seed(title="First")
        self.seed(title="First")
        self.assertEqual(1, len(self.manifest().data["records"][RECORD]["observations"]))
        self.seed(title="Second")
        self.seed(title="First")
        manifest = self.seed(urls=(PDF_URL, PDF_URL.replace("issue", "other")), title="First")
        self.assertEqual(4, len(manifest.data["records"][RECORD]["observations"]))
        self.seed(urls=(), title="First")
        self.assertTrue(all(not asset["current"] for asset in self.manifest().data["assets"].values()))

    def test_manifest_rejects_unknown_version_and_atomic_save_preserves_previous(self):
        path = self.directory / "magarif" / "manifest.json"
        atomic_json(path, {"schema_version": 99})
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self.manifest()
        before = path.read_bytes()
        with mock.patch("ingestion.state.os.replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                atomic_json(path, {"new": True})
        self.assertEqual(before, path.read_bytes())
        self.assertEqual([], list(path.parent.glob(".manifest-*.tmp")))

    def test_parser_version_change_adds_observation_without_rewriting_history(self):
        manifest = self.seed()
        metadata, assets = magarif.record(detail(title="Issue"), RECORD)
        first = manifest.data["records"][RECORD]["observations"][0].copy()
        manifest.observe(metadata, assets, parser_version=2)
        observations = manifest.data["records"][RECORD]["observations"]
        self.assertEqual(2, len(observations))
        self.assertEqual(first, observations[0])
        self.assertEqual(2, observations[1]["parser_version"])

    def test_source_lock_rejects_overlap_and_releases(self):
        directory = self.directory / "magarif"
        with source_lock(directory):
            with self.assertRaisesRegex(RuntimeError, "already writing"):
                with source_lock(directory):
                    self.fail("Unexpected second writer")
        with source_lock(directory):
            pass

    def test_download_hashes_and_repeat_skips_without_network(self):
        self.seed()
        summary, _ = self.execute({PDF_URL: lambda: Response(PDF_URL, PDF)})
        self.assertEqual(1, summary["downloaded"])
        self.assertEqual(len(PDF), summary["attempted_download_bytes"])
        result = next(iter(self.manifest().data["assets"].values()))["results"][0]
        self.assertEqual(hashlib.sha256(PDF).hexdigest(), result["sha256"])
        self.assertEqual(hashlib.md5(PDF).hexdigest(), result["md5"])
        self.assertEqual(PDF, (self.directory / "magarif" / result["path"]).read_bytes())
        again, request = self.execute({})
        request.assert_not_called()
        self.assertEqual(1, again["skipped"])

    def test_recheck_304_preserves_acquisition_observation(self):
        self.seed(title="First")
        headers = {"Content-Type": "application/pdf", "ETag": '"v1"', "Content-Length": str(len(PDF))}
        self.execute({PDF_URL: lambda: Response(PDF_URL, PDF, headers=headers)})
        before = next(iter(self.manifest().data["assets"].values()))["results"]
        self.seed(title="New metadata")
        summary, request = self.execute({PDF_URL: lambda: Response(PDF_URL, status=304)}, recheck=True)
        self.assertEqual(1, summary["not_modified"])
        self.assertEqual('"v1"', request.call_args.kwargs["headers"]["If-None-Match"])
        self.assertEqual(before, next(iter(self.manifest().data["assets"].values()))["results"])

    def test_new_bytes_preserve_old_file_and_result(self):
        self.seed()
        self.execute({PDF_URL: lambda: Response(PDF_URL, PDF)})
        changed = PDF + b"new version"
        self.execute({PDF_URL: lambda: Response(PDF_URL, changed)}, recheck=True)
        results = next(iter(self.manifest().data["assets"].values()))["results"]
        self.assertEqual(2, len(results))
        self.assertNotEqual(results[0]["sha256"], results[1]["sha256"])
        self.assertTrue(all((self.directory / "magarif" / r["path"]).exists() for r in results))

    def test_identical_bytes_keep_result_but_update_recheck_validator(self):
        self.seed()
        self.execute({PDF_URL: lambda: Response(PDF_URL, PDF, headers={"ETag": '"v1"'})})
        original = next(iter(self.manifest().data["assets"].values()))["results"]
        summary, _ = self.execute({PDF_URL: lambda: Response(PDF_URL, PDF, headers={"ETag": '"v2"'})}, recheck=True)
        self.assertEqual(1, summary["unchanged_downloads"])
        self.assertEqual(original, next(iter(self.manifest().data["assets"].values()))["results"])
        _, request = self.execute({PDF_URL: lambda: Response(PDF_URL, status=304)}, recheck=True)
        self.assertEqual('"v2"', request.call_args.kwargs["headers"]["If-None-Match"])

    def test_missing_or_corrupt_local_file_is_reacquired_without_conditions(self):
        self.seed()
        self.execute({PDF_URL: lambda: Response(PDF_URL, PDF, headers={"ETag": '"v1"'})})
        result = next(iter(self.manifest().data["assets"].values()))["results"][0]
        path = self.directory / "magarif" / result["path"]
        for missing in (True, False):
            if missing:
                path.unlink()
            else:
                path.write_bytes(b"corrupt")
            summary, request = self.execute({PDF_URL: lambda: Response(PDF_URL, PDF)})
            self.assertEqual({}, request.call_args.kwargs["headers"])
            self.assertEqual(PDF, path.read_bytes())
            self.assertFalse(summary["errors"])

    def test_discovery_cycles_and_identical_bytes_preserve_both_sources(self):
        second, empty = ARCHIVE + "/second", ARCHIVE + "/notice"
        mapping = {
            ARCHIVE: lambda: Response(ARCHIVE, listing([RECORD, empty], [ARCHIVE + "/page/2"])),
            ARCHIVE + "/page/2": lambda: Response(ARCHIVE, listing([RECORD, second], [ARCHIVE])),
            RECORD: lambda: Response(RECORD, detail()),
            empty: lambda: Response(empty, detail(urls=())),
            second: lambda: Response(second, detail(title="Another record")),
            PDF_URL: lambda: Response(PDF_URL, PDF),
        }
        summary, _ = self.execute(mapping, command="run")
        self.assertEqual(2, summary["pages"])
        self.assertEqual(3, summary["records"])
        self.assertTrue(summary["discovery_complete"])
        self.assertEqual(2, summary["downloaded"])
        self.assertEqual(1, summary["reused_blobs"])
        self.assertEqual(1, len(list((self.directory / "magarif" / "files").iterdir())))
        self.assertEqual(1, self.manifest().status()["records_without_attachments"])

    def test_partial_scan_keeps_existing_work_and_can_still_acquire(self):
        self.seed()
        summary, _ = self.execute({ARCHIVE: lambda: Response(ARCHIVE, "<html>Login</html>"),
                                   PDF_URL: lambda: Response(PDF_URL, PDF)}, command="run")
        self.assertFalse(summary["discovery_complete"])
        self.assertEqual(1, summary["downloaded"])
        self.assertEqual(1, len(summary["errors"]))
        self.assertIn(ARCHIVE, self.manifest().data["discovery_errors"])

    def test_page_cap_does_not_prevent_queued_downloads(self):
        self.seed()
        summary, _ = self.execute({ARCHIVE: lambda: Response(ARCHIVE, listing([], [ARCHIVE + "/page/2"])),
                                   PDF_URL: lambda: Response(PDF_URL, PDF)}, command="run",
                                  settings=replace(self.settings, max_pages=1))
        self.assertIn("discovery page cap", summary["stops"])
        self.assertEqual(1, summary["downloaded"])

    def test_item_cap_leaves_other_assets_pending(self):
        other = PDF_URL.replace("issue", "other")
        self.seed(urls=(PDF_URL, other))
        summary, _ = self.execute({PDF_URL: lambda: Response(PDF_URL, PDF)}, settings=replace(self.settings, max_items=1))
        self.assertEqual(1, summary["started_items"])
        self.assertIn("download item cap", summary["stops"])
        self.assertEqual(1, summary["backlog"]["current_assets"]["pending"])

    def test_known_size_checks_prevent_body_reads(self):
        self.seed()
        response = Response(PDF_URL, PDF)
        with mock.patch.object(response.raw, "read", wraps=response.raw.read) as read:
            summary, _ = self.execute({PDF_URL: [response]}, settings=replace(self.settings, max_file_bytes=5))
            read.assert_not_called()
        self.assertTrue(summary["errors"])
        self.assertEqual(0, summary["attempted_download_bytes"])
        response = Response(PDF_URL, PDF)
        summary, _ = self.execute({PDF_URL: [response]}, settings=replace(self.settings, max_download_bytes=5))
        self.assertFalse(summary["errors"])
        self.assertIn("download byte cap", summary["stops"])

    def test_unknown_length_stream_is_bounded_and_partial_removed(self):
        self.seed()
        summary, _ = self.execute({PDF_URL: lambda: Response(PDF_URL, PDF, headers={})},
                                  settings=replace(self.settings, max_download_bytes=8))
        self.assertEqual(8, summary["attempted_download_bytes"])
        self.assertIn("download byte cap", summary["stops"])
        self.assertEqual("pending", next(iter(self.manifest().data["assets"].values()))["status"])
        self.assertEqual([], list((self.directory / "magarif" / ".tmp").glob("run-*")))

    def test_retry_counts_partial_bytes_and_keeps_other_run_temporary_files(self):
        self.seed()
        old = self.directory / "magarif" / ".tmp" / "old-run" / "keep.part"
        old.parent.mkdir(parents=True)
        old.write_bytes(b"other run")
        summary, _ = self.execute({PDF_URL: [Response(PDF_URL, headers={}, raw=Interrupted()), Response(PDF_URL, PDF)]})
        self.assertEqual(8 + len(PDF), summary["attempted_download_bytes"])
        self.assertEqual(1, summary["network_retries"])
        self.assertEqual(1, summary["started_items"])
        self.assertTrue(old.exists())

    def test_server_retry_and_independent_item_failure(self):
        other = PDF_URL.replace("issue", "other")
        self.seed(urls=(PDF_URL, other))
        summary, request = self.execute({PDF_URL: [Response(PDF_URL, status=503), Response(PDF_URL, PDF)],
                                        other: lambda: Response(other, status=404)})
        self.assertEqual(1, summary["network_retries"])
        self.assertEqual(1, summary["downloaded"])
        self.assertEqual(1, len(summary["errors"]))
        self.assertEqual(3, request.call_count)

    def test_deadline_keeps_work_and_records_incomplete_discovery(self):
        self.seed()
        with mock.patch("ingestion.network.Budget.check", side_effect=BudgetStop("soft deadline")):
            summary, request = self.execute({}, command="run")
        request.assert_not_called()
        self.assertFalse(summary["discovery_complete"])
        self.assertEqual(["soft deadline"], summary["stops"])
        self.assertEqual(1, self.manifest().status()["current_assets"]["pending"])
        self.assertFalse(summary["errors"])

    def test_error_html_empty_and_bad_signatures_do_not_publish_files(self):
        for body, headers in ((b"<html>Login</html>", {"Content-Type": "text/html"}),
                              (b"", {}), (b"not a PDF", {})):
            with self.subTest(body=body):
                self.seed()
                summary, _ = self.execute({PDF_URL: lambda: Response(PDF_URL, body, headers=headers)})
                self.assertTrue(summary["errors"])
                self.assertEqual([], next(iter(self.manifest().data["assets"].values()))["results"])
        self.assertFalse((self.directory / "magarif" / "files").exists())

    def test_disk_failure_stops_run_with_summary(self):
        self.seed()
        with mock.patch("ingestion.core.check_space", side_effect=OSError("disk reserve")):
            summary, _ = self.execute({PDF_URL: lambda: Response(PDF_URL, PDF)})
        self.assertEqual("operation", summary["errors"][0]["stage"])
        self.assertTrue(Path(summary["summary_path"]).is_file())

    def test_status_does_not_create_artifacts_or_network(self):
        with mock.patch.object(HTTP, "get", side_effect=AssertionError("unexpected network")):
            summary = run(self.settings, "magarif", "status")
        self.assertEqual(0, summary["records"])
        self.assertEqual([], list(self.directory.iterdir()))

    def test_configuration_paths_and_invalid_numbers(self):
        data = yaml.safe_load((ROOT / "ingestion.example.yaml").read_text())
        path = self.directory / "operational.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        self.assertEqual(self.directory / "__artifacts" / "ingestion", load_settings(path).artifacts_root)
        for bad in (True, 1.5, "10", 0, -1):
            data["limits"]["max_items"] = bad
            path.write_text(yaml.safe_dump(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_settings(path)
        with self.assertRaises(ValueError):
            restricted_settings(self.settings, limit=self.settings.max_items + 1)
        with self.assertRaises(ValueError):
            load_settings(None)
        path.write_text("limits: [", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Invalid YAML"):
            load_settings(path)

    def test_cli_help_sources_config_failure_and_no_network_status(self):
        runner = CliRunner()
        self.assertEqual(0, runner.invoke(app, ["--help"]).exit_code)
        self.assertEqual(["magarif", "tatarica"], runner.invoke(app, ["sources"]).stdout.splitlines())
        missing = runner.invoke(app, ["download", "--source", "magarif"])
        self.assertEqual(1, missing.exit_code)
        self.assertIn("--config", missing.output)
        unknown = runner.invoke(app, ["download", "--source", "unknown"])
        self.assertIn("Unknown source", unknown.output)
        data = yaml.safe_load((ROOT / "ingestion.example.yaml").read_text())
        data["artifacts_root"] = str(self.directory / "empty")
        path = self.directory / "config.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        with mock.patch("requests.Session.get", side_effect=AssertionError("unexpected network")):
            status = runner.invoke(app, ["--config", str(path), "status", "--source", "magarif"])
        self.assertEqual(0, status.exit_code, status.output)
        self.assertFalse((self.directory / "empty").exists())
        self.assertEqual(0, json.loads(status.stdout)["records"])


if __name__ == "__main__":
    unittest.main()
