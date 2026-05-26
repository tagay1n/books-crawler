import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LITRES_DIR = ROOT / "litres"
LITRES_DISCOVER = ROOT / "litres" / "discover.py"
if str(LITRES_DIR) not in sys.path:
    sys.path.insert(0, str(LITRES_DIR))
spec = importlib.util.spec_from_file_location("litres_discover_for_tests", LITRES_DISCOVER)
litres_discover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(litres_discover)


class _FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"{self.status_code} error", response=self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class LitresDiscoverTests(unittest.TestCase):
    def test_search_url_encodes_query_and_page(self):
        self.assertEqual(
            litres_discover._search_url("на татарском", 1),
            "https://www.litres.ru/search/?q=%D0%BD%D0%B0+%D1%82%D0%B0%D1%82%D0%B0%D1%80%D1%81%D0%BA%D0%BE%D0%BC&art_types=text_book&only_litres_subscription_arts=true&languages=ru&languages=en&languages=ba",
        )
        self.assertEqual(
            litres_discover._search_url("на татарском", 2),
            "https://www.litres.ru/search/?q=%D0%BD%D0%B0+%D1%82%D0%B0%D1%82%D0%B0%D1%80%D1%81%D0%BA%D0%BE%D0%BC&art_types=text_book&only_litres_subscription_arts=true&languages=ru&languages=en&languages=ba&page=2",
        )

    def test_score_candidate_uses_tatar_signals(self):
        score, signals = litres_discover._score_candidate(
            {
                "title": "Күңел дәфтәре",
                "summary": "Книга на татарском языке",
                "author": "Known Author",
            },
            "на татарском",
            {"Known Author"},
        )

        self.assertGreaterEqual(score, 100)
        self.assertIn("tatar_letters", signals)
        self.assertIn("known_author", signals)

    def test_discover_candidates_writes_reviewable_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = root / "__artifacts" / "litres"
            artifacts.mkdir(parents=True)
            existing_url = "https://www.litres.ru/book/a/known-1/"
            (artifacts / "books-index.json").write_text(
                json.dumps(
                    {
                        "known": {
                            "url": existing_url,
                            "author": "Known Author",
                            "content_type": "text",
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            search_html = """
            <article>
              <a href="/book/a/known-1/"><span class="title">Күңел китабы</span></a>
              <a href="/author/known/">Known Author</a>
            </article>
            <article>
              <a href="/book/b/new-2/"><span class="title">Russian title</span></a>
              <a href="/author/other/">Other Author</a>
            </article>
            """
            detail_html_by_url = {
                existing_url: '<html><meta name="description" content="Повесть на татарском языке"></html>',
                "https://www.litres.ru/book/b/new-2/": '<html><meta name="description" content="No relevant marker"></html>',
            }

            def _get_in_workdir(path):
                return str(root / path.removeprefix("../"))

            def _fake_get(url, **_kwargs):
                if "/search/" in url:
                    return _FakeResponse(search_html)
                return _FakeResponse(detail_html_by_url[url])

            with (
                mock.patch.object(litres_discover, "get_in_workdir", side_effect=_get_in_workdir),
                mock.patch.object(
                    litres_discover,
                    "read_config",
                    return_value={
                        "discover": _discover_config(max_pages_per_query=1)
                    },
                ),
                mock.patch.object(litres_discover, "get_sid", return_value="sid"),
                mock.patch.object(litres_discover.requests, "get", side_effect=_fake_get),
            ):
                litres_discover.discover_candidates()

            candidates = json.loads((artifacts / "candidates-index.json").read_text(encoding="utf-8"))
            self.assertEqual(1, len(candidates))
            candidate = next(iter(candidates.values()))
            self.assertEqual(existing_url, candidate["url"])
            self.assertTrue(candidate["already_indexed"])
            self.assertEqual("candidate", candidate["status"])
            self.assertEqual("на татарском", candidate["sources"][0]["query"])
            self.assertGreaterEqual(candidate["score"], 40)

    def test_discover_config_caps_pages_per_query_at_twenty(self):
        with mock.patch.object(
            litres_discover,
            "read_config",
            return_value={"discover": _discover_config(max_pages_per_query=400)},
        ):
            config = litres_discover._discover_config()

        self.assertEqual(20, config["max_pages_per_query"])

    def test_discover_config_allows_lower_pages_per_query(self):
        with mock.patch.object(
            litres_discover,
            "read_config",
            return_value={"discover": _discover_config(max_pages_per_query=7)},
        ):
            config = litres_discover._discover_config()

        self.assertEqual(7, config["max_pages_per_query"])

    def test_discover_config_requires_values(self):
        with mock.patch.object(litres_discover, "read_config", return_value={}):
            with self.assertRaisesRegex(ValueError, "discover"):
                litres_discover._discover_config()

    def test_discover_config_rejects_empty_queries(self):
        with mock.patch.object(
            litres_discover,
            "read_config",
            return_value={"discover": _discover_config(search_queries=[])},
        ):
            with self.assertRaisesRegex(ValueError, "search_queries"):
                litres_discover._discover_config()

    def test_parse_search_books_reads_next_data_payload(self):
        initial_state = {
            "rtkqApi": {
                "queries": {
                    'getSearchData({"q":"на татарском"})': {
                        "data": {
                            "data": [
                                {
                                    "type": "text_book",
                                    "instance": {
                                        "url": "/book/a/book-1/",
                                        "title": "Күңелем җылы тели",
                                        "subtitle": "Повесть",
                                        "art_type": 0,
                                        "language_code": "ru",
                                        "is_available_with_litres_subscription": True,
                                        "persons": [
                                            {"role": "author", "full_name": "Миляуша Кагарманова"}
                                        ],
                                    },
                                },
                                {
                                    "type": "text_book",
                                    "instance": {
                                        "url": "/book/b/book-2/",
                                        "title": "Кырлай әкиятләре",
                                        "art_type": 4,
                                        "persons": [
                                            {"role": "translator", "full_name": "Translator"},
                                            {"role": "author", "full_name": "Габдулла Тукай"},
                                        ],
                                    },
                                },
                                {
                                    "type": "audiobook",
                                    "instance": {
                                        "url": "/audiobook/a/audio-3/",
                                        "title": "Audio",
                                        "art_type": 1,
                                    },
                                },
                            ]
                        }
                    }
                }
            }
        }
        html = (
            '<script id="__NEXT_DATA__" type="application/json">'
            + json.dumps({"props": {"pageProps": {"initialState": json.dumps(initial_state)}}})
            + "</script>"
        )

        books = litres_discover._parse_search_books(html)

        self.assertEqual(2, len(books))
        self.assertEqual(
            {
                "title": "Күңелем җылы тели",
                "url": "https://www.litres.ru/book/a/book-1/",
                "subscription": True,
                "content_type": "text",
                "author": "Миляуша Кагарманова",
                "summary": "Повесть",
                "litres_language": "ru",
                "full_name": "Күңелем җылы тели - Миляуша Кагарманова",
            },
            books[0],
        )
        self.assertEqual("pdf", books[1]["content_type"])
        self.assertEqual("Габдулла Тукай", books[1]["author"])

    def test_extract_summary_reads_meta_description(self):
        soup = litres_discover.bs.BeautifulSoup(
            '<html><meta name="description" content=" Китап  на татарском языке "></html>',
            "html.parser",
        )

        self.assertEqual("Китап на татарском языке", litres_discover._extract_summary(soup))

    def test_fetch_search_page_html_retries_before_browser_after_403(self):
        class _Driver:
            page_source = "<html>browser</html>"

            def __init__(self):
                self.urls = []

            def get(self, url):
                self.urls.append(url)

        driver = _Driver()
        responses = [_FakeResponse("blocked", 403), _FakeResponse("<html>ok</html>")]
        with (
            mock.patch.object(litres_discover.requests, "get", side_effect=responses) as get,
            mock.patch.object(litres_discover.time, "sleep") as sleep,
        ):
            html = litres_discover._fetch_search_page_html(
                "https://www.litres.ru/search/?q=x",
                {},
                lambda: driver,
                retries=3,
            )

        self.assertEqual("<html>ok</html>", html)
        self.assertEqual(2, get.call_count)
        sleep.assert_called_once_with(1)
        self.assertEqual([], driver.urls)

    def test_fetch_search_page_html_uses_browser_after_retries(self):
        class _Driver:
            page_source = "<html>browser</html>"

            def __init__(self):
                self.urls = []

            def get(self, url):
                self.urls.append(url)

        driver = _Driver()
        with (
            mock.patch.object(litres_discover.requests, "get", return_value=_FakeResponse("blocked", 403)),
            mock.patch.object(litres_discover.time, "sleep"),
        ):
            html = litres_discover._fetch_search_page_html(
                "https://www.litres.ru/search/?q=x",
                {},
                lambda: driver,
                retries=2,
            )

        self.assertEqual("<html>browser</html>", html)
        self.assertEqual(["https://www.litres.ru/search/?q=x"], driver.urls)

    def test_config_bool_accepts_string_values(self):
        self.assertTrue(litres_discover._config_bool("false") is False)
        self.assertTrue(litres_discover._config_bool("true") is True)


def _discover_config(**overrides):
    config = {
        "search_queries": ["на татарском", "на татарском языке", "татарский язык"],
        "max_pages_per_query": 20,
        "min_score": 40,
        "browser_headless": True,
        "search_request_retries": 3,
    }
    config.update(overrides)
    return config


if __name__ == "__main__":
    unittest.main()
