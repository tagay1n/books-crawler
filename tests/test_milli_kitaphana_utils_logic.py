import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from glob import glob
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import utils as mk_utils  # noqa: E402


class MilliUtilsLogicTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="mk_utils_test_")
        self.old_index_root = mk_utils.index_root_dir
        mk_utils.index_root_dir = self.tmp_dir

    def tearDown(self):
        mk_utils.index_root_dir = self.old_index_root
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_index_path_is_under__index_dir(self):
        index_path = mk_utils.get_index_file_loc()
        normalized = index_path.replace("\\", "/")
        self.assertTrue(normalized.endswith("/_index/books-index.json"))
        self.assertTrue(os.path.isdir(os.path.join(self.tmp_dir, "_index")))

    def test_backup_snapshot_writes_empty_json_when_index_missing(self):
        backup_path = mk_utils.backup_index_snapshot()
        self.assertTrue(os.path.exists(backup_path))
        self.assertIn("/_backups/", backup_path.replace("\\", "/"))
        with zipfile.ZipFile(backup_path, "r") as zf:
            self.assertEqual(zf.namelist(), ["books-index.json"])
            payload = zf.read("books-index.json").decode("utf-8")
            self.assertEqual(payload, "{}\n")

    def test_backup_snapshot_writes_current_index_content(self):
        expected = {"/card/1": {"title": "Book 1", "downloaded": "full"}}
        mk_utils.dump_index(expected)

        backup_path = mk_utils.backup_index_snapshot()
        with zipfile.ZipFile(backup_path, "r") as zf:
            payload = json.loads(zf.read("books-index.json").decode("utf-8"))
        self.assertEqual(payload, expected)

    def test_backup_snapshot_has_normalized_readable_name(self):
        backup_path = mk_utils.backup_index_snapshot()
        self.assertTrue(os.path.isabs(backup_path))
        self.assertNotIn("/../", backup_path.replace("\\", "/"))
        self.assertRegex(
            os.path.basename(backup_path),
            r"^books-index_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.zip$",
        )

    def test_get_not_downloaded_docs_default_mode(self):
        index = {
            "/a": {"publish_year": "1999", "downloaded": None},
            "/b": {"publish_year": "2005", "downloaded": "full"},
            "/c": {"publish_year": "2010", "downloaded": None, "broken": True},
            "/d": {"publish_year": "[2020]", "downloaded": None},
        }
        docs = mk_utils.get_not_downloaded_docs(index, limited=False)
        self.assertEqual([p for p, _ in docs], ["/d", "/a"])

    def test_get_not_downloaded_docs_limited_mode(self):
        index = {
            "/a": {"needs_full_download": True, "downloaded": None},
            "/b": {"needs_full_download": True, "downloaded": "limited"},
            "/c": {"needs_full_download": True, "downloaded": "full"},
            "/d": {"needs_full_download": False, "downloaded": None},
            "/e": {"needs_full_download": True, "downloaded": None, "broken": True},
        }
        docs = mk_utils.get_not_downloaded_docs(index, limited=True)
        self.assertEqual({p for p, _ in docs}, {"/a", "/b"})

    def test_get_list_file_loc(self):
        lists_dir = os.path.join(self.tmp_dir, "lists")
        loc1 = mk_utils.get_list_file_loc("part-1", lists_dir=lists_dir)
        loc2 = mk_utils.get_list_file_loc("part-2.json", lists_dir=lists_dir)
        self.assertTrue(loc1.endswith("part-1.json"))
        self.assertTrue(loc2.endswith("part-2.json"))
        with self.assertRaises(ValueError):
            mk_utils.get_list_file_loc("", lists_dir=lists_dir)

    def test_open_lock_creates_and_removes_lock_file(self):
        index_path = os.path.join(self.tmp_dir, "index.json")
        lock_path = f"{index_path}.lock"
        with mk_utils.open_lock(index_path, wait_seconds=0.01):
            self.assertTrue(os.path.exists(lock_path))
        self.assertFalse(os.path.exists(lock_path))

    def test_dump_index_writes_json_and_cleans_tmp_part_file(self):
        index_path = os.path.join(self.tmp_dir, "index.json")
        payload = {"/a": {"title": "A"}}
        mk_utils.dump_index(payload, index_file=index_path)
        with open(index_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded, payload)
        self.assertEqual(glob(index_path + ".*_part"), [])

    def test_read_config_supports_utf8_sig(self):
        cfg_path = os.path.join(self.tmp_dir, "config.yaml")
        with open(cfg_path, "w", encoding="utf-8-sig") as f:
            f.write("aes:\n  raw_key: [1, 2, 3]\n")

        with unittest.mock.patch.object(mk_utils, "get_in_workdir", return_value=cfg_path):
            cfg = mk_utils.read_config()

        self.assertEqual(cfg["aes"]["raw_key"], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
