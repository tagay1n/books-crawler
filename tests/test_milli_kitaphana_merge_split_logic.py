import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import merge_index as mk_merge  # noqa: E402
import split_index as mk_split  # noqa: E402


class MilliMergeSplitLogicTests(unittest.TestCase):
    def test_merge_indexes_updates_existing_and_keeps_old(self):
        old_index = {
            "/a": {"title": "A", "downloaded": "full", "stable": "old"},
            "/b": {"title": "B", "downloaded": None},
        }
        new_index = {
            "/a": {"title": "A2", "new_field": "x"},
            "/c": {"title": "C"},
        }

        merged = mk_merge._merge_indexes(new_index, old_index)
        self.assertEqual(set(merged.keys()), {"/a", "/b", "/c"})
        self.assertEqual(merged["/a"]["stable"], "old")
        self.assertEqual(merged["/a"]["new_field"], "x")
        self.assertEqual(merged["/a"]["title"], "A2")
        self.assertEqual(merged["/b"]["title"], "B")
        self.assertEqual(merged["/c"]["title"], "C")

    def test_split_is_allowed_by_code_or_title(self):
        filters = {"download_codes": {"abc_1"}, "titles": {"good title"}}
        by_code = {"download_code": "abc_1", "title": "Other"}
        by_title = {"download_code": "zzz", "title": "  Good Title  "}
        denied = {"download_code": "xxx", "title": "Nope"}

        self.assertTrue(mk_split._is_allowed(by_code, filters))
        self.assertTrue(mk_split._is_allowed(by_title, filters))
        self.assertFalse(mk_split._is_allowed(denied, filters))

    def test_split_is_allowed_without_filter(self):
        meta = {"download_code": "x", "title": "t"}
        self.assertTrue(mk_split._is_allowed(meta, None))


if __name__ == "__main__":
    unittest.main()
