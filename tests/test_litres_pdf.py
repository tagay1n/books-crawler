import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

import pymupdf
import requests
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
LITRES_DIR = ROOT / "litres"
LITRES_PDF = ROOT / "litres" / "pdf.py"
if str(LITRES_DIR) not in sys.path:
    sys.path.insert(0, str(LITRES_DIR))
spec = importlib.util.spec_from_file_location("litres_pdf_for_tests", LITRES_PDF)
litres_pdf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(litres_pdf)
sys.modules.pop("utils", None)


class _FakeResponse:
    def __init__(self, content_type, content=b"not image", status_code=200):
        self.headers = {"content-type": content_type}
        self.content = content
        self.status_code = status_code
        self.text = content.decode("utf-8", errors="replace")
        self.url = "https://www.litres.ru/test"

    def raise_for_status(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _ForbiddenResponse(_FakeResponse):
    def __init__(self):
        super().__init__("text/html; charset=utf-8", b"Forbidden", 403)

    def raise_for_status(self):
        error = requests.HTTPError("403 Client Error: Forbidden")
        error.response = self
        raise error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class LitresPdfTests(unittest.TestCase):
    def test_get_pdf_books_to_visit_skips_already_reconstructed_pdfs(self):
        books = {
            "done": {
                "content_type": "pdf",
                "pdf_file": "/old/machine/book.pdf",
            },
            "pending": {
                "content_type": "pdf",
            },
            "text": {
                "content_type": "text",
            },
        }

        self.assertEqual(litres_pdf._get_pdf_books_to_visit(books), [books["pending"]])

    def test_has_pdf_runtime_details_requires_file_id_and_extensions(self):
        self.assertTrue(litres_pdf._has_pdf_runtime_details({"file_id": "39934490", "ext": {"pages": []}}))
        self.assertFalse(litres_pdf._has_pdf_runtime_details({"file_id": "39934490"}))
        self.assertFalse(litres_pdf._has_pdf_runtime_details({"ext": {"pages": []}}))

    def test_non_image_pdf_page_response_has_diagnostic_error(self):
        response = litres_pdf._response_details(
            _FakeResponse("text/html; charset=utf-8", b"<html>DDoS or auth page</html>")
        )

        with self.assertRaisesRegex(ValueError, "non-image PDF page response.*text/html"):
            litres_pdf._raise_for_non_image_pdf_page_response(
                response,
                "https://www.litres.ru/pages/get_pdf_page/?file=1&page=0",
            )

    def test_non_javascript_pdf_metadata_response_has_diagnostic_error(self):
        response = litres_pdf._response_details(
            _FakeResponse("text/html; charset=utf-8", b"<title>DDoS-Guard</title>", 403)
        )

        with self.assertRaisesRegex(ValueError, "non-JavaScript PDF metadata response.*DDoS-Guard"):
            litres_pdf._raise_for_non_javascript_pdf_metadata_response(
                response,
                "https://www.litres.ru/pages/get_pdf_js/?file=1",
            )

    def test_should_retry_response_with_browser_detects_uppercase_ddos_guard(self):
        self.assertTrue(
            litres_pdf._should_retry_response_with_browser(
                {
                    "content_type": "text/html; charset=UTF-8",
                    "text": "<title>DDOS-GUARD</title>",
                }
            )
        )

    def test_invalid_selenium_session_error_is_detected(self):
        from selenium.common.exceptions import InvalidSessionIdException, WebDriverException

        self.assertTrue(litres_pdf._is_invalid_selenium_session_error(InvalidSessionIdException("invalid session id")))
        self.assertTrue(litres_pdf._is_invalid_selenium_session_error(WebDriverException("invalid session id")))
        self.assertFalse(litres_pdf._is_invalid_selenium_session_error(WebDriverException("other selenium failure")))

    def test_auth_response_raises_actionable_error(self):
        response = litres_pdf._response_details(
            _FakeResponse("text/html; charset=utf-8", b"<html>login</html>")
        )
        response["url"] = "https://www.litres.ru/auth/login/?ref_url=%2Fpages%2Fget_pdf_js%2F"

        with self.assertRaisesRegex(litres_pdf.LitresAuthenticationError, "Update 'sid'"):
            litres_pdf._raise_for_auth_response(response, "auth failed")

    def test_get_file_id_from_book_page_html_reads_release_file_id(self):
        class _Session:
            def get(self, url, **_kwargs):
                self.url = url
                return _FakeResponse(
                    "text/html; charset=utf-8",
                    b'{\\"release_file_id\\":99942979,\\"preview_file_id\\":null}',
                )

        self.assertEqual(
            litres_pdf._get_file_id_from_book_page_html(
                "https://www.litres.ru/book/a/book-1/",
                _Session(),
            ),
            "99942979",
        )

    def test_get_content_type_from_book_page_reads_art_type(self):
        class _Session:
            def get(self, url, **_kwargs):
                self.url = url
                return _FakeResponse(
                    "text/html; charset=utf-8",
                    b'{\\"id\\":56748420,\\"title\\":\\"Book\\",\\"art_type\\":0}',
                )

        self.assertEqual(
            litres_pdf._get_content_type_from_book_page(
                "https://www.litres.ru/book/a/book-56748420/",
                _Session(),
            ),
            "text",
        )

    def test_get_content_type_from_book_page_falls_back_to_browser_on_403(self):
        class _Session:
            def get(self, _url, **_kwargs):
                return _ForbiddenResponse()

        driver = object()
        original_open_reader_url = litres_pdf._open_reader_url
        try:
            litres_pdf._open_reader_url = lambda _url, current_driver: (
                self.assertIs(current_driver, driver) or "https://www.litres.ru/reader/?file=12345"
            )
            self.assertEqual(
                litres_pdf._get_content_type_from_book_page(
                    "https://www.litres.ru/book/a/book-1/",
                    _Session(),
                    driver_provider=lambda: driver,
                ),
                "pdf",
            )
        finally:
            litres_pdf._open_reader_url = original_open_reader_url

    def test_get_file_id_falls_back_to_browser_on_403(self):
        class _Session:
            def get(self, _url, **_kwargs):
                return _ForbiddenResponse()

        driver = object()
        original_open_reader_url = litres_pdf._open_reader_url
        try:
            litres_pdf._open_reader_url = lambda _url, current_driver: (
                self.assertIs(current_driver, driver) or "https://www.litres.ru/reader/?file=12345"
            )
            self.assertEqual(
                litres_pdf._get_file_id(
                    "https://www.litres.ru/book/a/book-1/",
                    session=_Session(),
                    driver_provider=lambda: driver,
                ),
                "12345",
            )
        finally:
            litres_pdf._open_reader_url = original_open_reader_url

    def test_get_page_extensions_falls_back_to_browser_on_403(self):
        class _Session:
            def get(self, _url, **_kwargs):
                return _ForbiddenResponse()

        class _Driver:
            def execute_async_script(self, _script, _url):
                return {
                    "status": 200,
                    "content_type": "application/javascript",
                    "text": "PFURL.pdf[12345] = {pages:[{p:[]}]};",
                }

            def execute_script(self, _script):
                return {"pages": [{"p": []}]}

        self.assertEqual(
            litres_pdf._get_page_extensions(
                "12345",
                session=_Session(),
                driver_provider=lambda: _Driver(),
            ),
            {"pages": [{"p": []}]},
        )

    def test_get_page_extensions_falls_back_to_browser_on_ddos_guard_html(self):
        class _Session:
            def get(self, _url, **_kwargs):
                return _FakeResponse(
                    "text/html; charset=UTF-8",
                    b"<!doctype html><title>DDoS-Guard</title>",
                    200,
                )

        class _Driver:
            def execute_async_script(self, _script, _url):
                return {
                    "status": 200,
                    "content_type": "application/javascript",
                    "text": "PFURL.pdf[12345] = {pages:[{p:[]}]};",
                }

            def execute_script(self, _script):
                return {"pages": [{"p": []}]}

        self.assertEqual(
            litres_pdf._get_page_extensions(
                "12345",
                session=_Session(),
                driver_provider=lambda: _Driver(),
            ),
            {"pages": [{"p": []}]},
        )

    def test_download_page_images_falls_back_to_browser_on_ddos_guard_html(self):
        image_bytes = io.BytesIO()
        Image.new("RGB", (20, 10), "white").save(image_bytes, format="JPEG")

        class _Session:
            def get(self, _url, **_kwargs):
                return _FakeResponse(
                    "text/html; charset=UTF-8",
                    b"<!doctype html><title>DDoS-Guard</title>",
                    200,
                )

        class _Driver:
            pass

        with tempfile.TemporaryDirectory() as tmpdir:
            original_get_in_workdir = litres_pdf.get_in_workdir
            original_fetch_binary = litres_pdf._fetch_binary_with_browser
            try:
                litres_pdf.get_in_workdir = lambda path: str(Path(tmpdir) / path.removeprefix("../"))
                litres_pdf._fetch_binary_with_browser = lambda driver, _url: (
                    self.assertIsInstance(driver, _Driver) or image_bytes.getvalue(),
                    "image/jpeg",
                )
                litres_pdf.download_page_images(
                    "12345",
                    {"pages": [{"p": [{"w": 1900, "ext": "jpg"}]}]},
                    session=_Session(),
                    driver_provider=lambda: _Driver(),
                )
            finally:
                litres_pdf.get_in_workdir = original_get_in_workdir
                litres_pdf._fetch_binary_with_browser = original_fetch_binary

            self.assertTrue(litres_pdf._is_valid_image_file(Path(tmpdir) / "__artifacts/litres/images/12345/0.png"))

    def test_fetch_pdf_page_with_browser_warms_up_after_ddos_guard_html(self):
        image_bytes = io.BytesIO()
        Image.new("RGB", (20, 10), "white").save(image_bytes, format="JPEG")
        calls = []

        def _fetch_binary(_driver, _url):
            calls.append("fetch")
            if len(calls) == 1:
                return b"<!doctype html><title>DDoS-Guard</title>", "text/html; charset=UTF-8"
            return image_bytes.getvalue(), "image/jpeg"

        original_fetch_binary = litres_pdf._fetch_binary_with_browser
        original_fetch_cookies = litres_pdf._fetch_binary_with_browser_cookies
        original_warm_up = litres_pdf._warm_up_browser_for_protected_url
        try:
            litres_pdf._fetch_binary_with_browser = _fetch_binary
            litres_pdf._fetch_binary_with_browser_cookies = lambda _driver, _url, referer=None: (
                calls.append(("cookies", _url, referer)) or (image_bytes.getvalue(), "image/jpeg")
            )
            litres_pdf._warm_up_browser_for_protected_url = lambda _driver, protected_url, context_url: calls.append(
                ("warm", protected_url, context_url)
            )
            self.assertEqual(
                litres_pdf._fetch_pdf_page_with_browser(
                    object(),
                    "https://www.litres.ru/pages/get_pdf_page/?file=1&page=0",
                    "https://www.litres.ru/book/a/book-1/",
                ),
                (image_bytes.getvalue(), "image/jpeg"),
            )
        finally:
            litres_pdf._fetch_binary_with_browser = original_fetch_binary
            litres_pdf._fetch_binary_with_browser_cookies = original_fetch_cookies
            litres_pdf._warm_up_browser_for_protected_url = original_warm_up

        self.assertEqual(
            calls,
            [
                "fetch",
                (
                    "warm",
                    "https://www.litres.ru/pages/get_pdf_page/?file=1&page=0",
                    "https://www.litres.ru/book/a/book-1/",
                ),
                (
                    "cookies",
                    "https://www.litres.ru/pages/get_pdf_page/?file=1&page=0",
                    "https://www.litres.ru/book/a/book-1/",
                ),
            ],
        )

    def test_fetch_pdf_page_with_browser_uses_cookies_after_fetch_error(self):
        image_bytes = io.BytesIO()
        Image.new("RGB", (20, 10), "white").save(image_bytes, format="JPEG")
        calls = []

        original_fetch_binary = litres_pdf._fetch_binary_with_browser
        original_fetch_cookies = litres_pdf._fetch_binary_with_browser_cookies
        original_warm_up = litres_pdf._warm_up_browser_for_protected_url
        try:
            litres_pdf._fetch_binary_with_browser = lambda _driver, _url: (
                calls.append("fetch") or (_ for _ in ()).throw(ValueError("browser fetch failed"))
            )
            litres_pdf._fetch_binary_with_browser_cookies = lambda _driver, _url, referer=None: (
                calls.append(("cookies", _url, referer)) or (image_bytes.getvalue(), "image/jpeg")
            )
            litres_pdf._warm_up_browser_for_protected_url = lambda _driver, protected_url, context_url: calls.append(
                ("warm", protected_url, context_url)
            )
            self.assertEqual(
                litres_pdf._fetch_pdf_page_with_browser(
                    object(),
                    "https://www.litres.ru/pages/get_pdf_page/?file=1&page=0",
                    "https://www.litres.ru/book/a/book-1/",
                ),
                (image_bytes.getvalue(), "image/jpeg"),
            )
        finally:
            litres_pdf._fetch_binary_with_browser = original_fetch_binary
            litres_pdf._fetch_binary_with_browser_cookies = original_fetch_cookies
            litres_pdf._warm_up_browser_for_protected_url = original_warm_up

        self.assertEqual(
            calls,
            [
                "fetch",
                (
                    "warm",
                    "https://www.litres.ru/pages/get_pdf_page/?file=1&page=0",
                    "https://www.litres.ru/book/a/book-1/",
                ),
                (
                    "cookies",
                    "https://www.litres.ru/pages/get_pdf_page/?file=1&page=0",
                    "https://www.litres.ru/book/a/book-1/",
                ),
            ],
        )

    def test_get_litres_page_image_headers_use_browser_session(self):
        class _Driver:
            def execute_script(self, _script):
                return "Browser UA"

            def get_cookies(self):
                return [{"name": "SID", "value": "sid"}, {"name": "ddg", "value": "token"}]

        headers = litres_pdf._get_litres_page_image_headers(
            _Driver(),
            referer="https://www.litres.ru/book/a/book-1/",
        )

        self.assertEqual("Browser UA", headers["User-Agent"])
        self.assertIn("SID=sid", headers["Cookie"])
        self.assertIn("ddg=token", headers["Cookie"])
        self.assertEqual("https://www.litres.ru/book/a/book-1/", headers["Referer"])
        self.assertEqual("image", headers["Sec-Fetch-Dest"])

    def test_save_pdf_page_image_writes_final_atomically(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_bytes = io.BytesIO()
            Image.new("RGB", (20, 10), "white").save(image_bytes, format="JPEG")
            result_file = os.path.join(tmpdir, "0.png")

            litres_pdf._save_pdf_page_image(
                image_bytes.getvalue(),
                {"status": 200, "content_type": "image/jpeg", "content": image_bytes.getvalue()},
                result_file,
                "https://www.litres.ru/pages/get_pdf_page/?file=1&page=0",
            )

            self.assertTrue(litres_pdf._is_valid_image_file(result_file))
            self.assertEqual([], list(Path(tmpdir).glob("*.tmp.*")))

    def test_compressed_page_jpeg_bytes_downscales_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_page = Path(tmpdir) / "0.png"
            Image.new("RGB", (200, 100), "white").save(raw_page, format="PNG")

            compressed = litres_pdf._compressed_page_jpeg_bytes(
                raw_page,
                {"jpeg_quality": 70, "max_width": 50, "dpi": 120},
            )

            with Image.open(io.BytesIO(compressed)) as image:
                self.assertEqual("JPEG", image.format)
                self.assertEqual((50, 25), image.size)
            with Image.open(raw_page) as image:
                self.assertEqual((200, 100), image.size)

    def test_create_pdf_replaces_invalid_existing_pdf_atomically(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            images_dir = root / "__artifacts" / "litres" / "images" / "12345"
            docs_dir = root / "__artifacts" / "litres" / "docs"
            images_dir.mkdir(parents=True)
            docs_dir.mkdir(parents=True)
            Image.new("RGB", (120, 80), "white").save(images_dir / "0.png", format="PNG")
            pdf_file = docs_dir / "Book.pdf"
            pdf_file.write_bytes(b"partial")

            original_get_in_workdir = litres_pdf.get_in_workdir
            original_read_config = litres_pdf.read_config
            try:
                litres_pdf.get_in_workdir = lambda path: str(root / path.removeprefix("../"))
                litres_pdf.read_config = lambda: {"pdf": {"jpeg_quality": 80, "max_width": 60, "dpi": 120}}
                self.assertEqual(
                    litres_pdf._create_pdf({"file_id": "12345", "full_name": "Book"}),
                    str(pdf_file),
                )
            finally:
                litres_pdf.get_in_workdir = original_get_in_workdir
                litres_pdf.read_config = original_read_config

            with pymupdf.open(pdf_file) as doc:
                self.assertEqual(1, doc.page_count)
            self.assertEqual([], list(docs_dir.glob("*.tmp.*")))

    def test_temporary_path_uses_short_basename_for_long_pdf_names(self):
        long_name = "Тату яшәгәндә генә. Татарстан композиторларының балаларга атап язган җырлары | Когда мы дружим. Песни композиторов Татарстана для дет.pdf"

        tmp_path = litres_pdf._temporary_path(f"/tmp/{long_name}")

        self.assertLessEqual(len(os.path.basename(tmp_path).encode("utf-8")), 255)
        self.assertTrue(tmp_path.endswith(".pdf"))
        self.assertIn(".tmp.", os.path.basename(tmp_path))

    def test_get_pdf_browser_headless_reads_boolean_config(self):
        original_read_config = litres_pdf.read_config
        try:
            litres_pdf.read_config = lambda: {"pdf": {"browser_headless": "false"}}
            self.assertFalse(litres_pdf._get_pdf_browser_headless())
            litres_pdf.read_config = lambda: {"pdf": {"browser_headless": True}}
            self.assertTrue(litres_pdf._get_pdf_browser_headless())
        finally:
            litres_pdf.read_config = original_read_config

    def test_get_file_id_from_reader_url_uses_shared_reader_opening(self):
        driver = object()

        def _open_reader_url(book_page_url, current_driver):
            self.assertEqual(book_page_url, "https://www.litres.ru/book/a/book-1/")
            self.assertIs(current_driver, driver)
            return "https://www.litres.ru/reader/?file=12345"

        original_open_reader_url = litres_pdf._open_reader_url
        try:
            litres_pdf._open_reader_url = _open_reader_url
            self.assertEqual(
                litres_pdf._get_file_id_from_reader_url(
                    "https://www.litres.ru/book/a/book-1/",
                    driver,
                ),
                "12345",
            )
        finally:
            litres_pdf._open_reader_url = original_open_reader_url

    def test_get_file_id_from_reader_url_raises_with_reader_url_when_file_is_missing(self):
        original_open_reader_url = litres_pdf._open_reader_url
        try:
            litres_pdf._open_reader_url = lambda _url, _driver: "https://www.litres.ru/static/or3/view/or.html?art_type=4"
            with self.assertRaisesRegex(ValueError, "Could not find file id.*art_type=4"):
                litres_pdf._get_file_id_from_reader_url(
                    "https://www.litres.ru/book/a/book-1/",
                    object(),
                )
        finally:
            litres_pdf._open_reader_url = original_open_reader_url


if __name__ == "__main__":
    unittest.main()
