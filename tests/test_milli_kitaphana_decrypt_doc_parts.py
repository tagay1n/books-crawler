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

import decrypt as mk_decrypt  # noqa: E402


class _FakeThreadPool:
    def __init__(self, processes):
        self.processes = processes

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def map(self, func, iterable):
        return [func(item) for item in iterable]


class _FakePdfDoc:
    def __init__(self, path):
        self.path = path
        self.passwords = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def authenticate(self, password):
        self.passwords.append(password)
        return True


class _FakeAccumulator:
    def __init__(self):
        self.inserted = []
        self.page_mode = None
        self.page_layout = None
        self.toc = None
        self.metadata = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def insert_pdf(self, pdf_doc):
        self.inserted.append(pdf_doc.path)

    def set_pagemode(self, value):
        self.page_mode = value

    def set_pagelayout(self, value):
        self.page_layout = value

    def set_toc(self, value):
        self.toc = value

    def set_metadata(self, value):
        self.metadata = value

    def write(self):
        return b"%PDF-1.4\n"


class _DummyProgress:
    def __init__(self):
        self.messages = []

    def main(self, message):
        self.messages.append(message)


class MilliDecryptDocPartsTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="mk_dec_parts_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_decrypt_doc_parts_merges_parts_and_sets_metadata_and_toc(self):
        meta_dir = os.path.join(self.tmp_dir, "meta")
        os.makedirs(meta_dir, exist_ok=True)
        source_meta = {
            "parts": [
                {"url": "part1.zip", "pagesCount": 2},
                {"url": None, "pagesCount": 1},
            ],
            "fingerprint": "fp-123",
            "pageMode": "UseOutlines",
            "pageLayout": "SinglePage",
        }
        with open(os.path.join(meta_dir, "source.json"), "w", encoding="utf-8") as f:
            json.dump(source_meta, f)
        with open(os.path.join(meta_dir, "outline.json"), "w", encoding="utf-8") as f:
            json.dump(
                [
                    {"title": " Chapter 1. ", "dest": [0]},
                    {"title": " Chapter Too Far. ", "dest": [5]},
                ],
                f,
            )

        acc = _FakeAccumulator()

        def _fake_open(path=None):
            if path is None:
                return acc
            return _FakePdfDoc(path)

        def _fake_decrypt_file(context, part, enc_unzip_dir):
            if part == "part0.zip":
                return meta_dir
            return os.path.join(self.tmp_dir, f"{part}.pdf")

        def _fake_decrypt_file_task(context, num, part_url, enc_unzip_dir, counter, total):
            return num, os.path.join(self.tmp_dir, f"dec_{num}.pdf")

        context = {
            "work_dir": self.tmp_dir,
            "progress": _DummyProgress(),
            "meta": {
                "enc_part_paths": [
                    {"num": 0, "part_url": "part1.zip", "enc_unzip_dir": "e1"},
                    {"num": 1, "part_url": "part2.zip", "enc_unzip_dir": "e2"},
                ],
                "title": "Test Title",
                "integrated_description": ["Desc"],
                "classification": "CLS",
                "author": "Auth",
                "tags": ["a", "b"],
            },
        }

        with mock.patch.object(mk_decrypt, "ThreadPool", _FakeThreadPool):
            with mock.patch.object(mk_decrypt, "download_part", return_value="/enc-meta"):
                with mock.patch.object(mk_decrypt, "_decrypt_file", side_effect=_fake_decrypt_file):
                    with mock.patch.object(mk_decrypt, "_decrypt_file_task", side_effect=_fake_decrypt_file_task):
                        with mock.patch.object(mk_decrypt, "_build_output_filename", return_value="result.pdf"):
                            with mock.patch.object(mk_decrypt.pymupdf, "open", side_effect=_fake_open):
                                out = mk_decrypt.decrypt_doc_parts(context)

        self.assertEqual(out, os.path.join(self.tmp_dir, "result.pdf"))
        self.assertTrue(os.path.exists(out))
        self.assertEqual(acc.inserted, [os.path.join(self.tmp_dir, "dec_0.pdf"), os.path.join(self.tmp_dir, "dec_1.pdf")])
        self.assertEqual(acc.page_mode, "UseOutlines")
        self.assertEqual(acc.page_layout, "SinglePage")
        self.assertEqual(acc.toc, [[1, "Chapter 1", 1], [1, "Chapter Too Far", -1]])
        self.assertEqual(acc.metadata["title"], "Test Title")
        self.assertEqual(acc.metadata["author"], "Auth")
        self.assertEqual(acc.metadata["keywords"], "a, b")
        self.assertEqual(acc.metadata["subject"], "Desc; CLS")
        self.assertEqual(context["meta"]["available_pages"], 2)

    def test_get_toc_returns_empty_when_outline_missing(self):
        meta_dir = os.path.join(self.tmp_dir, "meta-no-outline")
        os.makedirs(meta_dir, exist_ok=True)
        context = {"meta": {}}
        toc = mk_decrypt._get_toc(context, meta_dir, [{"url": "x", "pagesCount": 3}])
        self.assertEqual(toc, [])
        self.assertNotIn("available_pages", context["meta"])


if __name__ == "__main__":
    unittest.main()
