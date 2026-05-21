"""Upload Litres markdown media files to S3-compatible storage and export rewritten markdown."""

import hashlib
import json
import mimetypes
import re
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlparse

from boto3 import Session
from rich.progress import track

from utils import get_in_workdir, read_config

MARKDOWN_DIR = "../__artifacts/litres/markdown"
OUTPUT_DIR = "../__artifacts/litres/markdown-s3"
IMAGE_LINK_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def upload_media_to_s3():
    """
    Upload media files from Litres markdown folders and export markdown with S3 image links.
    """
    root = Path(get_in_workdir(MARKDOWN_DIR)).resolve()
    if not root.exists():
        raise ValueError(f"Markdown directory does not exist: {root}")
    output_root = Path(get_in_workdir(OUTPUT_DIR)).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    config = read_config()["s3"]
    client = _create_s3_client(config)
    bucket = _required_config(config, "bucket")
    endpoint_url = _required_config(config, "endpoint_url").rstrip("/")

    markdown_files = sorted(path for path in root.rglob("*.md") if path.is_file())
    print(f"Processing {len(markdown_files)} Litres markdown file(s)")
    print(f"Export directory: {output_root}")
    uploaded = 0
    exported = 0
    manifest = []
    for markdown_file in track(markdown_files, description="Uploading Litres media"):
        doc_id = _document_id(markdown_file)
        media_files = _media_files_for_markdown(markdown_file)
        print(f"Processing book: {markdown_file.parent.name}")
        print(f"Document id: {doc_id}")
        print(f"Found {len(media_files)} media file(s)")
        url_by_relative_path = {}
        uploaded_images = []
        for image_number, media_file in enumerate(media_files):
            relative_path = media_file.relative_to(markdown_file.parent)
            key = _image_key(doc_id, image_number, media_file)
            _upload_file(client, bucket, key, media_file)
            url = _public_url(endpoint_url, bucket, key)
            url_by_relative_path[_normalize_relative_url(relative_path)] = url
            uploaded_images.append(
                {
                    "source": str(relative_path),
                    "s3_key": key,
                    "url": url,
                }
            )
            uploaded += 1
        output_file = output_root / f"{doc_id}.md"
        _write_rewritten_markdown(markdown_file, output_file, url_by_relative_path)
        print(f"Exported markdown: {output_file}")
        manifest.append(
            {
                "document_id": doc_id,
                "source_markdown": str(markdown_file),
                "output_markdown": str(output_file),
                "images": uploaded_images,
            }
        )
        exported += 1

    _write_manifest(output_root, manifest)
    print(f"Uploaded {uploaded} media file(s)")
    print(f"Exported {exported} markdown file(s) to {output_root}")


def _create_s3_client(config):
    return Session().client(
        service_name="s3",
        aws_access_key_id=_required_config(config, "aws_access_key_id"),
        aws_secret_access_key=_required_config(config, "aws_secret_access_key"),
        endpoint_url=_required_config(config, "endpoint_url"),
    )


def _required_config(config, key):
    value = config.get(key)
    if not value or value == "<SET ME>":
        raise ValueError(f"s3.{key} is not set in litres/config.yaml")
    return value


def _media_files_for_markdown(markdown_file):
    media_dir = markdown_file.parent / "media"
    if not media_dir.exists():
        return []
    return sorted(path for path in media_dir.rglob("*") if path.is_file())


def _document_id(markdown_file):
    return hashlib.md5(markdown_file.parent.name.encode("utf-8")).hexdigest()


def _image_key(doc_id, image_number, path):
    return f"{doc_id}-{image_number}{path.suffix.lower()}"


def _upload_file(client, bucket, key, path):
    extra_args = {}
    if content_type := mimetypes.guess_type(path.name)[0]:
        extra_args["ContentType"] = content_type
    if extra_args:
        client.upload_file(str(path), bucket, key, ExtraArgs=extra_args)
    else:
        client.upload_file(str(path), bucket, key)


def _public_url(endpoint_url, bucket, key):
    return f"{endpoint_url}/{quote(bucket)}/{quote(key)}"


def _write_rewritten_markdown(markdown_file, output_file, url_by_relative_path):
    original = markdown_file.read_text(encoding="utf-8")

    def _replace(match):
        alt, url = match.groups()
        normalized = _normalize_relative_url(url)
        if _is_absolute_url(url) or normalized not in url_by_relative_path:
            return match.group(0)
        return f"![{alt}]({url_by_relative_path[normalized]})"

    updated = IMAGE_LINK_RE.sub(_replace, original)
    output_file.write_text(updated, encoding="utf-8")


def _normalize_relative_url(value):
    parsed = urlparse(str(value))
    return str(PurePosixPath(unquote(parsed.path)))


def _is_absolute_url(value):
    parsed = urlparse(value)
    return bool(parsed.scheme or parsed.netloc)


def _write_manifest(output_root, manifest):
    (output_root / "_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
