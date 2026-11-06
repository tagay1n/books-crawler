"""Publication-level acquisition and derived PDFs from ordered upstream JPEG/JPEG2000 images."""
from .runtime_config import option as operational_option

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
from .network import BudgetStop, InvalidDocument
from .state import now


ASSEMBLER_VERSION = "jpeg-pages-v1/pymupdf-" + pymupdf.VersionBind

CONVERSION_VERSION = "colour-lanczos-v1"


def image_policy(record):
    policy = record["observations"][-1]["metadata"].get("pdf_image_policy")
    if policy is not None and policy != operational_option('image_issues', 'colour_policy'):
        raise ValueError("Unsupported PDF image conversion policy.")
    return policy


def colour_page(path):
    """Derive a 200 DPI colour page without changing the retained original."""
    policy = operational_option("image_issues", "colour_policy")
    target_dpi = policy["dpi"]
    with Image.open(path) as source:
        if source.width * source.height > 150_000_000:
            raise ValueError("Page exceeds the 150 megapixel decode limit.")
        dpi = source.info.get("dpi")
        if (not dpi or len(dpi) != 2
                or any(not math.isfinite(float(d)) or float(d) < target_dpi for d in dpi)):
            raise ValueError("200 DPI assembly requires source image resolution metadata of at least 200 DPI.")
        xdpi, ydpi = map(float, dpi)
        orientation = source.getexif().get(274, 1)
        profile = source.info.get("icc_profile") if source.mode == "RGB" else None
        if source.mode not in {"RGB", "L"}:
            raise ValueError("Colour assembly requires RGB or grayscale source images.")
        image = ImageOps.exif_transpose(source)
        if orientation in {5, 6, 7, 8}:
            xdpi, ydpi = ydpi, xdpi
        width, height = image.width * 72 / xdpi, image.height * 72 / ydpi
        image = image.convert("RGB").resize(
            (math.ceil(image.width * target_dpi / xdpi), math.ceil(image.height * target_dpi / ydpi)),
            Image.Resampling.LANCZOS)
        encoded = BytesIO()
        image.save(encoded, format="JPEG", quality=policy["jpeg_quality"], optimize=True, dpi=(target_dpi, target_dpi),
                   **({"icc_profile": profile} if profile else {}))
        return encoded.getvalue(), width, height


def validate_page(path, *, extension):
    try:
        with Image.open(path) as image:
            expected = "JPEG2000" if extension == ".jp2" else "JPEG"
            if image.format != expected:
                raise ValueError(f"Expected {expected} page image.")
            if image.width * image.height > 150_000_000:
                raise ValueError("Page exceeds the 150 megapixel decode limit.")
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("Expected a single-frame page image.")
            image.verify()
        with Image.open(path) as image:
            image.load()
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise InvalidDocument(f"Invalid page image: {error}") from error


def validate_jpeg(path):
    """Compatibility entry point for existing JPEG callers."""
    return validate_page(path, extension=".jpg")


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


def completed_output(record, assets):
    """Completion depends on recorded inputs and recipe, not runner-local files."""
    state = record.get('pdf', {})
    if (state.get('status') != 'complete' or not state.get('results') or not assets
            or any(a.get('status') != 'downloaded' or not a.get('results') for a in assets)):
        return False
    return state['results'][-1].get('input_fingerprint') == inputs_for(record, assets)[0]


def assemble(http, manifest, record, assets, temporary, summary):
    fingerprint, inputs = inputs_for(record, assets)
    state = record["pdf"]
    previous = state["results"][-1] if state["results"] else None
    if (previous and previous["input_fingerprint"] == fingerprint
            and valid_local(manifest.directory, previous, folder="derived")):
        state.update(status="complete", last_checked=now())
        state.pop("last_error", None)
        summary["pdf_reused"] += 1
        manifest.checkpoint()
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
        manifest.checkpoint()
    finally:
        partial.unlink(missing_ok=True)


