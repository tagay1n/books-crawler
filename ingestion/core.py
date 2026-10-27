import hashlib
import os
import shutil
import tempfile
from dataclasses import replace
from email.message import Message
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import requests
from urllib3.exceptions import HTTPError as TransportError

from .discovery import discover
from .documents import DOCUMENT_EXTENSIONS, same_origin
from .network import Budget, BudgetStop, HTTP, InvalidDocument
from .registry import SOURCES
from .state import Manifest, atomic_json, now, source_lock


MIME_EXTENSIONS = {
    "application/pdf": ".pdf", "image/vnd.djvu": ".djvu", "image/x-djvu": ".djvu",
    "application/epub+zip": ".epub", "text/plain": ".txt", "text/html": ".html",
    "application/msword": ".doc", "application/rtf": ".rtf", "text/rtf": ".rtf",
    "application/vnd.ms-powerpoint": ".ppt", "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.oasis.opendocument.text": ".odt",
    "application/vnd.oasis.opendocument.presentation": ".odp",
    "application/vnd.oasis.opendocument.spreadsheet": ".ods",
}


def restricted_settings(settings, limit=None, max_pages=None):
    changes = {}
    for value, name in ((limit, "max_items"), (max_pages, "max_pages")):
        if value is not None:
            if type(value) is not int or not 0 < value <= getattr(settings, name):
                raise ValueError(f"CLI {name} must be positive and no higher than the YAML cap.")
            changes[name] = value
    return replace(settings, **changes)


def file_digests(path):
    sha, md5, size = hashlib.sha256(), hashlib.md5(), 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
            md5.update(chunk)
            size += len(chunk)
    return sha.hexdigest(), md5.hexdigest(), size


def valid_local(directory, result, *, folder="files"):
    if not result:
        return False
    path = (directory / result["path"]).resolve()
    if not path.is_relative_to((directory / folder).resolve()):
        raise ValueError("Manifest contains a file reference outside its managed files directory.")
    if not path.is_file() or path.stat().st_size != result["size"]:
        return False
    return file_digests(path)[0] == result["sha256"]


def check_space(directory, reserve, upcoming=0):
    if shutil.disk_usage(directory).free - upcoming < reserve:
        raise OSError("Insufficient free disk space for the configured reserve and transfer.")


def validate_document(prefix, extension, mime):
    stripped = prefix.lstrip().lower()
    html = stripped.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))
    if extension not in {".html", ".htm"} and (html or mime in {"text/html", "application/xhtml+xml"}):
        raise InvalidDocument("Received an HTML/error/login page instead of a document.")
    if extension == ".pdf" and b"%PDF-" not in prefix[:1024]:
        raise InvalidDocument("Response does not have a PDF signature.")
    if extension in {".djvu", ".djv"} and not prefix.startswith(b"AT&TFORM"):
        raise InvalidDocument("Response does not have a DjVu signature.")
    if extension in {".docx", ".pptx", ".xlsx", ".epub", ".odt", ".odp", ".ods"} and not prefix.startswith(b"PK"):
        raise InvalidDocument("Response does not have an expected document-container signature.")
    if extension in {".doc", ".ppt", ".xls"} and not prefix.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise InvalidDocument("Response does not have an expected office-document signature.")
    if extension == ".rtf" and not stripped.startswith(b"{\\rtf"):
        raise InvalidDocument("Response does not have an RTF signature.")


