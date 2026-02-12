import io
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

import download as mk_download  # noqa: E402
import utils as mk_utils  # noqa: E402


class _DummyAux:
    def update(self, *args, **kwargs):
        return None

    def stop_task(self, *args, **kwargs):
        return None


class _DummyProgress:
    def __init__(self):
        self._aux = _DummyAux()

    def download(self, _part):
        return "task"


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_content(self, chunk_size=1024):
        for i in range(0, len(self._payload), chunk_size):
            yield self._payload[i:i + chunk_size]


def _zip_bytes_with_enc(enc_bytes: bytes) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("enc.dat", enc_bytes)
    return stream.getvalue()


class MilliDownloadReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="mk_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_download_part_uses_part_suffix_and_extracts(self):
        zip_payload = _zip_bytes_with_enc(b"A" * 16)
        ctx = {
            "work_dir": self.tmp_dir,
            "meta": {"format_url": "/download/{url}"},
            "progress": _DummyProgress(),
        }

        with mock.patch.object(mk_utils, "request", return_value=_FakeResponse(zip_payload)):
            unzip_dir = mk_utils.download_part(ctx, "part1.zip")

        enc_zip_path, enc_zip_part_path, _, enc_file_path = mk_utils.get_part_paths(self.tmp_dir, "part1.zip")
        self.assertEqual(unzip_dir, os.path.join(self.tmp_dir, "part1_encrypted"))
        self.assertTrue(os.path.exists(enc_zip_path))
        self.assertFalse(os.path.exists(enc_zip_part_path))
        self.assertTrue(os.path.exists(enc_file_path))

    def test_download_part_rejects_invalid_zip_content(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("wrong.bin", b"123")
        zip_payload = stream.getvalue()
        ctx = {
            "work_dir": self.tmp_dir,
            "meta": {"format_url": "/download/{url}"},
            "progress": _DummyProgress(),
        }

        with mock.patch.object(mk_utils, "request", return_value=_FakeResponse(zip_payload)):
            with self.assertRaises(ValueError):
                mk_utils.download_part(ctx, "part2.zip")

    def test_is_valid_encrypted_part(self):
        missing = os.path.join(self.tmp_dir, "missing.dat")
        self.assertFalse(mk_utils.is_valid_encrypted_part(missing))

        path = os.path.join(self.tmp_dir, "enc.dat")
        with open(path, "wb") as f:
            f.write(b"A" * 15)
        self.assertFalse(mk_utils.is_valid_encrypted_part(path))

        with open(path, "wb") as f:
            f.write(b"A" * 16)
        self.assertTrue(mk_utils.is_valid_encrypted_part(path))

    def test_reuse_prefers_existing_valid_enc_dat(self):
        _, _, enc_unzip_dir, enc_file_path = mk_utils.get_part_paths(self.tmp_dir, "part3.zip")
        os.makedirs(enc_unzip_dir, exist_ok=True)
        with open(enc_file_path, "wb") as f:
            f.write(b"A" * 16)

        reused = mk_download._try_reuse_local_part({"work_dir": self.tmp_dir}, "part3.zip")
        self.assertEqual(reused, os.path.normpath(enc_unzip_dir))

    def test_reuse_extracts_from_existing_zip(self):
        enc_zip_path, _, enc_unzip_dir, enc_file_path = mk_utils.get_part_paths(self.tmp_dir, "part4.zip")
        with zipfile.ZipFile(enc_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("enc.dat", b"A" * 32)

        reused = mk_download._try_reuse_local_part({"work_dir": self.tmp_dir}, "part4.zip")
        self.assertEqual(reused, os.path.normpath(enc_unzip_dir))
        self.assertTrue(os.path.exists(enc_file_path))

    def test_reuse_ignores_invalid_zip_or_payload(self):
        enc_zip_path, _, _, _ = mk_utils.get_part_paths(self.tmp_dir, "part5.zip")
        with zipfile.ZipFile(enc_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("enc.dat", b"A" * 15)

        reused = mk_download._try_reuse_local_part({"work_dir": self.tmp_dir}, "part5.zip")
        self.assertIsNone(reused)

    def test_reuse_removes_stale_part_file(self):
        _, enc_zip_part_path, _, _ = mk_utils.get_part_paths(self.tmp_dir, "part6.zip")
        os.makedirs(os.path.dirname(enc_zip_part_path), exist_ok=True)
        with open(enc_zip_part_path, "wb") as f:
            f.write(b"partial")

        reused = mk_download._try_reuse_local_part({"work_dir": self.tmp_dir}, "part6.zip")
        self.assertIsNone(reused)
        self.assertFalse(os.path.exists(enc_zip_part_path))


if __name__ == "__main__":
    unittest.main()
