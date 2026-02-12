import base64
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


class _FakeAux:
    def update(self, *args, **kwargs):
        return None

    def stop_task(self, *args, **kwargs):
        return None


class _DummyProgress:
    def __init__(self):
        self._aux = _FakeAux()

    def decrypt(self, _part, _total_size):
        return "task"


class _IdentityCipher:
    def decrypt(self, chunk):
        return chunk


class MilliDecryptFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="mk_dec_file_")
        self.enc_dir = os.path.join(self.tmp_dir, "enc")
        os.makedirs(self.enc_dir, exist_ok=True)
        with open(os.path.join(self.enc_dir, "enc.dat"), "wb") as f:
            f.write(b"A" * 16)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _base_context(self):
        return {
            "work_dir": self.tmp_dir,
            "progress": _DummyProgress(),
            "meta": {
                "decryption_key": base64.b64encode(b"k" * 16).decode("ascii"),
                "decryption_key_iv": base64.b64encode(b"i" * 16).decode("ascii"),
            },
        }

    def test_decrypt_file_non_zip_returns_decrypted_file_path(self):
        context = self._base_context()
        with mock.patch.object(mk_decrypt.AES, "new", return_value=_IdentityCipher()):
            with mock.patch.object(mk_decrypt, "unpad", return_value=b"PDFDATA"):
                out = mk_decrypt._decrypt_file(context, "part1.pdf", self.enc_dir)

        self.assertTrue(out.endswith("part1_decrypted.pdf"))
        with open(out, "rb") as f:
            self.assertEqual(f.read(), b"PDFDATA")

    def test_decrypt_file_raises_for_invalid_padding(self):
        context = self._base_context()
        with mock.patch.object(mk_decrypt.AES, "new", return_value=_IdentityCipher()):
            with mock.patch.object(mk_decrypt, "unpad", side_effect=ValueError("Padding is incorrect.")):
                with self.assertRaises(ValueError):
                    mk_decrypt._decrypt_file(context, "part2.pdf", self.enc_dir)


if __name__ == "__main__":
    unittest.main()
