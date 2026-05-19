import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

import bs4 as bs


ROOT = Path(__file__).resolve().parents[1]
LITRES_DIR = ROOT / "litres"
LITRES_INDEX = ROOT / "litres" / "index.py"
if str(LITRES_DIR) not in sys.path:
    sys.path.insert(0, str(LITRES_DIR))
spec = importlib.util.spec_from_file_location("litres_index_for_tests", LITRES_INDEX)
litres_index = importlib.util.module_from_spec(spec)
spec.loader.exec_module(litres_index)
sys.modules.pop("utils", None)


class LitresIndexTests(unittest.TestCase):
    def test_parse_legacy_card(self):
        soup = bs.BeautifulSoup(
            """
            <div class="ArtDefault_container__x">
              <a class="ArtDefault_cover__x" href="/book/a/b-123/"></a>
              <p class="ArtInfo_title__x"> Title / One </p>
              <a class="ArtInfo_author__x"> Author One </a>
              <div class="ArtPriceFooter_ArtPriceFooterSubscriptions__x">subscription</div>
              <span class="Label_label__x">PDF</span>
            </div>
            """,
            "html.parser",
        )

        books = litres_index._parse_books(soup)

        self.assertEqual(len(books), 1)
        self.assertEqual(books[0]["url"], "https://www.litres.ru/book/a/b-123/")
        self.assertEqual(books[0]["title"], "Title / One")
        self.assertEqual(books[0]["author"], "Author One")
        self.assertEqual(books[0]["content_type"], "pdf")
        self.assertTrue(books[0]["subscription"])
        self.assertEqual(books[0]["full_name"], "Title | One - Author One")

    def test_parse_current_link_card(self):
        soup = bs.BeautifulSoup(
            """
            <article data-testid="book-card">
              <a href="/book/raznoe/idel-na-tatarskom-yazyke-02-2025-73817343/">
                <span data-testid="art-title">Идел №2 2025</span>
              </a>
              <a href="/author/raznoe/">Разное</a>
              <div>Можно читать по абонементу</div>
              <div>Электронная книга</div>
            </article>
            """,
            "html.parser",
        )

        books = litres_index._parse_books(soup)

        self.assertEqual(len(books), 1)
        self.assertEqual(
            books[0]["url"],
            "https://www.litres.ru/book/raznoe/idel-na-tatarskom-yazyke-02-2025-73817343/",
        )
        self.assertEqual(books[0]["title"], "Идел №2 2025")
        self.assertEqual(books[0]["author"], "Разное")
        self.assertEqual(books[0]["content_type"], "text")
        self.assertTrue(books[0]["subscription"])

    def test_parse_current_link_card_detects_pdf_from_card_attributes(self):
        soup = bs.BeautifulSoup(
            """
            <article data-testid="book-card" data-format="PDF">
              <a href="/book/r-kurbanov-32253560/duslar-zh-yry-pesnya-druzey-69431533/">
                <span data-testid="art-title">Дуслар җыры / Песня друзей</span>
              </a>
            </article>
            """,
            "html.parser",
        )

        books = litres_index._parse_books(soup)

        self.assertEqual(len(books), 1)
        self.assertEqual(books[0]["content_type"], "pdf")

    def test_parse_current_link_card_deduplicates_urls(self):
        soup = bs.BeautifulSoup(
            """
            <article data-testid="book-card">
              <a href="/book/a/book-1/">Book One</a>
              <a href="/book/a/book-1/?from=card">Book One duplicate</a>
            </article>
            """,
            "html.parser",
        )

        books = litres_index._parse_books(soup)

        self.assertEqual(len(books), 1)
        self.assertEqual(books[0]["url"], "https://www.litres.ru/book/a/book-1/")

    def test_merge_uses_existing_pdf_artifacts_when_card_type_is_unknown(self):
        existing = {
            "title": "Old title",
            "url": "https://www.litres.ru/book/a/book-1/",
            "file_id": "99972571",
        }
        parsed = {
            "title": "New title",
            "content_type": None,
            "url": "https://www.litres.ru/book/a/book-1/",
        }

        details = litres_index._merge_book_details(existing, parsed)

        self.assertEqual(details["title"], "New title")
        self.assertEqual(details["content_type"], "pdf")
        self.assertEqual(details["file_id"], "99972571")

    def test_merge_resolves_unknown_type_when_no_local_artifacts(self):
        parsed = {
            "title": "New title",
            "content_type": None,
            "url": "https://www.litres.ru/book/a/book-1/",
        }

        details = litres_index._merge_book_details({}, parsed, lambda _url: "pdf")

        self.assertEqual(details["content_type"], "pdf")

    def test_merge_raises_when_card_type_is_unknown(self):
        parsed = {
            "title": "New title",
            "content_type": None,
            "url": "https://www.litres.ru/book/a/book-1/",
        }

        with self.assertRaisesRegex(ValueError, "Could not determine Litres content type.*book-1"):
            litres_index._merge_book_details({}, parsed)

    def test_merge_raises_when_existing_pdf_conflicts_with_explicit_text(self):
        existing = {
            "url": "https://www.litres.ru/book/a/book-1/",
            "file_id": "99972571",
        }
        parsed = {
            "title": "New title",
            "content_type": "text",
            "url": "https://www.litres.ru/book/a/book-1/",
        }

        with self.assertRaisesRegex(ValueError, "content type conflict.*book-1"):
            litres_index._merge_book_details(existing, parsed)

    def test_content_type_from_reader_url_detects_pdf_reader(self):
        self.assertEqual(
            litres_index._content_type_from_reader_url(
                "https://www.litres.ru/reader/?file=12345",
                "https://www.litres.ru/book/a/book-1/",
            ),
            "pdf",
        )

    def test_content_type_from_reader_url_detects_or3_pdf_reader(self):
        self.assertEqual(
            litres_index._content_type_from_reader_url(
                "https://www.litres.ru/static/or3/view/or.html?art_type=4&art=73817343&trial=1",
                "https://www.litres.ru/book/raznoe/idel-na-tatarskom-yazyke-02-2025-73817343/",
            ),
            "pdf",
        )

    def test_content_type_from_reader_url_detects_text_reader(self):
        self.assertEqual(
            litres_index._content_type_from_reader_url(
                "https://www.litres.ru/reader/?baseurl=/pages/biblio_book/",
                "https://www.litres.ru/book/a/book-1/",
            ),
            "text",
        )

    def test_content_type_from_reader_url_raises_for_unknown_reader(self):
        with self.assertRaisesRegex(ValueError, "reader URL"):
            litres_index._content_type_from_reader_url(
                "https://www.litres.ru/reader/",
                "https://www.litres.ru/book/a/book-1/",
            )

    def test_reader_resolver_reuses_single_driver(self):
        driver = mock.Mock()
        with (
            mock.patch.object(litres_index, "create_driver", return_value=driver) as create_driver,
            mock.patch.object(litres_index, "_open_reader_url", side_effect=["https://www.litres.ru/reader/?file=1", "https://www.litres.ru/reader/?file=2"]),
        ):
            resolver = litres_index._ReaderContentTypeResolver()
            try:
                self.assertEqual(resolver("https://www.litres.ru/book/a/book-1/"), "pdf")
                self.assertEqual(resolver("https://www.litres.ru/book/a/book-2/"), "pdf")
            finally:
                resolver.close()

        create_driver.assert_called_once_with()
        driver.quit.assert_called_once_with()

    def test_raise_if_blocked_detects_ddos_guard(self):
        with self.assertRaises(RuntimeError):
            litres_index._raise_if_blocked("<title>DDoS-Guard</title>", "https://example.test")


if __name__ == "__main__":
    unittest.main()
