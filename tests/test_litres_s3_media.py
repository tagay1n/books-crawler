import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LITRES_DIR = ROOT / "litres"
LITRES_S3_MEDIA = ROOT / "litres" / "s3_media.py"
if str(LITRES_DIR) not in sys.path:
    sys.path.insert(0, str(LITRES_DIR))
spec = importlib.util.spec_from_file_location("litres_s3_media_for_tests", LITRES_S3_MEDIA)
litres_s3_media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(litres_s3_media)


class _FakeS3Client:
    def __init__(self):
        self.uploads = []

    def upload_file(self, *args, **kwargs):
        self.uploads.append((args, kwargs))


class LitresS3MediaTests(unittest.TestCase):
    def test_upload_media_to_s3_exports_rewritten_markdown_with_deterministic_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "markdown-s3"
            markdown_root = root / "markdown"
            markdown_root.mkdir()
            book_name = "Китап - Book - Author"
            book_dir = root / book_name
            media_dir = book_dir / "media"
            media_dir.mkdir(parents=True)
            image = media_dir / "cover image.png"
            image.write_bytes(b"png")
            second_image = media_dir / "page.jpeg"
            second_image.write_bytes(b"jpg")
            markdown = book_dir / f"{book_name}.md"
            markdown.write_text(
                "![cover](media/cover image.png)\n"
                "![page](media/page.jpeg)\n"
                "![remote](https://example.test/image.png)\n",
                encoding="utf-8",
            )
            client = _FakeS3Client()
            config = {
                "s3": {
                    "endpoint_url": "https://storage.example.test",
                    "aws_access_key_id": "key",
                    "aws_secret_access_key": "secret",
                    "bucket": "bucket",
                }
            }

            def _get_in_workdir(path):
                if path == litres_s3_media.MARKDOWN_DIR:
                    return str(markdown_root)
                if path == litres_s3_media.OUTPUT_DIR:
                    return str(output)
                return str(root / path)

            book_dir.rename(markdown_root / book_dir.name)
            markdown = markdown_root / book_dir.name / markdown.name
            image = markdown_root / book_dir.name / "media" / image.name
            second_image = markdown_root / book_dir.name / "media" / second_image.name

            with (
                mock.patch.object(litres_s3_media, "read_config", return_value=config),
                mock.patch.object(litres_s3_media, "get_in_workdir", side_effect=_get_in_workdir),
                mock.patch.object(litres_s3_media, "_create_s3_client", return_value=client),
            ):
                litres_s3_media.upload_media_to_s3()

            doc_id = hashlib.md5(book_name.encode("utf-8")).hexdigest()
            self.assertEqual(len(client.uploads), 2)
            self.assertEqual(Path(client.uploads[0][0][0]).resolve(), image.resolve())
            self.assertEqual(client.uploads[0][0][1:3], ("bucket", f"{doc_id}-0.png"))
            self.assertEqual(client.uploads[0][1]["ExtraArgs"]["ContentType"], "image/png")
            self.assertEqual(Path(client.uploads[1][0][0]).resolve(), second_image.resolve())
            self.assertEqual(client.uploads[1][0][1:3], ("bucket", f"{doc_id}-1.jpeg"))
            self.assertEqual(client.uploads[1][1]["ExtraArgs"]["ContentType"], "image/jpeg")
            self.assertEqual(
                (output / f"{doc_id}.md").read_text(encoding="utf-8"),
                f"![cover](https://storage.example.test/bucket/{doc_id}-0.png)\n"
                f"![page](https://storage.example.test/bucket/{doc_id}-1.jpeg)\n"
                "![remote](https://example.test/image.png)\n",
            )
            self.assertIn("media/cover image.png", markdown.read_text(encoding="utf-8"))
            manifest = json.loads((output / "_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest[0]["document_id"], doc_id)

    def test_required_s3_config_rejects_placeholders(self):
        with self.assertRaisesRegex(ValueError, "s3.bucket"):
            litres_s3_media._required_config({"bucket": "<SET ME>"}, "bucket")


if __name__ == "__main__":
    unittest.main()
