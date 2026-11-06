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
from .network import Budget, BudgetStop, HTTP, InvalidDocument, SourceAccessError
from .paths import source_directory
from .registry import SOURCES, configured_adapter
from .runtime_config import configured, discovery_window
from .state import Manifest, now, source_lock


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


def source_version_matches(asset):
    """Opt-in source hints do not alter older adapters' download behavior."""
    return ("source_version" not in asset
            or asset.get("verified_source_version") == asset["source_version"])


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
    version_ok = source_version_matches(asset)
    if local_ok and version_ok:
        if asset.get("etag", previous.get("etag")):
            headers["If-None-Match"] = asset.get("etag", previous.get("etag"))
        if asset.get("last_modified", previous.get("last_modified")):
            headers["If-Modified-Since"] = asset.get("last_modified", previous.get("last_modified"))

    def attempt():
        partial = temporary / (asset["id"] + ".part")
        try:
            if hasattr(http, "validate_acquisition"):
                http.validate_acquisition(asset)
            with http.get(asset["url"], headers=headers) as response:
                if hasattr(http, "validate_download_response"):
                    http.validate_download_response(response, asset)
                elif not same_origin(response.url, settings.archive_url):
                    raise InvalidDocument("Attachment redirected outside the configured source origin.")
                if response.status_code == 304:
                    if not local_ok or not version_ok:
                        raise InvalidDocument("Unexpected 304 without a verified local original at the current source version.")
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
                        if size == len(chunk) and hasattr(http, "validate_document_prefix"):
                            http.validate_document_prefix(prefix)
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
                validation = validate_file(partial) if validate_file is not None else None
                digest = sha.hexdigest()
                source_validation = {}
                if hasattr(http, "validate_acquired_asset"):
                    source_validation = http.validate_acquired_asset(
                        asset, {**(validation if isinstance(validation, dict) else {}),
                                "size": size, "sha256": digest, "md5": md5.hexdigest()})
                target = manifest.directory / "files" / (digest + extension)
                target.parent.mkdir(parents=True, exist_ok=True)
                reused = target.is_file() and file_digests(target)[0] == digest
                if reused:
                    summary["reused_blobs"] += 1
                else:
                    os.replace(partial, target)
                return {**(validation if isinstance(validation, dict) else {}), **source_validation,
                        **({"source_version": asset["source_version"]} if "source_version" in asset else {}),
                        "id": uuid4().hex, "observation_id": asset["observation_id"],
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
    if "source_version" in asset:
        asset["verified_source_version"] = asset["source_version"]
    asset.pop("last_error", None)
    manifest.checkpoint()


def download(http, manifest, summary, log, recheck, *, selected_records=None, extensions=None, validate_file=None):
    workspace = manifest.directory / ".tmp"
    workspace.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="run-", dir=workspace) as temporary:
        for asset in manifest.data["assets"].values():
            http.budget.check()
            if (not asset.get("current", True) or asset["status"] == "unsupported"
                    or asset.get("kind") == "page_image"):
                continue
            previous = asset["results"][-1] if asset["results"] else None
            if asset.get("imported_acquisition_complete") and not recheck and source_version_matches(asset):
                summary["skipped"] += 1
                continue
            if (asset["status"] == "downloaded" and not recheck and source_version_matches(asset)
                    and previous):
                summary["skipped"] += 1
                continue
            if recheck:
                asset.pop("imported_acquisition_complete", None)
            http.budget.start_item()
            try:
                acquire(http, manifest, asset, Path(temporary), summary,
                        extensions=extensions, validate_file=validate_file)
                log(f"Acquired: {asset['label'] or asset['url']}")
            except (requests.RequestException, TransportError, ValueError) as error:
                asset["status"], asset["last_error"] = "failed", str(error)
                manifest.checkpoint()
                summary["errors"].append({"url": asset["url"], "stage": "download", "error": str(error)})
                log(f"Download failed: {asset['url']}: {error}")


