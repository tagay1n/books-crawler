import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import requests


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import utils as mk_utils  # noqa: E402


class _FakeResponse:
    def __init__(self, error=None):
        self.error = error
        self.raise_called = False

    def raise_for_status(self):
        self.raise_called = True
        if self.error:
            raise self.error


class MilliUtilsRequestLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="mk_utils_req_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_request_passes_expected_args_and_headers(self):
        response = _FakeResponse()
        with mock.patch.object(mk_utils.requests, "request", return_value=response) as m_req:
            result = mk_utils.request(
                method="GET",
                url="https://example.test/a",
                params={"p": 1},
                data={"d": 2},
                stream=True,
                headers={"X-Test": "1"},
                proxies={"http": "http://proxy"},
            )

        self.assertIs(result, response)
        kwargs = m_req.call_args.kwargs
        self.assertEqual(kwargs["verify"], False)
        self.assertEqual(kwargs["timeout"], 30)
        self.assertEqual(kwargs["params"], {"p": 1})
        self.assertEqual(kwargs["data"], {"d": 2})
        self.assertEqual(kwargs["stream"], True)
        self.assertEqual(kwargs["proxies"], {"http": "http://proxy"})
        self.assertEqual(kwargs["headers"]["X-Test"], "1")
        self.assertIn("User-Agent", kwargs["headers"])
        self.assertTrue(response.raise_called)

    def test_request_raises_on_http_status_error(self):
        response = _FakeResponse(error=requests.HTTPError("bad status"))
        with mock.patch.object(mk_utils.requests, "request", return_value=response):
            with self.assertRaises(requests.HTTPError):
                mk_utils.request("GET", "https://example.test/b")

    def test_request_propagates_transport_error(self):
        with mock.patch.object(mk_utils.requests, "request", side_effect=requests.RequestException("boom")):
            with self.assertRaises(requests.RequestException):
                mk_utils.request("GET", "https://example.test/c")

    def test_open_lock_waits_for_other_holder_and_cleans_up(self):
        index_file = os.path.join(self.tmp_dir, "index.json")
        lock_file = f"{index_file}.lock"
        first_acquired = threading.Event()
        order = []
        timings = {}

        def worker_1():
            with mk_utils.open_lock(index_file, wait_seconds=0.01):
                order.append("t1_acquired")
                first_acquired.set()
                time.sleep(0.2)
                order.append("t1_released")

        def worker_2():
            first_acquired.wait(timeout=2)
            start = time.monotonic()
            with mk_utils.open_lock(index_file, wait_seconds=0.01):
                timings["waited"] = time.monotonic() - start
                order.append("t2_acquired")

        t1 = threading.Thread(target=worker_1)
        t2 = threading.Thread(target=worker_2)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        self.assertIn("t1_acquired", order)
        self.assertIn("t1_released", order)
        self.assertIn("t2_acquired", order)
        self.assertLess(order.index("t1_released"), order.index("t2_acquired"))
        self.assertGreaterEqual(timings["waited"], 0.15)
        self.assertFalse(os.path.exists(lock_file))


if __name__ == "__main__":
    unittest.main()
