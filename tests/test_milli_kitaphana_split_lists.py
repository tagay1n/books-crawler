import json
import os
import shutil
import sys
import tempfile
import codecs
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import split_index as mk_split  # noqa: E402


class MilliSplitListsTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="mk_split_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_split_lists_raises_for_invalid_parts(self):
        with self.assertRaises(ValueError):
            mk_split.split_lists(parts=0, dest=self.tmp_dir, prefix="p")

    def test_split_lists_distributes_docs_evenly(self):
        docs = [
            ("/a", {"download_code": "a", "title": "A"}),
            ("/b", {"download_code": "b", "title": "B"}),
            ("/c", {"download_code": "c", "title": "C"}),
            ("/d", {"download_code": "d", "title": "D"}),
            ("/e", {"download_code": "e", "title": "E"}),
        ]
        with mock.patch.object(mk_split, "load_index_file", return_value={"x": {}}):
            with mock.patch.object(mk_split, "get_not_downloaded_docs", return_value=docs):
                with mock.patch.object(mk_split, "_load_filter", return_value=None):
                    mk_split.split_lists(parts=3, dest=self.tmp_dir, prefix="part")

        files = sorted(os.listdir(self.tmp_dir))
        self.assertEqual(files, ["part-1.json", "part-2.json", "part-3.json"])
        counts = []
        for fn in files:
            with open(os.path.join(self.tmp_dir, fn), "r", encoding="utf-8") as f:
                counts.append(len(json.load(f)))
        self.assertEqual(sorted(counts), [1, 2, 2])

    def test_split_lists_applies_filter(self):
        docs = [
            ("/a", {"download_code": "code_1", "title": "Title One"}),
            ("/b", {"download_code": "code_2", "title": "Other"}),
            ("/c", {"download_code": "code_3", "title": "Keep Me"}),
        ]
        filters = {"download_codes": {"code_2"}, "titles": {"keep me"}}
        with mock.patch.object(mk_split, "load_index_file", return_value={"x": {}}):
            with mock.patch.object(mk_split, "get_not_downloaded_docs", return_value=docs):
                with mock.patch.object(mk_split, "_load_filter", return_value=filters):
                    mk_split.split_lists(parts=2, dest=self.tmp_dir, prefix="flt")

        kept = {}
        for fn in os.listdir(self.tmp_dir):
            with open(os.path.join(self.tmp_dir, fn), "r", encoding="utf-8") as f:
                kept.update(json.load(f))
        self.assertEqual(set(kept.keys()), {"/b", "/c"})

    def test_load_filter_returns_none_when_missing(self):
        fake_module_file = os.path.join(self.tmp_dir, "milli_kitaphana", "split_index.py")
        os.makedirs(os.path.dirname(fake_module_file), exist_ok=True)
        with mock.patch.object(mk_split, "__file__", fake_module_file):
            self.assertIsNone(mk_split._load_filter())

    def test_load_filter_reads_utf8_sig_and_normalizes_values(self):
        fake_module_file = os.path.join(self.tmp_dir, "milli_kitaphana", "split_index.py")
        os.makedirs(os.path.dirname(fake_module_file), exist_ok=True)
        filter_path = os.path.join(self.tmp_dir, "filter.json")
        payload = {
            "download_codes": [" code_1 ", "code_2"],
            "titles": ["  Some Title  ", "Another   One"],
        }
        with codecs.open(filter_path, "w", encoding="utf-8-sig") as f:
            json.dump(payload, f, ensure_ascii=False)

        with mock.patch.object(mk_split, "__file__", fake_module_file):
            filters = mk_split._load_filter()

        self.assertEqual(filters["download_codes"], {"code_1", "code_2"})
        self.assertEqual(filters["titles"], {"some title", "another   one"})

    def test_load_filter_returns_none_when_empty(self):
        fake_module_file = os.path.join(self.tmp_dir, "milli_kitaphana", "split_index.py")
        os.makedirs(os.path.dirname(fake_module_file), exist_ok=True)
        filter_path = os.path.join(self.tmp_dir, "filter.json")
        with open(filter_path, "w", encoding="utf-8") as f:
            json.dump({"download_codes": [], "titles": []}, f)

        with mock.patch.object(mk_split, "__file__", fake_module_file):
            self.assertIsNone(mk_split._load_filter())


if __name__ == "__main__":
    unittest.main()
