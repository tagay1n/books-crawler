import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import mark_existing_limited as mk_mark  # noqa: E402


class MilliMarkExistingLimitedTests(unittest.TestCase):
    def test_build_lookups_normalizes_url_and_title(self):
        idx = {
            "/a": {
                "doc_url": "https://x/y/",
                "download_code": "dc1",
                "doc_card_url": "https://x/card/1/",
                "title": "  Hello   World ",
            }
        }
        lookups = mk_mark._build_lookups(idx)
        self.assertIn("https://x/y", lookups["doc_url"])
        self.assertIn("https://x/card/1", lookups["doc_card_url"])
        self.assertIn("Hello World", lookups["title"])

    def test_match_index_entry_uses_priority_order(self):
        lookups = {
            "doc_url": {"https://x/doc": ["/a"]},
            "download_code": {"dc": ["/b"]},
            "doc_card_url": {"https://x/card": ["/c"]},
            "title": {"Title": ["/d"]},
        }
        meta = {
            "doc_url": "https://x/doc",
            "download_code": "dc",
            "doc_card_url": "https://x/card",
            "title": "Title",
        }
        card, by = mk_mark._match_index_entry(meta, lookups)
        self.assertEqual(card, "/a")
        self.assertEqual(by, "doc_url")

    def test_match_index_entry_falls_through_ambiguous_first_candidate(self):
        lookups = {
            "doc_url": {"https://x/doc": ["/a", "/b"]},
            "download_code": {"dc": ["/c"]},
            "doc_card_url": {},
            "title": {},
        }
        meta = {"doc_url": "https://x/doc", "download_code": "dc"}
        card, by = mk_mark._match_index_entry(meta, lookups)
        self.assertEqual(card, "/c")
        self.assertEqual(by, "download_code")

    def test_match_index_entry_raises_when_no_unique_match(self):
        lookups = {"doc_url": {}, "download_code": {}, "doc_card_url": {}, "title": {}}
        with self.assertRaises(ValueError):
            mk_mark._match_index_entry({"title": "none"}, lookups)

    def test_match_by_title_prefix_min_len(self):
        lookups = {"title": {"Very Long Title Example": ["/a"]}}
        self.assertIsNone(mk_mark._match_index_entry_by_title("short", lookups))
        self.assertEqual(mk_mark._match_index_entry_by_title("Very Long", lookups), "/a")

    def test_match_by_title_prefix_returns_none_for_ambiguous(self):
        lookups = {"title": {"Very Long Title One": ["/a"], "Very Long Title Two": ["/b"]}}
        self.assertIsNone(mk_mark._match_index_entry_by_title("Very Long", lookups))

    def test_mark_existing_limited_sets_flag_and_resets_fallback_matches(self):
        index = {
            "/doc/a": {
                "download_code": "code_a",
                "title": "Alpha Title",
                "downloaded": "limited",
                "decrypted": True,
            },
            "/doc/b": {
                "download_code": "code_b",
                "title": "Long DB Title with extra suffix",
                "downloaded": "limited",
                "decrypted": False,
            },
        }
        rows = [
            ("md5-a", False, "https://example.org/meta-a.zip", "unused"),
            ("md5-b", False, None, "Long DB Title"),
        ]

        class _FakeResult:
            def all(self):
                return rows

        class _FakeConn:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, _query):
                return _FakeResult()

        class _FakeEngine:
            def connect(self):
                return _FakeConn()

        with mock.patch.object(mk_mark, "load_index_file", return_value=index):
            with mock.patch.object(mk_mark, "create_engine", return_value=_FakeEngine()):
                with mock.patch.object(
                    mk_mark,
                    "_load_upstream_metadata",
                    return_value={"download_code": "code_a"},
                ):
                    with mock.patch.object(mk_mark, "dump_index") as m_dump:
                        mk_mark.mark_existing_limited()

        self.assertTrue(index["/doc/a"]["needs_full_download"])
        self.assertEqual(index["/doc/a"]["matched_by"], "download_code")
        self.assertEqual(index["/doc/a"]["downloaded"], "limited")
        self.assertTrue(index["/doc/a"]["decrypted"])

        self.assertEqual(index["/doc/b"]["matched_by"], "title")
        self.assertNotIn("downloaded", index["/doc/b"])
        self.assertNotIn("decrypted", index["/doc/b"])

        m_dump.assert_called_once_with(index)

    def test_mark_existing_limited_logs_when_title_fallback_not_found(self):
        index = {
            "/doc/a": {
                "download_code": "code_a",
                "title": "Known Title",
                "downloaded": "limited",
                "decrypted": False,
            }
        }
        rows = [("md5-x", False, None, "Unknown Title")]

        class _FakeResult:
            def all(self):
                return rows

        class _FakeConn:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, _query):
                return _FakeResult()

        class _FakeEngine:
            def connect(self):
                return _FakeConn()

        with mock.patch.object(mk_mark, "load_index_file", return_value=index):
            with mock.patch.object(mk_mark, "create_engine", return_value=_FakeEngine()):
                with mock.patch("builtins.print") as m_print:
                    with mock.patch.object(mk_mark, "dump_index") as m_dump:
                        mk_mark.mark_existing_limited()

        self.assertEqual(index["/doc/a"]["downloaded"], "limited")
        self.assertFalse(index["/doc/a"]["decrypted"])
        m_dump.assert_called_once_with(index)

        logged = "\n".join(call.args[0] for call in m_print.call_args_list if call.args)
        self.assertIn("No title match for md5='md5-x'", logged)
        self.assertIn("Marked 0 index entries", logged)


if __name__ == "__main__":
    unittest.main()
