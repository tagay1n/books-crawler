import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import upload_docs as mk_upload  # noqa: E402


class _FakeConnection:
    def __init__(self, execute_error=None):
        self.execute_calls = []
        self.execute_error = execute_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params):
        self.execute_calls.append((statement, params))
        if self.execute_error:
            raise self.execute_error


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

    def test_persist_upstream_metadata_inserts_jsonb_record(self):
        connection = _FakeConnection()
        payload = {"title": "Kitap", "download_code": "abc"}

        with mock.patch.object(mk_upload.psycopg, "connect", return_value=connection) as connect:
            mk_upload.persist_upstream_metadata(
                "a" * 32,
                payload,
                "postgresql://writer:secret@example.test/defaultdb?sslmode=require",
            )

        connect.assert_called_once_with(
            "postgresql://writer:secret@example.test/defaultdb?sslmode=require"
        )
        self.assertEqual(len(connection.execute_calls), 1)
        statement, params = connection.execute_calls[0]
        self.assertIn("INSERT INTO monocorpus.library_upstream_metadata", statement)
        self.assertNotIn("ON CONFLICT", statement)
        self.assertEqual(params[0], "a" * 32)
        self.assertEqual(params[1].obj, payload)

    def test_persist_upstream_metadata_requires_database_url(self):
        with self.assertRaisesRegex(ValueError, "database_url"):
            mk_upload.persist_upstream_metadata("a" * 32, {}, "")
        with self.assertRaisesRegex(ValueError, "database_url"):
            mk_upload.persist_upstream_metadata("a" * 32, {}, "<SET ME>")

    def test_persist_upstream_metadata_propagates_duplicate_error(self):
        duplicate = RuntimeError("duplicate key")
        connection = _FakeConnection(execute_error=duplicate)

        with mock.patch.object(mk_upload.psycopg, "connect", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "duplicate key"):
                mk_upload.persist_upstream_metadata(
                    "a" * 32,
                    {"title": "Kitap"},
                    "postgresql://db",
                )


if __name__ == "__main__":
    unittest.main()