def acquire(http, manifest, asset, temporary, summary, *, extensions=None, validate_file=None):
    settings, budget = http.settings, http.budget
    previous = asset["results"][-1] if asset["results"] else None
    local_ok = valid_local(manifest.directory, previous)
    headers = {}
    if local_ok:
        if asset.get("etag", previous.get("etag")):
            headers["If-None-Match"] = asset.get("etag", previous.get("etag"))
        if asset.get("last_modified", previous.get("last_modified")):
            headers["If-Modified-Since"] = asset.get("last_modified", previous.get("last_modified"))

    def attempt():
        partial = temporary / (asset["id"] + ".part")
        try:
            with http.get(asset["url"], headers=headers) as response:
                if not same_origin(response.url, settings.archive_url):
                    raise InvalidDocument("Attachment redirected outside the configured source origin.")
                if response.status_code == 304:
                    if not local_ok:
                        raise InvalidDocument("Unexpected 304 without a verified local original.")
                    return None
                if response.status_code != 200:
                    raise InvalidDocument(f"Expected a complete document response, received HTTP {response.status_code}.")
                mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                filename_header = Message()
                filename_header["Content-Disposition"] = response.headers.get("Content-Disposition", "")
                filename = filename_header.get_filename() or unquote(PurePosixPath(urlsplit(response.url).path).name)
                extension = asset.get("extension") or PurePosixPath(filename).suffix.lower() or MIME_EXTENSIONS.get(mime)
                if extension not in (DOCUMENT_EXTENSIONS if extensions is None else extensions):
                    raise InvalidDocument(f"Unsupported attachment format or MIME: {extension or mime!r}")
                length = response.headers.get("Content-Length")
                expected = int(length) if length is not None and response.headers.get("Content-Encoding", "identity") == "identity" else None
                if expected is not None:
                    if expected <= 0:
                        raise InvalidDocument("Empty or invalid declared file size.")
                    if expected > settings.max_file_bytes:
                        raise InvalidDocument("Declared file size exceeds max_file_bytes.")
                    if expected > settings.max_download_bytes - budget.bytes:
                        raise BudgetStop("download byte cap")
                check_space(manifest.directory, settings.disk_reserve_bytes, expected or 0)
                sha, md5, size, prefix = hashlib.sha256(), hashlib.md5(), 0, b""
                with partial.open("wb") as handle:
                    while True:
                        budget.check()
                        remaining = settings.max_download_bytes - budget.bytes
                        if remaining <= 0:
                            # A known identity-encoded length establishes the complete boundary.
                            if expected is not None and size == expected:
                                break
                            raise BudgetStop("download byte cap")
                        read_size = min(65536, remaining, settings.max_file_bytes - size + 1)
                        chunk = response.raw.read(read_size, decode_content=True)
                        if not chunk:
                            break
                        budget.bytes += len(chunk)
                        size += len(chunk)
                        if size > settings.max_file_bytes:
                            raise InvalidDocument("Streamed file exceeds max_file_bytes.")
                        check_space(manifest.directory, settings.disk_reserve_bytes, len(chunk))
                        prefix = (prefix + chunk)[:1024]
                        sha.update(chunk)
                        md5.update(chunk)
                        handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
                if size == 0:
                    raise InvalidDocument("Empty document response.")
                if expected is not None and size != expected:
                    raise requests.ConnectionError("Incomplete transfer: Content-Length mismatch.")
                validate_document(prefix, extension, mime)
                if validate_file is not None:
                    validate_file(partial)
                digest = sha.hexdigest()
                target = manifest.directory / "files" / (digest + extension)
                target.parent.mkdir(parents=True, exist_ok=True)
                reused = target.is_file() and file_digests(target)[0] == digest
                if reused:
                    summary["reused_blobs"] += 1
                else:
                    os.replace(partial, target)
                return {"id": uuid4().hex, "observation_id": asset["observation_id"],
                        "url": asset["url"], "final_url": response.url, "filename": filename,
                        "sha256": digest, "md5": md5.hexdigest(), "size": size, "mime": mime,
                        "path": target.relative_to(manifest.directory).as_posix(), "acquired_at": now(),
                        "etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified")}
        finally:
            partial.unlink(missing_ok=True)

    result = http.retry(attempt)
    if result is None:
        summary["not_modified"] += 1
    elif previous and previous["sha256"] == result["sha256"]:
        # Keep the original acquisition/observation relationship on byte-identical rechecks.
        for key in ("etag", "last_modified"):
            asset[key] = result.get(key)
        summary["unchanged_downloads"] += 1
    else:
        asset["results"].append(result)
        summary["downloaded"] += 1
    if result is not None:
        asset["etag"], asset["last_modified"] = result.get("etag"), result.get("last_modified")
    asset["status"], asset["last_checked"] = "downloaded", now()
    asset.pop("last_error", None)
    manifest.save()


def download(http, manifest, summary, log, recheck):
    workspace = manifest.directory / ".tmp"
    workspace.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="run-", dir=workspace) as temporary:
        for asset in manifest.data["assets"].values():
            http.budget.check()
            if not asset.get("current", True) or asset["status"] == "unsupported":
                continue
            previous = asset["results"][-1] if asset["results"] else None
            if asset["status"] == "downloaded" and not recheck and valid_local(manifest.directory, previous):
                summary["skipped"] += 1
                continue
            http.budget.start_item()
            try:
                acquire(http, manifest, asset, Path(temporary), summary)
                log(f"Acquired: {asset['label'] or asset['url']}")
            except (requests.RequestException, TransportError, ValueError) as error:
                asset["status"], asset["last_error"] = "failed", str(error)
                manifest.save()
                summary["errors"].append({"url": asset["url"], "stage": "download", "error": str(error)})
                log(f"Download failed: {asset['url']}: {error}")


def run(settings, source, command, *, recheck=False, log=print):
    if source not in SOURCES:
        raise ValueError(f"Unknown source: {source}. Available: {', '.join(SOURCES)}")
    directory = settings.artifacts_root / source
    if command == "status":
        return Manifest(directory, source).status()
    summary = {"id": uuid4().hex, "source": source, "command": command, "started_at": now(),
               "pages": 0, "records": 0, "observations": 0, "downloaded": 0, "reused_blobs": 0,
               "not_modified": 0, "unchanged_downloads": 0, "skipped": 0,
               "requests": 0, "network_retries": 0, "stops": [], "errors": []}
    with source_lock(directory):
        manifest = Manifest(directory, source)
        budget = Budget(settings)
        http = HTTP(settings, budget, summary)
        try:
            if command in {"discover", "run"}:
                try:
                    discover(http, manifest, SOURCES[source], summary, log)
                except BudgetStop as error:
                    summary["stops"].append(str(error))
                    summary["discovery_complete"] = False
            if command in {"download", "run"}:
                if getattr(SOURCES[source], "DOWNLOAD_UNIT", None) == "issue":
                    from .image_issues import download as download_issues
                    download_issues(http, manifest, summary, log, recheck)
                else:
                    download(http, manifest, summary, log, recheck)
        except BudgetStop as error:
            summary["stops"].append(str(error))
        except (OSError, KeyboardInterrupt) as error:
            summary["errors"].append({"stage": "operation", "error": str(error) or "Interrupted"})
        finally:
            http.close()
            summary.update(finished_at=now(), attempted_download_bytes=budget.bytes, started_items=budget.items,
                           backlog=manifest.status())
            summary["stops"] = list(dict.fromkeys(summary["stops"]))
            summary["summary_path"] = str(directory / "summaries" / (summary["id"] + ".json"))
            manifest.data["last_run"] = summary
            manifest.save()
            atomic_json(Path(summary["summary_path"]), summary)
    return summary
