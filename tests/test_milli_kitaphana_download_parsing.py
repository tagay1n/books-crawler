import io
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

import download as mk_download  # noqa: E402


class _FakeTextResponse:
    def __init__(self, text, url="https://kitap.tatar.ru/tt/ssearch/detail/x/"):
        self.text = text
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeBinaryResponse:
    def __init__(self, headers, content):
        self.headers = headers
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _DummyProgress:
    def __init__(self):
        self.messages = []

    def main(self, message):
        self.messages.append(message)


def _make_doc_zip(doc):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("doc.json", json.dumps(doc))
    return stream.getvalue()


class MilliDownloadParsingTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="mk_download_parse_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_scrap_doc_card_parses_url_code_and_description(self):
        html = """
<html><body>
  <div class="record">
    Загл. с титул. экрана
    — Электронный ресурс [Электронный ресурс] УДК 123.45
    — Коллекция: test
    — Полезный текст
    <a href="http://kitap.tatar.ru/dl/nbrt-tatarica-Inv-L-1759455">Электронный ресурс</a>
  </div>
</body></html>
"""
        meta = {}
        with mock.patch.object(mk_download, "request", return_value=_FakeTextResponse(html)):
            mk_download._scrap_doc_card("/tt/ssearch/detail/x", meta, proxies=None)

        self.assertEqual(meta["doc_url"], "http://kitap.tatar.ru/dl/nbrt-tatarica-Inv-L-1759455")
        self.assertEqual(meta["download_code"], "nbrt_tatarica_Inv_L_1759455")
        self.assertEqual(meta["doc_card_url"], "https://kitap.tatar.ru/tt/ssearch/detail/x/")
        self.assertEqual(meta["classification"], "УДК 123.45")
        self.assertEqual(meta["integrated_description"], ["Полезный текст"])

    def test_scrap_doc_card_raises_when_no_download_link(self):
        html = '<html><body><div class="record">No links here</div></body></html>'
        meta = {}
        with mock.patch.object(mk_download, "request", return_value=_FakeTextResponse(html)):
            with self.assertRaises(ValueError):
                mk_download._scrap_doc_card("/tt/ssearch/detail/x", meta, proxies=None)

    def test_get_details_rejects_non_zip_content_type(self):
        ctx = {
            "meta": {"download_code": "book-1"},
            "progress": _DummyProgress(),
        }
        fake_resp = _FakeBinaryResponse(headers={"Content-Type": "application/json"}, content=b"{}")
        with mock.patch.object(mk_download, "request", return_value=fake_resp):
            with mock.patch.object(mk_download, "base_dir", self.tmp_dir):
                with self.assertRaises(ValueError):
                    mk_download._get_details(ctx)

    def test_get_details_extracts_doc_json_and_updates_context(self):
        ctx = {
            "meta": {"download_code": "book-2"},
            "progress": _DummyProgress(),
        }
        payload = {
            "formatUrl": "/download/{url}",
            "token2": "token-x",
            "keyUrl": "/tt/dl/key",
        }
        zip_bytes = _make_doc_zip(payload)
        fake_resp = _FakeBinaryResponse(headers={"Content-Type": "application/zip"}, content=zip_bytes)

        with mock.patch.object(mk_download, "request", return_value=fake_resp):
            with mock.patch.object(mk_download, "base_dir", self.tmp_dir):
                mk_download._get_details(ctx)

        self.assertEqual(ctx["meta"]["format_url"], "/download/{url}")
        self.assertEqual(ctx["token2"], "token-x")
        self.assertEqual(ctx["keyUrl"], "/tt/dl/key")
        self.assertEqual(ctx["work_dir"], os.path.join(self.tmp_dir, "book-2"))
        self.assertTrue(os.path.exists(os.path.join(ctx["work_dir"], "key_exchange_response", "doc.json")))


if __name__ == "__main__":
    unittest.main()
