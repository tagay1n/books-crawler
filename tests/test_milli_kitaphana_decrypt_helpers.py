import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import decrypt as mk_decrypt  # noqa: E402


class MilliDecryptHelpersTests(unittest.TestCase):
    def test_get_not_decrypted_docs(self):
        idx = {
            "/a": {"decrypted": False, "enc_part_paths": [{"num": 1}]},
            "/b": {"decrypted": True, "enc_part_paths": [{"num": 1}]},
            "/c": {"decrypted": False},
            "/d": {"enc_part_paths": [{"num": 2}]},
        }
        docs = mk_decrypt._get_not_decrypted_docs(idx)
        self.assertEqual({p for p, _ in docs}, {"/a", "/d"})

    def test_safe_filename_strips_invalid_chars(self):
        src = 'bad<>:"/\\\\|?*name.'
        out = mk_decrypt._safe_filename(src)
        self.assertEqual(out, "bad----------name")

    def test_safe_filename_reserved_name(self):
        out = mk_decrypt._safe_filename("con")
        self.assertEqual(out, "_con")

    def test_build_output_filename_includes_code_and_extension(self):
        meta = {"title": "Пример китап", "download_code": "abc_123"}
        out = mk_decrypt._build_output_filename(meta)
        self.assertTrue(out.endswith(".pdf"))
        self.assertIn("__abc_123", out)

    def test_build_output_filename_capped_length(self):
        meta = {"title": "a" * 500, "download_code": "x"}
        out = mk_decrypt._build_output_filename(meta)
        self.assertTrue(out.endswith(".pdf"))
        self.assertLessEqual(len(out), 104)


if __name__ == "__main__":
    unittest.main()
