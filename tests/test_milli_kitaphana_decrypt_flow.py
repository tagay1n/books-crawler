import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import decrypt as mk_decrypt  # noqa: E402


class _DummyProgressWrapper:
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def main(self, *_args, **_kwargs):
        return None


class MilliDecryptFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="mk_decrypt_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_decrypt_exits_without_dump_when_no_docs(self):
        with mock.patch.object(mk_decrypt, "backup_index_snapshot", return_value="/tmp/b.zip"):
            with mock.patch.object(mk_decrypt, "load_index_file", return_value={}):
                with mock.patch.object(mk_decrypt, "_get_not_decrypted_docs", return_value=[]):
                    with mock.patch.object(mk_decrypt, "dump_index") as m_dump:
                        with mock.patch.object(mk_decrypt, "read_config") as m_cfg:
                            mk_decrypt.decrypt()
        m_dump.assert_not_called()
        m_cfg.assert_not_called()

    def test_decrypt_marks_doc_and_writes_metadata_zip(self):
        meta = {
            "title": "Book",
            "download_code": "code_x",
            "downloaded": "limited",
            "decrypted": False,
            "enc_part_paths": [{"num": 0}],
            "format_url": "/fmt/{url}",
            "decryption_key": "a2V5",
            "decryption_key_iv": "aXY=",
            "integrated_description": ["desc"],
        }
        index = {"/card": meta}

        def _fake_decrypt_doc_parts(context):
            os.makedirs(context["work_dir"], exist_ok=True)
            pdf_path = os.path.join(context["work_dir"], "result.pdf")
            with open(pdf_path, "wb") as f:
                f.write(b"%PDF-1.4\n")
            return pdf_path

        with mock.patch.object(mk_decrypt, "base_dir", self.tmp_dir):
            with mock.patch.object(mk_decrypt, "backup_index_snapshot", return_value="/tmp/b.zip"):
                with mock.patch.object(mk_decrypt, "load_index_file", return_value=index):
                    with mock.patch.object(mk_decrypt, "read_config", return_value={"cfg": 1}):
                        with mock.patch.object(mk_decrypt, "ProgressWrapper", _DummyProgressWrapper):
                            with mock.patch.object(mk_decrypt, "decrypt_doc_parts", side_effect=_fake_decrypt_doc_parts):
                                with mock.patch.object(mk_decrypt, "_calculate_md5", return_value="md5x"):
                                    with mock.patch.object(mk_decrypt, "upload_doc") as m_upload_doc:
                                        with mock.patch.object(mk_decrypt, "upload_metadata") as m_upload_meta:
                                            with mock.patch.object(mk_decrypt, "dump_index") as m_dump:
                                                mk_decrypt.decrypt()

        self.assertTrue(meta["decrypted"])
        self.assertNotIn("enc_part_paths", meta)
        self.assertNotIn("format_url", meta)
        self.assertNotIn("decryption_key", meta)
        self.assertNotIn("decryption_key_iv", meta)

        m_upload_doc.assert_called_once()
        self.assertEqual(m_upload_doc.call_args.kwargs["is_limited"], True)
        m_upload_meta.assert_called_once()
        m_dump.assert_called_once_with(idx=index)

        meta_zip = os.path.join(self.tmp_dir, "code_x", "metadata.zip")
        self.assertTrue(os.path.exists(meta_zip))
        with zipfile.ZipFile(meta_zip, "r") as zf:
            payload = json.loads(zf.read("metadata.json").decode("utf-8"))
        self.assertNotIn("downloaded", payload)
        self.assertNotIn("decrypted", payload)
        self.assertNotIn("enc_part_paths", payload)
        self.assertNotIn("format_url", payload)
        self.assertNotIn("decryption_key", payload)
        self.assertNotIn("decryption_key_iv", payload)
        self.assertEqual(payload["download_code"], "code_x")

    def test_decrypt_preserves_recovery_fields_when_upload_fails(self):
        meta = {
            "title": "Book",
            "download_code": "code_x",
            "downloaded": "full",
            "decrypted": False,
            "enc_part_paths": [{"num": 0}],
            "format_url": "/fmt/{url}",
            "decryption_key": "a2V5",
            "decryption_key_iv": "aXY=",
            "integrated_description": ["desc"],
        }
        index = {"/card": meta}

        def _fake_decrypt_doc_parts(context):
            os.makedirs(context["work_dir"], exist_ok=True)
            pdf_path = os.path.join(context["work_dir"], "result.pdf")
            with open(pdf_path, "wb") as f:
                f.write(b"%PDF-1.4\n")
            return pdf_path

        with mock.patch.object(mk_decrypt, "base_dir", self.tmp_dir):
            with mock.patch.object(mk_decrypt, "backup_index_snapshot", return_value="/tmp/b.zip"):
                with mock.patch.object(mk_decrypt, "load_index_file", return_value=index):
                    with mock.patch.object(mk_decrypt, "read_config", return_value={"cfg": 1}):
                        with mock.patch.object(mk_decrypt, "ProgressWrapper", _DummyProgressWrapper):
                            with mock.patch.object(mk_decrypt, "decrypt_doc_parts", side_effect=_fake_decrypt_doc_parts):
                                with mock.patch.object(mk_decrypt, "_calculate_md5", return_value="md5x"):
                                    with mock.patch.object(mk_decrypt, "upload_doc", side_effect=RuntimeError("upload failed")):
                                        with mock.patch.object(mk_decrypt, "upload_metadata") as m_upload_meta:
                                            with mock.patch.object(mk_decrypt, "dump_index") as m_dump:
                                                mk_decrypt.decrypt()

        self.assertFalse(meta["decrypted"])
        self.assertEqual(meta["enc_part_paths"], [{"num": 0}])
        self.assertEqual(meta["format_url"], "/fmt/{url}")
        self.assertEqual(meta["decryption_key"], "a2V5")
        self.assertEqual(meta["decryption_key_iv"], "aXY=")
        m_upload_meta.assert_not_called()
        m_dump.assert_called_once_with(idx=index)


if __name__ == "__main__":
    unittest.main()
