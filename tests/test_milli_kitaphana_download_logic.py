import contextlib
import copy
import sys
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import download as mk_download  # noqa: E402


class _DummyProgressWrapper:
    def __init__(self, *_args, **_kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@contextlib.contextmanager
def _dummy_lock(_index_file):
    yield


class MilliDownloadLogicTests(unittest.TestCase):
    def test_download_part_task_sets_limited_when_url_missing(self):
        ctx = {"meta": {"access": "open"}, "work_dir": "/tmp", "progress": mock.Mock()}
        counter = iter([0])
        res = mk_download._download_part_task(ctx, part={}, num=0, counter=counter, total=1)
        self.assertIsNone(res)
        self.assertEqual(ctx["meta"]["access"], "limited")

    def test_download_part_task_prefers_reuse(self):
        ctx = {"meta": {"access": "open"}, "work_dir": "/tmp", "progress": mock.Mock()}
        counter = iter([0])
        with mock.patch.object(mk_download, "_try_reuse_local_part", return_value="/tmp/reused") as m_reuse:
            with mock.patch.object(mk_download, "download_part", side_effect=AssertionError("must not download")):
                res = mk_download._download_part_task(
                    ctx,
                    part={"url": "part1.zip"},
                    num=2,
                    counter=counter,
                    total=3,
                )
        self.assertEqual(res, (2, "part1.zip", "/tmp/reused"))
        m_reuse.assert_called_once()

    def test_download_part_task_downloads_when_no_reuse(self):
        ctx = {"meta": {"access": "open"}, "work_dir": "/tmp", "progress": mock.Mock()}
        counter = iter([0])
        with mock.patch.object(mk_download, "_try_reuse_local_part", return_value=None):
            with mock.patch.object(mk_download, "download_part", return_value="/tmp/downloaded"):
                res = mk_download._download_part_task(
                    ctx,
                    part={"url": "part2.zip"},
                    num=1,
                    counter=counter,
                    total=3,
                )
        self.assertEqual(res, (1, "part2.zip", "/tmp/downloaded"))

    def test_download_sets_downloaded_and_decrypted_flags_for_open_doc(self):
        meta = {"title": "Book", "download_code": "code_1", "doc_card_url": "u"}
        global_index = {"/card": meta}

        with mock.patch.object(mk_download, "backup_index_snapshot", return_value="/tmp/b.zip"):
            with mock.patch.object(mk_download, "get_index_file_loc", return_value="/tmp/index.json"):
                with mock.patch.object(mk_download, "load_index_file", return_value=global_index):
                    with mock.patch.object(mk_download, "get_not_downloaded_docs", return_value=[("/card", meta)]):
                        with mock.patch.object(mk_download, "read_config", return_value={}):
                            with mock.patch.object(mk_download, "_scrap_doc_card", return_value=None):
                                with mock.patch.object(mk_download, "_get_details", return_value=None):
                                    with mock.patch.object(mk_download, "_get_dh_params", return_value=None):
                                        with mock.patch.object(mk_download, "_dh_key_exchange", return_value=None):
                                            with mock.patch.object(mk_download, "dump_index", return_value=None):
                                                with mock.patch.object(mk_download, "open_lock", _dummy_lock):
                                                    with mock.patch.object(mk_download, "ProgressWrapper", _DummyProgressWrapper):
                                                        def _fake_download_by_code(ctx):
                                                            ctx["meta"]["access"] = "open"
                                                            ctx["meta"]["enc_part_paths"] = [{"num": 0}]
                                                        with mock.patch.object(mk_download, "_download_by_code", side_effect=_fake_download_by_code):
                                                            mk_download.download(limited=False, index_name=None)

        self.assertEqual(meta["downloaded"], "full")
        self.assertFalse(meta["decrypted"])

    def test_download_sets_downloaded_and_decrypted_flags_for_limited_doc(self):
        meta = {"title": "Book", "download_code": "code_2", "doc_card_url": "u"}
        global_index = {"/card": meta}

        with mock.patch.object(mk_download, "backup_index_snapshot", return_value="/tmp/b.zip"):
            with mock.patch.object(mk_download, "get_index_file_loc", return_value="/tmp/index.json"):
                with mock.patch.object(mk_download, "load_index_file", return_value=global_index):
                    with mock.patch.object(mk_download, "get_not_downloaded_docs", return_value=[("/card", meta)]):
                        with mock.patch.object(mk_download, "read_config", return_value={}):
                            with mock.patch.object(mk_download, "_scrap_doc_card", return_value=None):
                                with mock.patch.object(mk_download, "_get_details", return_value=None):
                                    with mock.patch.object(mk_download, "_get_dh_params", return_value=None):
                                        with mock.patch.object(mk_download, "_dh_key_exchange", return_value=None):
                                            with mock.patch.object(mk_download, "dump_index", return_value=None):
                                                with mock.patch.object(mk_download, "open_lock", _dummy_lock):
                                                    with mock.patch.object(mk_download, "ProgressWrapper", _DummyProgressWrapper):
                                                        def _fake_download_by_code(ctx):
                                                            ctx["meta"]["access"] = "limited"
                                                            ctx["meta"]["enc_part_paths"] = [{"num": 0}]
                                                        with mock.patch.object(mk_download, "_download_by_code", side_effect=_fake_download_by_code):
                                                            mk_download.download(limited=False, index_name=None)

        self.assertEqual(meta["downloaded"], "limited")
        self.assertFalse(meta["decrypted"])

    def test_download_worker_index_updates_worker_and_global_files(self):
        global_index_file = "/tmp/global.json"
        worker_index_file = "/tmp/worker.json"
        global_store = {
            "/card": {"title": "Book", "download_code": "code_3", "doc_card_url": "u", "downloaded": None}
        }
        worker_store = {
            "/card": {"title": "Book", "download_code": "code_3", "doc_card_url": "u", "downloaded": None}
        }
        files = {
            global_index_file: global_store,
            worker_index_file: worker_store,
        }

        def _fake_load(index_file=None):
            if index_file is None:
                index_file = global_index_file
            return copy.deepcopy(files[index_file])

        dump_calls = []

        def _fake_dump(idx, index_file=None):
            target = index_file or global_index_file
            files[target] = copy.deepcopy(idx)
            dump_calls.append(target)

        def _fake_download_by_code(ctx):
            ctx["meta"]["access"] = "open"
            ctx["meta"]["enc_part_paths"] = [{"num": 0}]

        with mock.patch.object(mk_download, "backup_index_snapshot", return_value="/tmp/b.zip"):
            with mock.patch.object(mk_download, "get_index_file_loc", return_value=global_index_file):
                with mock.patch.object(mk_download, "get_list_file_loc", return_value=worker_index_file):
                    with mock.patch.object(mk_download, "load_index_file", side_effect=_fake_load):
                        with mock.patch.object(mk_download, "dump_index", side_effect=_fake_dump):
                            with mock.patch.object(mk_download, "read_config", return_value={}):
                                with mock.patch.object(mk_download, "_scrap_doc_card", return_value=None):
                                    with mock.patch.object(mk_download, "_get_details", return_value=None):
                                        with mock.patch.object(mk_download, "_get_dh_params", return_value=None):
                                            with mock.patch.object(mk_download, "_dh_key_exchange", return_value=None):
                                                with mock.patch.object(mk_download, "_download_by_code", side_effect=_fake_download_by_code):
                                                    with mock.patch.object(mk_download, "open_lock", _dummy_lock):
                                                        with mock.patch.object(mk_download, "ProgressWrapper", _DummyProgressWrapper):
                                                            mk_download.download(limited=False, index_name="worker")

        self.assertEqual(files[worker_index_file]["/card"]["downloaded"], "full")
        self.assertFalse(files[worker_index_file]["/card"]["decrypted"])
        self.assertEqual(files[global_index_file]["/card"]["downloaded"], "full")
        self.assertFalse(files[global_index_file]["/card"]["decrypted"])
        self.assertIn(worker_index_file, dump_calls)
        self.assertIn(global_index_file, dump_calls)


if __name__ == "__main__":
    unittest.main()
