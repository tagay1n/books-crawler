import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import upload_docs as mk_upload  # noqa: E402


class _FakeS3Client:
    def __init__(self, doc_exists):
        self.doc_exists = doc_exists
        self.upload_calls = []

    def upload_file(self, src, bucket, key):
        self.upload_calls.append((src, bucket, key))

    def list_objects_v2(self, Bucket, Prefix, MaxKeys):
        if self.doc_exists:
            return {"Contents": [{"Key": Prefix}]}
        return {}


class _FakeSession:
    def __init__(self, client):
        self._client = client
        self.client_calls = []

    def client(self, **kwargs):
        self.client_calls.append(kwargs)
        return self._client


class MilliUploadDocsTests(unittest.TestCase):
    def test_upload_doc_routes_into_limited_or_full_directory(self):
        config = {"yandex": {"disk": {"target_dir": "/root/target", "oauth_token": "tok"}}}

        fake_client = mock.Mock()
        fake_client.upload_or_replace.return_value = ("x", "y")
        with mock.patch.object(mk_upload, "YaDisk", return_value=fake_client):
            mk_upload.upload_doc("/tmp/a.pdf", config=config, is_limited=True)
            mk_upload.upload_doc("/tmp/b.pdf", config=config, is_limited=False)

        self.assertEqual(fake_client.upload_or_replace.call_count, 2)
        self.assertEqual(
            fake_client.upload_or_replace.call_args_list[0].kwargs["remote_dir"],
            "/root/target/limited",
        )
        self.assertEqual(
            fake_client.upload_or_replace.call_args_list[1].kwargs["remote_dir"],
            "/root/target/full",
        )

    def test_upload_metadata_uploads_doc_only_when_missing(self):
        config = {
            "yandex": {
                "cloud": {
                    "aws_access_key_id": "k",
                    "aws_secret_access_key": "s",
                    "bucket": {
                        "upstream_metadata": "meta-bucket",
                        "document": "doc-bucket",
                    },
                }
            }
        }
        context = {"config": config, "md5": "abc123"}

        # Missing document in bucket => metadata + pdf are uploaded.
        client_missing = _FakeS3Client(doc_exists=False)
        sess_missing = _FakeSession(client_missing)
        with mock.patch.object(mk_upload, "Session", return_value=sess_missing):
            mk_upload.upload_metadata("/tmp/meta.zip", "/tmp/doc.pdf", context=context)

        self.assertEqual(
            client_missing.upload_calls,
            [
                ("/tmp/meta.zip", "meta-bucket", "abc123.zip"),
                ("/tmp/doc.pdf", "doc-bucket", "abc123.pdf"),
            ],
        )

        # Existing document in bucket => metadata only.
        client_exists = _FakeS3Client(doc_exists=True)
        sess_exists = _FakeSession(client_exists)
        with mock.patch.object(mk_upload, "Session", return_value=sess_exists):
            mk_upload.upload_metadata("/tmp/meta.zip", "/tmp/doc.pdf", context=context)

        self.assertEqual(
            client_exists.upload_calls,
            [
                ("/tmp/meta.zip", "meta-bucket", "abc123.zip"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
