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
import download as mk_download  # noqa: E402
import index as mk_index  # noqa: E402
import utils as mk_utils  # noqa: E402


class _DummyProgressWrapper:
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def main(self, *_args, **_kwargs):
        return None


class MilliPipelineSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="mk_pipeline_")
        self.index_root = os.path.join(self.tmp_dir, "artifacts", "milli.kitaphana")
        self.work_root = os.path.join(self.tmp_dir, "work")
        os.makedirs(self.index_root, exist_ok=True)
        os.makedirs(self.work_root, exist_ok=True)

        self.old_index_root = mk_utils.index_root_dir
        self.old_utils_base_dir = mk_utils.base_dir
        self.old_download_base_dir = mk_download.base_dir
        self.old_decrypt_base_dir = mk_decrypt.base_dir

        mk_utils.index_root_dir = self.index_root
        mk_utils.base_dir = self.work_root
        mk_download.base_dir = self.work_root
        mk_decrypt.base_dir = self.work_root

    def tearDown(self):
        mk_utils.index_root_dir = self.old_index_root
        mk_utils.base_dir = self.old_utils_base_dir
        mk_download.base_dir = self.old_download_base_dir
        mk_decrypt.base_dir = self.old_decrypt_base_dir
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_index_download_decrypt_state_transitions(self):
        new_index = {"/tt/ssearch/detail/abc": {"title": "Book A"}}

        with mock.patch.object(mk_index, "LANGUAGE_QUERIES", ["tat"]):
            with mock.patch.object(mk_index, "_create_newest_index", return_value=new_index):
                mk_index.index()

        index_after_index = mk_utils.load_index_file()
        self.assertIn("/tt/ssearch/detail/abc", index_after_index)
        self.assertEqual(index_after_index["/tt/ssearch/detail/abc"]["title"], "Book A")

        def _fake_scrap_doc_card(_card_path, meta, proxies):
            del proxies
            meta["download_code"] = "book_a"
            meta["doc_url"] = "http://kitap.tatar.ru/dl/book_a"
            meta["doc_card_url"] = "https://kitap.tatar.ru/tt/ssearch/detail/abc/"

        def _fake_get_details(context):
            context["meta"]["format_url"] = "/download/{url}"
            context["token2"] = "tok2"
            context["keyUrl"] = "/tt/dl/key"

        def _fake_dh_key_exchange(context):
            context["meta"]["decryption_key"] = "a2V5"
            context["meta"]["decryption_key_iv"] = "aXY="

        def _fake_download_by_code(context):
            context["meta"]["access"] = "open"
            context["meta"]["enc_part_paths"] = [
                {"num": 0, "part_url": "part1.zip", "enc_unzip_dir": os.path.join(self.work_root, "book_a", "e1")}
            ]

        with mock.patch.object(mk_download, "read_config", return_value={"cfg": 1}):
            with mock.patch.object(mk_download, "_scrap_doc_card", side_effect=_fake_scrap_doc_card):
                with mock.patch.object(mk_download, "_get_details", side_effect=_fake_get_details):
                    with mock.patch.object(mk_download, "_get_dh_params", return_value=None):
                        with mock.patch.object(mk_download, "_dh_key_exchange", side_effect=_fake_dh_key_exchange):
                            with mock.patch.object(mk_download, "_download_by_code", side_effect=_fake_download_by_code):
                                with mock.patch.object(mk_download, "ProgressWrapper", _DummyProgressWrapper):
                                    mk_download.download(limited=False, index_name=None)

        index_after_download = mk_utils.load_index_file()
        meta_after_download = index_after_download["/tt/ssearch/detail/abc"]
        self.assertEqual(meta_after_download["downloaded"], "full")
        self.assertFalse(meta_after_download["decrypted"])
        self.assertIn("enc_part_paths", meta_after_download)

        def _fake_decrypt_doc_parts(context):
            os.makedirs(context["work_dir"], exist_ok=True)
            out = os.path.join(context["work_dir"], "book_a.pdf")
            with open(out, "wb") as f:
                f.write(b"%PDF-1.4\n")
            return out

        with mock.patch.object(mk_decrypt, "read_config", return_value={"cfg": 1}):
            with mock.patch.object(mk_decrypt, "ProgressWrapper", _DummyProgressWrapper):
                with mock.patch.object(mk_decrypt, "decrypt_doc_parts", side_effect=_fake_decrypt_doc_parts):
                    with mock.patch.object(mk_decrypt, "_calculate_md5", return_value="md5-book-a"):
                        with mock.patch.object(mk_decrypt, "upload_doc", return_value=None):
                            with mock.patch.object(mk_decrypt, "upload_metadata", return_value=None):
                                mk_decrypt.decrypt()

        index_after_decrypt = mk_utils.load_index_file()
        meta_after_decrypt = index_after_decrypt["/tt/ssearch/detail/abc"]
        self.assertEqual(meta_after_decrypt["downloaded"], "full")
        self.assertTrue(meta_after_decrypt["decrypted"])
        self.assertNotIn("enc_part_paths", meta_after_decrypt)
        self.assertNotIn("format_url", meta_after_decrypt)
        self.assertNotIn("decryption_key", meta_after_decrypt)
        self.assertNotIn("decryption_key_iv", meta_after_decrypt)


if __name__ == "__main__":
    unittest.main()
