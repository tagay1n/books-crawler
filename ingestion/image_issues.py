"""Publication-level acquisition and derived PDFs from ordered upstream JPEGs."""

import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import tempfile
from uuid import uuid4

import pymupdf
from PIL import Image, ImageOps, __version__ as PILLOW_VERSION

from .core import acquire, check_space, file_digests, valid_local
from .discovery import READ_ERRORS
from .network import InvalidDocument
from .state import now


ASSEMBLER_VERSION = "jpeg-pages-v1/pymupdf-" + pymupdf.VersionBind
COLOUR_POLICY = {"dpi": 200, "jpeg_quality": 85, "mode": "RGB"}
CONVERSION_VERSION = "colour-lanczos-v1"


def image_policy(record):
    policy = record["observations"][-1]["metadata"].get("pdf_image_policy")
    if policy is not None and policy != COLOUR_POLICY:
        raise ValueError("Unsupported PDF image conversion policy.")
    return policy


def colour_page(path):
    """Derive a 200 DPI colour page without changing the retained original."""
    with Image.open(path) as source:
        dpi = source.info.get("dpi")
        if (not dpi or len(dpi) != 2
                or any(not math.isfinite(float(d)) or float(d) < 200 for d in dpi)):
            raise ValueError("200 DPI assembly requires source JPEG resolution metadata of at least 200 DPI.")
        xdpi, ydpi = map(float, dpi)
        orientation = source.getexif().get(274, 1)
        profile = source.info.get("icc_profile") if source.mode == "RGB" else None
        if source.mode not in {"RGB", "L"}:
            raise ValueError("Colour assembly requires RGB or grayscale source JPEGs.")
        image = ImageOps.exif_transpose(source)
        if orientation in {5, 6, 7, 8}:
            xdpi, ydpi = ydpi, xdpi
        width, height = image.width * 72 / xdpi, image.height * 72 / ydpi
        image = image.convert("RGB").resize(
            (math.ceil(image.width * 200 / xdpi), math.ceil(image.height * 200 / ydpi)),
            Image.Resampling.LANCZOS)
        encoded = BytesIO()
        image.save(encoded, format="JPEG", quality=85, optimize=True, dpi=(200, 200),
                   **({"icc_profile": profile} if profile else {}))
        return encoded.getvalue(), width, height


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
    policy = image_policy(record)
    if policy is not None:
        payload.update(image_policy=policy, pillow_version=PILLOW_VERSION,
                       conversion_version=CONVERSION_VERSION)
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
                if image_policy(record) is not None:
                    encoded, width, height = colour_page(path)
                    page = output.new_page(width=width, height=height)
                    page.insert_image(page.rect, stream=encoded)
                else:
                    # Existing adapters retain their original JPEG embedding policy.
                    with pymupdf.open(path) as image:
                        with pymupdf.open("pdf", image.convert_to_pdf()) as page:
                            output.insert_pdf(page)
            output.set_metadata({"title": record["observations"][-1]["metadata"]["title"],
                                 "creator": "BooksCrawler image publication assembler",
                                 "producer": ASSEMBLER_VERSION})
            budget.check()
            output.save(partial, garbage=3, deflate=True)
        with partial.open("rb") as handle:
            os.fsync(handle.fileno())
        budget.check()
        sha, md5, size = file_digests(partial)
        if size > settings.max_derived_pdf_bytes:
            raise ValueError("Assembled PDF exceeds max_derived_pdf_bytes.")
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
                                 "image_policy": image_policy(record),
                                 "pillow_version": PILLOW_VERSION if image_policy(record) else None,
                                 "conversion_version": CONVERSION_VERSION if image_policy(record) else None,
                                 "sha256": sha, "md5": md5, "size": size, "pages": len(assets)})
        state.update(status="complete", last_checked=now())
        state.pop("last_error", None)
        summary["pdf_assembled"] += 1
        manifest.save()
    finally:
        partial.unlink(missing_ok=True)


def download(http, manifest, summary, log, recheck, *, unit="issue"):
    summary.update(download_unit=unit, pdf_assembled=0, pdf_reused=0)
    workspace = manifest.directory / ".tmp"
    workspace.mkdir(parents=True, exist_ok=True)
    grouped = {}
    for asset in manifest.data["assets"].values():
        if (asset.get("current", True) and asset.get("kind") == "page_image"
                and asset["status"] != "unsupported"):
            grouped.setdefault(asset.get("record_key", asset["record_url"]), []).append(asset)
    with tempfile.TemporaryDirectory(prefix="run-", dir=workspace) as temporary:
        temporary = Path(temporary)
        for key, record in manifest.data["records"].items():
            http.budget.check()
            metadata = record["observations"][-1]["metadata"]
            if metadata.get("expected_pages") is None:
                continue
            assets = sorted(grouped.get(key, []), key=lambda a: a.get("page_index", -1))
            state = record.setdefault("pdf", {"status": "incomplete", "results": []})
            try:
                if [a["page_index"] for a in assets] != list(range(metadata["expected_pages"])):
                    raise ValueError("Current images do not match the expected page sequence.")
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
                    continue
                state["status"] = "incomplete"
                manifest.save()
                http.budget.start_item()
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
                    log(f"Publication incomplete: {metadata['title']}")
                else:
                    assemble(http, manifest, record, assets, temporary, summary)
                    log(f"PDF ready: {metadata['title']} ({len(assets)} pages)")
            except (ValueError, RuntimeError) as error:
                state.update(status="failed", last_error=str(error))
                summary["errors"].append({"url": metadata["url"], "stage": "assemble", "error": str(error)})
                log(f"PDF assembly failed: {metadata['title']}: {error}")
            finally:
                manifest.save()
