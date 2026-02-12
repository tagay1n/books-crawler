import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import download as mk_download  # noqa: E402


class _DummyProgress:
    def __init__(self):
        self.messages = []

    def main(self, message):
        self.messages.append(message)


class _FakeThreadPool:
    def __init__(self, processes):
        self.processes = processes

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def map(self, func, iterable):
        return [func(item) for item in iterable]


class MilliDownloadByCodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="mk_dl_code_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_download_by_code_handles_mixed_parts_and_access_downgrade(self):
        meta_dir = os.path.join(self.tmp_dir, "meta")
        os.makedirs(meta_dir, exist_ok=True)
        with open(os.path.join(meta_dir, "source.json"), "w", encoding="utf-8") as f:
            json.dump({"parts": [{"url": "part1.zip"}, {}]}, f)

        context = {
            "work_dir": self.tmp_dir,
            "progress": _DummyProgress(),
            "meta": {},
        }

        with mock.patch.object(mk_download, "ThreadPool", _FakeThreadPool):
            with mock.patch.object(mk_download, "download_part", return_value="/enc-part0") as m_download_part:
                with mock.patch.object(mk_download, "_decrypt_file", return_value=meta_dir):
                    with mock.patch.object(mk_download, "_try_reuse_local_part", return_value="/tmp/reused"):
                        mk_download._download_by_code(context)

        self.assertEqual(context["meta"]["access"], "limited")
        self.assertEqual(
            context["meta"]["enc_part_paths"],
            [{"num": 0, "part_url": "part1.zip", "enc_unzip_dir": os.path.normpath("/tmp/reused")}],
        )
        m_download_part.assert_called_once_with(context, "part0.zip")


if __name__ == "__main__":
    unittest.main()