def _run_local(settings, source, command, *, recheck=False, session_file=None, log=print, options=None, checkpoint=None, status_data=None):
    if source not in SOURCES:
        raise ValueError(f"Unknown source: {source}. Available: {', '.join(SOURCES)}")
    from .checkpoints import Checkpoint
    checkpoint = checkpoint or Checkpoint()
    adapter = configured_adapter(source, settings)
    if hasattr(adapter, "execute"):
        return adapter.execute(settings, command, recheck=recheck, log=log, options=options, checkpoint=checkpoint, status_data=status_data)
    directory = source_directory(settings, source)
    if command == "status":
        return Manifest(directory, source, checkpoint=checkpoint, data=status_data).status()
    summary = {"id": uuid4().hex, "source": source, "command": command, "started_at": now(),
               "pages": 0, "records": 0, "observations": 0, "downloaded": 0, "reused_blobs": 0,
               "not_modified": 0, "unchanged_downloads": 0, "skipped": 0,
               "requests": 0, "network_retries": 0, "stops": [], "errors": []}
    with source_lock(directory, source):
        manifest = Manifest(directory, source, checkpoint=checkpoint)
        budget = Budget(settings)
        http = HTTP(settings, budget, summary) if command != "finalize" else None
        selected_records = set()
        try:
            if http is not None and hasattr(adapter, "prepare_http"):
                adapter.prepare_http(http, session_file)
            if command in {"discover", "run"}:
                try:
                    with discovery_window(settings):
                        discover(http, manifest, adapter, summary, log)
                except BudgetStop as error:
                    summary["stops"].append(str(error))
                    summary["discovery_complete"] = False
            if command in {"download", "run"}:
                acquire = getattr(adapter, "download", None)
                if acquire is None:
                    if getattr(adapter, "DOWNLOAD_UNIT", None) == "issue":
                        from .image_issues import download as acquire
                    else:
                        acquire = download
                try:
                    acquire(http, manifest, summary, log, recheck, selected_records=selected_records)
                except BudgetStop as error:
                    if not hasattr(adapter, "finalize"):
                        raise
                    # A staged adapter can finish already selected local inputs.
                    summary["stops"].append(str(error))
            if command in {"finalize", "run"} and hasattr(adapter, "finalize"):
                adapter.finalize(settings, budget, manifest, summary, log,
                                 selected_records=selected_records if command == "run" else None)
        except BudgetStop as error:
            summary["stops"].append(str(error))
        except SourceAccessError as error:
            if command in {"discover", "run"}:
                summary.setdefault("discovery_complete", False)
            summary["errors"].append({"stage": "access", "error": str(error)})
            log(str(error))
        except (OSError, KeyboardInterrupt) as error:
            summary["errors"].append({"stage": "operation", "error": str(error) or "Interrupted"})
        finally:
            if http is not None:
                http.close()
            summary.update(finished_at=now(), attempted_download_bytes=budget.bytes, started_items=budget.items,
                           backlog=manifest.status())
            summary["stops"] = list(dict.fromkeys(summary["stops"]))
            summary['state_key'] = 'last_run'
            manifest.data["last_run"] = summary
            manifest.checkpoint()
    return summary


@configured
def run(settings, source, command, *, recheck=False, session_file=None, log=print, options=None):
    """Common lifecycle around native acquisition implementations."""
    from . import publication
    from .postgres_state import Repository
    from .commands import CommandOptions, validate
    options = options or CommandOptions(recheck=recheck, session_file=session_file)
    validate(source, command, options)
    recheck, session_file = options.recheck, options.session_file
    if command == 'run':
        from .automation import require_access
        require_access(settings, source)
    target = options.target
    remote = command == 'run' or (command == 'publish' and target == 's3')
    if command == 'status':
        data = Repository(source).load_status()
        result = _run_local(settings, source, command, recheck=recheck, session_file=session_file,
                            log=log, options=options, status_data=data)
        result['s3'] = {'published_artifacts': len(data.get('s3_publications', {}))}
        if settings.s3:
            directory = source_directory(settings, source)
            inventory = list(publication.artifacts(data, directory))
            result['s3']['current_artifacts'] = len(inventory)
            result['s3']['pending_artifacts'] = sum(not publication.completed(data, a, settings) for a in inventory)
        return result
    if not remote:
        return _run_local(settings, source, command, recheck=recheck, session_file=session_file, log=log, options=options)
    publication.configuration(settings)
    directory = source_directory(settings, source)
    upload_budget = None
    if command == 'run':
        with source_lock(directory, source):
            repository = Repository(source)
            data = repository.load()
            if publication.restore_missing(settings, data, directory):
                repository.save(data)
        uploads = dict(errors=[], stops=[])
        def checkpoint(repository, data):
            nonlocal upload_budget
            if data['source'] != source:
                return
            if upload_budget is None:
                upload_budget = Budget(settings, publication=True)
            try:
                publication.publish(settings, data, directory, lambda: repository.save(data), uploads,
                                    upload_budget, available_only=True)
            except BudgetStop as error:
                if str(error) not in uploads['stops']:
                    uploads['stops'].append(str(error))
        from .checkpoints import Checkpoint
        summary = _run_local(settings, source, command, recheck=recheck, session_file=session_file,
                             log=log, options=options, checkpoint=Checkpoint(checkpoint))
        summary['errors'].extend(uploads.pop('errors'))
        summary['stops'].extend(uploads.pop('stops'))
        summary.update(uploads)
    else:
        summary = dict(source=source, command=command, errors=[], stops=[], started_at=now())
    with source_lock(directory, source):
        repository = Repository(source)
        data = repository.load()
        try:
            publication.publish(settings, data, directory, lambda: repository.save(data), summary,
                                upload_budget or Budget(settings, publication=True), available_only=command == 'run')
        except BudgetStop as error:
            summary['stops'].append(str(error))
        inventory = list(publication.artifacts(data, directory))
        summary['s3'] = dict(current_artifacts=len(inventory),
                             pending_artifacts=sum(not publication.completed(data, a, settings) for a in inventory),
                             published_artifacts=len(data.get('s3_publications', {})))
        summary['backlog'] = Manifest(directory, source, data=data).status()
        summary['discovery'] = data.get('discovery', {})
        if source == 'litres':
            summary['discovery'] = data.get('litres_catalog', {})
        elif source == 'milli_kitaphana':
            scans = data.get('milli_catalog', {}).values()
            summary['discovery'] = dict(scans=len(data.get('milli_catalog', {})),
                                        complete_scans=sum(bool(s.get('complete')) for s in scans))
        summary.update(finished_at=now(), state_key='last_run')
        data['last_run'] = summary
        repository.save(data)
    return summary
