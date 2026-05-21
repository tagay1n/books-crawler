import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LITRES_DIR = ROOT / "litres"
LITRES_TEXT = ROOT / "litres" / "text.py"
if str(LITRES_DIR) not in sys.path:
    sys.path.insert(0, str(LITRES_DIR))
spec = importlib.util.spec_from_file_location("litres_text_for_tests", LITRES_TEXT)
litres_text = importlib.util.module_from_spec(spec)
spec.loader.exec_module(litres_text)
sys.modules.pop("utils", None)
sys.modules.pop("index", None)


class _FakeResponse:
    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content


class _FakeDriver:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class LitresTextTests(unittest.TestCase):
    def test_get_text_books_to_visit_skips_successfully_marked_books(self):
        books = {
            "done": {
                "content_type": "text",
                "markdown_file": "/tmp/book.md",
            },
            "failed": {
                "content_type": "text",
                "markdown_file": "/tmp/old.md",
                "download_error": "temporary failure",
            },
            "pending": {
                "content_type": "text",
            },
            "pdf": {
                "content_type": "pdf",
            },
        }

        self.assertEqual(
            litres_text._get_text_books_to_visit(books),
            [books["failed"], books["pending"]],
        )

    def test_make_up_markdown_returns_existing_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            book = {"full_name": "Existing Book"}
            output_dir = base / "markdown" / book["full_name"]
            output_dir.mkdir(parents=True)
            output_file = output_dir / f"{book['full_name']}.md"
            output_file.write_text("done", encoding="utf-8")

            def _get_in_workdir(path):
                if path.startswith("../__artifacts/litres/markdown/"):
                    return str(base / "markdown" / book["full_name"])
                return str(base / path)

            with mock.patch.object(litres_text, "get_in_workdir", side_effect=_get_in_workdir):
                self.assertEqual(
                    litres_text._make_up_markdown(str(base / "js"), book),
                    str(output_file),
                )

    def test_markdown_output_name_preserves_legacy_hf_style(self):
        book = {
            "full_name": "A/B | Кая бара бу дөнья?",
            "url": "https://www.litres.ru/book/a/book-123/",
        }

        output_name = litres_text._markdown_output_name(book)

        self.assertEqual(output_name, "A|B | Кая бара бу дөнья?")
        self.assertNotIn("/", output_name)

    def test_base_url_from_reader_url(self):
        self.assertEqual(
            litres_text._base_url_from_reader_url(
                "https://www.litres.ru/reader/?baseurl=/pages/biblio_book/123/",
                "https://www.litres.ru/book/a/book-1/",
            ),
            "/pages/biblio_book/123/",
        )

    def test_base_url_from_reader_url_raises_when_missing(self):
        with self.assertRaisesRegex(ValueError, "text resource base URL"):
            litres_text._base_url_from_reader_url(
                "https://www.litres.ru/reader/?file=123",
                "https://www.litres.ru/book/a/book-1/",
            )

    def test_download_page_descriptions_uses_shared_reader_opening(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            book = {"url": "https://www.litres.ru/book/a/book-without-id/"}

            def _get_in_workdir(path):
                if path == "../__artifacts/litres/js":
                    return str(base / "js")
                return str(base / path)

            def _fake_get(url, **_kwargs):
                if url.endswith("000.js"):
                    return _FakeResponse(200, b"[{t:'p',c:'Text'}]")
                return _FakeResponse(404)

            with (
                mock.patch.object(litres_text, "get_in_workdir", side_effect=_get_in_workdir),
                mock.patch.object(litres_text, "create_driver", return_value=_FakeDriver()),
                mock.patch.object(
                    litres_text,
                    "_open_reader_url",
                    return_value="https://www.litres.ru/reader/?baseurl=/pages/biblio_book/123/",
                ) as open_reader_url,
                mock.patch.object(litres_text, "get_sid", return_value="sid"),
                mock.patch.object(litres_text.requests, "get", side_effect=_fake_get),
            ):
                output_dir = Path(litres_text._download_page_descriptions(book))

            open_reader_url.assert_called_once()
            self.assertEqual(book["resource_url"], "https://www.litres.ru/pages/biblio_book/123/json/")
            self.assertTrue((output_dir / "000.js").exists())

    def test_download_page_descriptions_reuses_provided_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            driver = _FakeDriver()
            book = {"url": "https://www.litres.ru/book/a/book-without-id/"}

            def _get_in_workdir(path):
                if path == "../__artifacts/litres/js":
                    return str(base / "js")
                return str(base / path)

            def _fake_get(url, **_kwargs):
                if url.endswith("000.js"):
                    return _FakeResponse(200, b"[]")
                return _FakeResponse(404)

            with (
                mock.patch.object(litres_text, "get_in_workdir", side_effect=_get_in_workdir),
                mock.patch.object(litres_text, "create_driver") as create_driver,
                mock.patch.object(
                    litres_text,
                    "_open_reader_url",
                    return_value="https://www.litres.ru/reader/?baseurl=/pages/biblio_book/123/",
                ) as open_reader_url,
                mock.patch.object(litres_text, "get_sid", return_value="sid"),
                mock.patch.object(litres_text.requests, "get", side_effect=_fake_get),
            ):
                litres_text._download_page_descriptions(book, driver=driver)

            create_driver.assert_not_called()
            open_reader_url.assert_called_once_with("https://www.litres.ru/book/a/book-without-id/", driver)

    def test_resolve_resource_url_prefers_direct_litres_text_endpoint(self):
        with (
            mock.patch.object(litres_text, "get_sid", return_value="sid"),
            mock.patch.object(litres_text.requests, "get", return_value=_FakeResponse(200, b"[]")),
            mock.patch.object(litres_text, "_open_reader_url") as open_reader_url,
        ):
            resource_url = litres_text._resolve_resource_url("https://www.litres.ru/book/a/book-12345/")

        self.assertEqual(resource_url, "https://www.litres.ru/pub/t/12345.json/")
        open_reader_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
