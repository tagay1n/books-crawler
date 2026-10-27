"""Issue-level acquisition and derived PDFs from ordered upstream page images."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

import pymupdf
from PIL import Image

from .core import acquire, check_space, file_digests, valid_local
from .discovery import READ_ERRORS
from .network import InvalidDocument
from .state import now


ASSEMBLER_VERSION = "jpeg-pages-v1/pymupdf-" + pymupdf.VersionBind


def validate_jpeg(path):
    try:
        with Image.open(path) as image:
            if image.format != "JPEG":
                raise ValueError("Expected JPEG page image.")
            image.verify()
        with Image.open(path) as image:
            image.load()
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise InvalidDocument(f"Invalid JPEG page: {error}") from error


def inputs_for(record, assets):
    observation = record["observations"][-1]
    expected = observation["metadata"]["expected_pages"]
    if [a["page_index"] for a in assets] != list(range(expected)):
        raise ValueError("Current image descriptors do not match the expected page sequence.")
    inputs = [{"asset_id": a["id"], "result_id": a["results"][-1]["id"],
               "observation_id": a["results"][-1]["observation_id"],
               "page_index": a["page_index"], "sha256": a["results"][-1]["sha256"]}
              for a in assets]
    payload = {"assembler_version": ASSEMBLER_VERSION, "source_observation_id": observation["id"],
               "pages": [{k: item[k] for k in ("asset_id", "page_index", "sha256")} for item in inputs]}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return fingerprint, inputs


def assemble(http, manifest, record, assets, temporary, summary):
    fingerprint, inputs = inputs_for(record, assets)
    state = record["pdf"]
    previous = state["results"][-1] if state["results"] else None
    if (previous and previous["input_fingerprint"] == fingerprint
            and valid_local(manifest.directory, previous, folder="derived")):
        state.update(status="complete", last_checked=now())
        state.pop("last_error", None)
        summary["pdf_reused"] += 1
        manifest.save()
        return
    settings, budget = http.settings, http.budget
    partial = temporary / "issue.pdf.part"
    estimated = sum(a["results"][-1]["size"] for a in assets) + 1024 * 1024
    check_space(manifest.directory, settings.disk_reserve_bytes, estimated)
    try:
        with pymupdf.open() as output:
            for asset in assets:
                budget.check()
                check_space(manifest.directory, settings.disk_reserve_bytes, estimated)
                path = manifest.directory / asset["results"][-1]["path"]
                # MuPDF embeds the original JPEG stream and honors its orientation.
                with pymupdf.open(path) as image:
                    with pymupdf.open("pdf", image.convert_to_pdf()) as page:
                        output.insert_pdf(page)
            output.set_metadata({"title": record["observations"][-1]["metadata"]["title"],
                                 "creator": "BooksCrawler image issue assembler",
                                 "producer": ASSEMBLER_VERSION})
            budget.check()
            output.save(partial, garbage=3, deflate=True)
        with partial.open("rb") as handle:
            os.fsync(handle.fileno())
        budget.check()
        sha, md5, size = file_digests(partial)
        if size > settings.max_file_bytes:
            raise ValueError("Assembled PDF exceeds max_file_bytes.")
        with pymupdf.open(partial) as document:
            if document.page_count != len(assets):
                raise ValueError("Assembled PDF page count does not match its inputs.")
        check_space(manifest.directory, settings.disk_reserve_bytes)
        target = manifest.directory / "derived" / (sha + ".pdf")
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(partial, target)
        state["results"].append({"id": uuid4().hex, "kind": "derived_pdf", "created_at": now(),
                                 "assembler_version": ASSEMBLER_VERSION, "input_fingerprint": fingerprint,
                                 "source_observation_id": record["observations"][-1]["id"], "inputs": inputs,
                                 "path": target.relative_to(manifest.directory).as_posix(),
                                 "sha256": sha, "md5": md5, "size": size, "pages": len(assets)})
        state.update(status="complete", last_checked=now())
        state.pop("last_error", None)
        summary["pdf_assembled"] += 1
        manifest.save()
    finally:
        partial.unlink(missing_ok=True)


def download(http, manifest, summary, log, recheck):
    summary.update(download_unit="issue", pdf_assembled=0, pdf_reused=0)
    workspace = manifest.directory / ".tmp"
    workspace.mkdir(parents=True, exist_ok=True)
    grouped = {}
    for asset in manifest.data["assets"].values():
        if asset.get("current", True):
            grouped.setdefault(asset.get("record_key", asset["record_url"]), []).append(asset)
    with tempfile.TemporaryDirectory(prefix="run-", dir=workspace) as temporary:
        temporary = Path(temporary)
        for key, record in manifest.data["records"].items():
            http.budget.check()
            metadata = record["observations"][-1]["metadata"]
            assets = sorted(grouped.get(key, []), key=lambda a: a.get("page_index", -1))
            state = record.setdefault("pdf", {"status": "incomplete", "results": []})
            ready = bool(assets) and all(a["status"] == "downloaded" and a["results"]
                                        and valid_local(manifest.directory, a["results"][-1]) for a in assets)
            current = state["results"][-1] if state["results"] else None
            fingerprint = inputs_for(record, assets)[0] if ready else None
            if (not recheck and ready and current and current["input_fingerprint"] == fingerprint
                    and valid_local(manifest.directory, current, folder="derived")):
                state.update(status="complete", last_checked=now())
                state.pop("last_error", None)
                summary["skipped"] += len(assets)
                summary["pdf_reused"] += 1
                manifest.save()
                continue
            state["status"] = "incomplete"
            manifest.save()
            http.budget.start_item()
            try:
                for asset in assets:
                    http.budget.check()
                    previous = asset["results"][-1] if asset["results"] else None
                    if not recheck and asset["status"] == "downloaded" and valid_local(manifest.directory, previous):
                        summary["skipped"] += 1
                        continue
                    try:
                        acquire(http, manifest, asset, temporary, summary,
                                extensions={".jpg", ".jpeg"}, validate_file=validate_jpeg)
                        log(f"Acquired image: {asset['label']}")
                    except READ_ERRORS as error:
                        asset.update(status="failed", last_error=str(error))
                        summary["errors"].append({"url": asset["url"], "stage": "download", "error": str(error)})
                        manifest.save()
                        log(f"Image download failed: {asset['url']}: {error}")
                if not assets or any(a["status"] != "downloaded" for a in assets):
                    state["last_error"] = "Expected page images remain unresolved; no complete PDF published."
                    log(f"Issue incomplete: {metadata['title']}")
                else:
                    assemble(http, manifest, record, assets, temporary, summary)
                    log(f"PDF ready: {metadata['title']} ({len(assets)} pages)")
            except (ValueError, RuntimeError) as error:
                state.update(status="failed", last_error=str(error))
                summary["errors"].append({"url": metadata["url"], "stage": "assemble", "error": str(error)})
                log(f"PDF assembly failed: {metadata['title']}: {error}")
            finally:
                manifest.save()
