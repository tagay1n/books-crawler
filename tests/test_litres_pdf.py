import importlib.util
import sys
import unittest
from pathlib import Path


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
