import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from typer.testing import CliRunner


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import cli as mk_cli  # noqa: E402


class MilliCliTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_download_help_has_limited_option(self):
        res = self.runner.invoke(mk_cli.app, ["download", "--help"])
        self.assertEqual(res.exit_code, 0, res.output)
        self.assertIn("--limited", res.output)
        self.assertNotIn("--with-limited", res.output)

    def test_download_command_forwards_limited_and_index_name(self):
        fake_download = types.ModuleType("download")
        called = {}

        def _fake_download_fn(limited, index_name):
            called["limited"] = limited
            called["index_name"] = index_name

        fake_download.download = _fake_download_fn

        with mock.patch.dict(sys.modules, {"download": fake_download}):
            res = self.runner.invoke(
                mk_cli.app, ["download", "--limited", "--index-name", "part-1"]
            )

        self.assertEqual(res.exit_code, 0, res.output)
        self.assertEqual(called, {"limited": True, "index_name": "part-1"})

    def test_index_command_wires_to_index_module(self):
        fake_index = types.ModuleType("index")
        called = {"count": 0}

        def _fake_index_fn():
            called["count"] += 1

        fake_index.index = _fake_index_fn
        with mock.patch.dict(sys.modules, {"index": fake_index}):
            res = self.runner.invoke(mk_cli.app, ["index"])

        self.assertEqual(res.exit_code, 0, res.output)
        self.assertEqual(called["count"], 1)

    def test_decrypt_command_wires_to_decrypt_module(self):
        fake_decrypt = types.ModuleType("decrypt")
        called = {"count": 0}

        def _fake_decrypt_fn():
            called["count"] += 1

        fake_decrypt.decrypt = _fake_decrypt_fn
        with mock.patch.dict(sys.modules, {"decrypt": fake_decrypt}):
            res = self.runner.invoke(mk_cli.app, ["decrypt"])

        self.assertEqual(res.exit_code, 0, res.output)
        self.assertEqual(called["count"], 1)

    def test_merge_index_command_forwards_path(self):
        fake_merge = types.ModuleType("merge_index")
        called = {}

        def _fake_merge_fn(path):
            called["path"] = path

        fake_merge.merge_indexes = _fake_merge_fn
        with mock.patch.dict(sys.modules, {"merge_index": fake_merge}):
            res = self.runner.invoke(mk_cli.app, ["merge-index", "x.json"])

        self.assertEqual(res.exit_code, 0, res.output)
        self.assertEqual(called["path"], "x.json")

    def test_split_command_forwards_options(self):
        fake_split = types.ModuleType("split_index")
        called = {}

        def _fake_split_fn(parts, dest, prefix):
            called["parts"] = parts
            called["dest"] = dest
            called["prefix"] = prefix

        fake_split.split_lists = _fake_split_fn
        with mock.patch.dict(sys.modules, {"split_index": fake_split}):
            res = self.runner.invoke(
                mk_cli.app,
                ["split", "--parts", "3", "--dest", "tmp/sub", "--prefix", "pfx"],
            )

        self.assertEqual(res.exit_code, 0, res.output)
        self.assertEqual(called, {"parts": 3, "dest": "tmp/sub", "prefix": "pfx"})


if __name__ == "__main__":
    unittest.main()