def download(http, manifest, summary, log, recheck, *, unit="issue",
             assemble_outputs=True, selected_records=None):
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
            if record.get("imported_acquisition_complete") and not recheck:
                summary["skipped"] += 1
                continue
            if recheck:
                record.pop("imported_acquisition_complete", None)
            metadata = record["observations"][-1]["metadata"]
            if metadata.get("expected_pages") is None:
                continue
            assets = sorted(grouped.get(key, []), key=lambda a: a.get("page_index", -1))
            state = record.setdefault("pdf", {"status": "incomplete", "results": []})
            if not recheck and completed_output(record, assets):
                summary['skipped'] += len(assets)
                summary['pdf_reused'] += 1
                continue
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
                manifest.checkpoint()
                http.budget.start_item()
                if selected_records is not None:
                    selected_records.add(key)
                for asset in assets:
                    http.budget.check()
                    previous = asset["results"][-1] if asset["results"] else None
                    if (not recheck and asset["status"] == "downloaded" and previous
                            and valid_local(manifest.directory, previous)):
                        summary["skipped"] += 1
                        continue
                    try:
                        acquire(http, manifest, asset, temporary, summary,
                                extensions={".jpg", ".jpeg", ".jp2"},
                                validate_file=lambda path: validate_page(path, extension=asset["extension"]))
                        log(f"Acquired image: {asset['label']}")
                    except READ_ERRORS as error:
                        asset.update(status="failed", last_error=str(error))
                        summary["errors"].append({"url": asset["url"], "stage": "download", "error": str(error)})
                        manifest.checkpoint()
                        log(f"Image download failed: {asset['url']}: {error}")
                if not assets or any(a["status"] != "downloaded" for a in assets):
                    state["last_error"] = "Expected page images remain unresolved; no complete PDF published."
                    log(f"Publication incomplete: {metadata['title']}")
                elif assemble_outputs and not all(valid_local(manifest.directory, a["results"][-1]) for a in assets):
                    summary["awaiting_inputs"] = summary.get("awaiting_inputs", 0) + 1
                    state["last_error"] = "Restore page inputs or use download --recheck before assembly."
                elif assemble_outputs:
                    assemble(http, manifest, record, assets, temporary, summary)
                    log(f"PDF ready: {metadata['title']} ({len(assets)} pages)")
            except (ValueError, RuntimeError) as error:
                state.update(status="failed", last_error=str(error))
                summary["errors"].append({"url": metadata["url"], "stage": "assemble", "error": str(error)})
                log(f"PDF assembly failed: {metadata['title']}: {error}")
            finally:
                manifest.checkpoint()


def finalize(settings, budget, manifest, summary, log, *, selected_records=None):
    """Publish PDFs using local inputs only; no HTTP client is constructed."""
    from types import SimpleNamespace

    runtime = SimpleNamespace(settings=settings, budget=budget)
    summary.setdefault("pdf_assembled", 0)
    summary.setdefault("pdf_reused", 0)
    grouped = {}
    for asset in manifest.data["assets"].values():
        if (asset.get("current", True) and asset.get("kind") == "page_image"
                and asset["status"] != "unsupported"):
            grouped.setdefault(asset.get("record_key", asset["record_url"]), []).append(asset)
    workspace = manifest.directory / ".tmp"
    workspace.mkdir(parents=True, exist_ok=True)
    attempted = 0
    with tempfile.TemporaryDirectory(prefix="finalize-", dir=workspace) as temporary:
        for key, record in manifest.data["records"].items():
            budget.check()
            if selected_records is not None and key not in selected_records:
                continue
            if record.get("imported_acquisition_complete"):
                summary["skipped"] += 1
                continue
            metadata = record["observations"][-1]["metadata"]
            if metadata.get("expected_pages") is None:
                continue
            assets = sorted(grouped.get(key, []), key=lambda a: a.get("page_index", -1))
            state = record.setdefault("pdf", {"status": "incomplete", "results": []})
            if completed_output(record, assets):
                summary['pdf_reused'] += 1
                continue
            try:
                ready = bool(assets) and all(a["status"] == "downloaded" and a["results"]
                    and valid_local(manifest.directory, a["results"][-1]) for a in assets)
                fingerprint = inputs_for(record, assets)[0] if ready else None
                previous = state["results"][-1] if state["results"] else None
                if (ready and previous and previous["input_fingerprint"] == fingerprint
                        and valid_local(manifest.directory, previous, folder="derived")):
                    assemble(runtime, manifest, record, assets, Path(temporary), summary)
                    continue
                if selected_records is None and attempted >= settings.max_items:
                    raise BudgetStop("finalization item cap")
                attempted += 1
                state["status"] = "incomplete"
                if not ready:
                    summary["awaiting_inputs"] = summary.get("awaiting_inputs", 0) + 1
                    state["last_error"] = "Restore page inputs or use download --recheck before finalization."
                    continue
                for asset in assets:
                    budget.check()
                    validate_page(manifest.directory / asset["results"][-1]["path"],
                                  extension=asset["extension"])
                assemble(runtime, manifest, record, assets, Path(temporary), summary)
                log(f"PDF ready: {metadata['title']} ({len(assets)} pages)")
            except (ValueError, RuntimeError, OSError) as error:
                state.update(status="failed", last_error=str(error))
                summary["errors"].append({"url": metadata["url"], "stage": "finalize", "error": str(error)})
                log(f"PDF finalization failed: {metadata['title']}: {error}")
            finally:
                manifest.checkpoint()
