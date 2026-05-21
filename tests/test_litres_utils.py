import importlib.util
import json
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LITRES_DIR = ROOT / "litres"
LITRES_UTILS = ROOT / "litres" / "utils.py"
if str(LITRES_DIR) not in sys.path:
    sys.path.insert(0, str(LITRES_DIR))
spec = importlib.util.spec_from_file_location("litres_utils_for_tests", LITRES_UTILS)
litres_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(litres_utils)


class LitresUtilsTests(unittest.TestCase):
    def test_dump_json_atomic_writes_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "index.json"

            litres_utils.dump_json_atomic({"book": {"title": "Әлифба"}}, str(output))

            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                {"book": {"title": "Әлифба"}},
            )
            self.assertEqual(list(Path(tmp).glob("*.tmp.*")), [])

    def test_get_sid_reads_config_sid(self):
        with mock.patch.object(litres_utils, "read_config", return_value={"sid": "abc"}):
            self.assertEqual(litres_utils.get_sid(), "abc")

    def test_get_sid_raises_without_config_sid(self):
        with mock.patch.object(litres_utils, "read_config", return_value={}):
            with self.assertRaisesRegex(ValueError, "sid is not set"):
                litres_utils.get_sid()


if __name__ == "__main__":
    unittest.main()
