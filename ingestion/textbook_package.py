"""Read bounded FlipHTML5 ZIP members and derive PDFs without executing content."""

import hashlib
from io import BytesIO
import json
import os
from pathlib import PurePosixPath
import re
import stat
from uuid import uuid4
import zipfile
import zlib

import pymupdf
from PIL import Image

from .core import check_space, file_digests, valid_local
from .network import InvalidDocument
from .state import now


RECIPE = "fliphtml5-zip-jpeg-v1/pymupdf-" + pymupdf.VersionBind
DPI = 200
MAX_MEMBERS = 20000
MAX_UNCOMPRESSED = 2 * 1024**3
MAX_PAGE_BYTES = 32 * 1024**2
MAX_CONFIG_BYTES = 1024**2
MAX_PAGES = 2000
MAX_BOOKS = 20


def member_path(name):
    path = PurePosixPath(name)
    if (not name or "\\" in name or "\x00" in name or path.is_absolute()
            or ".." in path.parts or any(":" in part for part in path.parts)):
        raise InvalidDocument("Archive contains an unsafe member path.")
    return path.as_posix().rstrip("/")


def inventory(archive, budget):
    items = archive.infolist()
    if not items or len(items) > MAX_MEMBERS:
        raise InvalidDocument("ZIP is empty or exceeds the member-count limit.")
    total, names = 0, {}
    for item in items:
        budget.check()
        key = member_path(item.filename)
        if key in names:
            raise InvalidDocument("ZIP contains duplicate/ambiguous member paths.")
        mode = item.external_attr >> 16
        if stat.S_ISLNK(mode) or item.flag_bits & 1:
            raise InvalidDocument("Symlinks and encrypted ZIP members are unsupported.")
        if item.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
            raise InvalidDocument("ZIP uses an unsupported compression method.")
        total += item.file_size
        if total > MAX_UNCOMPRESSED:
            raise InvalidDocument("ZIP exceeds the total uncompressed-size limit.")
        names[key] = item
    return names, total


def validate_zip(path, budget):
    try:
        with zipfile.ZipFile(path) as archive:
            names, total = inventory(archive, budget)
            return {"zip_members": len(names), "zip_uncompressed_bytes": total}
    except (zipfile.BadZipFile, NotImplementedError, EOFError, zlib.error) as error:
        raise InvalidDocument(f"Invalid textbook ZIP: {error}") from None


def read_member(archive, item, cap, budget):
    budget.check()
    if item.is_dir() or item.file_size > cap:
        raise InvalidDocument("Required package member exceeds its size limit or is a directory.")
    chunks, size = [], 0
    try:
        with archive.open(item) as source:
            while True:
                budget.check()
                chunk = source.read(min(65536, cap + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > cap:
                    raise InvalidDocument("Decompressed member exceeds its byte cap.")
                chunks.append(chunk)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error) as error:
        raise InvalidDocument(f"Required ZIP member failed integrity/decompression checks: {error}") from None
    if size != item.file_size:
        raise InvalidDocument("ZIP member size disagrees with its directory entry.")
    return b"".join(chunks)


def plans(archive, names, budget):
    configurations = [name for name, item in names.items()
                      if not item.is_dir() and name.endswith("/javascript/config.js")]
    if not configurations or len(configurations) > MAX_BOOKS:
        raise InvalidDocument("Expected one or more supported textbook reader configurations.")
    output, total_pages = [], 0
    for name in sorted(configurations):
        encoded = read_member(archive, names[name], MAX_CONFIG_BYTES, budget)
        text = encoded.decode("utf-8-sig")
        count = re.findall(r"\btotalPageCount\s*:\s*(\d+)\b", text)
        assignments = list(re.finditer(r"\bvar\s+fliphtml5_pages\s*=\s*", text))
        if len(count) != 1 or len(assignments) != 1:
            raise InvalidDocument("Unrecognized reader configuration; refusing to guess page paths.")
        try:
            pages, _ = json.JSONDecoder().raw_decode(text[assignments[0].end():].lstrip())
        except ValueError:
            raise InvalidDocument("Reader page list is not a literal JSON array.") from None
        expected = int(count[0])
        total_pages += expected
        if (not isinstance(pages, list) or not 0 < expected <= MAX_PAGES
                or len(pages) != expected or total_pages > MAX_PAGES):
            raise InvalidDocument("Declared reader count and explicit page list disagree or exceed limits.")
        root = PurePosixPath(name).parent.parent
        members = []
        for page in pages:
            target = page.get("l") if isinstance(page, dict) else None
            if not isinstance(target, str) or not re.fullmatch(r"files/large/[^/]+\.(?:jpg|jpeg)", target, re.IGNORECASE):
                raise InvalidDocument("Reader does not declare a supported original JPEG for every page.")
            member = member_path((root / member_path(target)).as_posix())
            if member not in names or names[member].is_dir() or names[member].file_size > MAX_PAGE_BYTES:
                raise InvalidDocument("A declared reader page is absent or oversized.")
            members.append(member)
        if len(set(members)) != len(members):
            raise InvalidDocument("Reader repeats an image as multiple declared pages.")
        output.append({"configuration_member": name, "configuration_sha256": hashlib.sha256(encoded).hexdigest(),
                       "members": members, "pages": expected})
    return output


def jpeg_dimensions(data):
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != "JPEG" or image.width * image.height > 40_000_000:
                raise ValueError("Expected a JPEG of at most 40 megapixels.")
            dimensions = image.size
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
        return dimensions
    except (OSError, ValueError, Image.DecompressionBombError) as error:
        raise InvalidDocument(f"Invalid textbook page image: {error}") from None


def assemble(http, manifest, record, asset, temporary, summary):
    source = asset["results"][-1]
    observation = record["observations"][-1]
    state = record.setdefault("package_pdf", {"status": "incomplete", "results": []})
    state.setdefault("results", [])
    state.update(status="incomplete", current_results=[])
    manifest.save()
    try:
        with zipfile.ZipFile(manifest.directory / source["path"]) as archive:
            names, _ = inventory(archive, http.budget)
            books = plans(archive, names, http.budget)
            for plan in books:
                http.budget.check()
                fingerprint = hashlib.sha256(json.dumps(
                    {"recipe": RECIPE, "dpi": DPI, "archive_sha256": source["sha256"],
                     "source_observation_id": observation["id"], "plan": plan}, sort_keys=True).encode()).hexdigest()
                previous = next((r for r in reversed(state["results"]) if r["input_fingerprint"] == fingerprint
                                 and valid_local(manifest.directory, r, folder="derived")), None)
                if previous:
                    state["current_results"].append(previous)
                    summary["pdf_reused"] += 1
                    continue
                partial = temporary / (uuid4().hex + ".pdf.part")
                estimated = sum(names[n].file_size for n in plan["members"]) + 1024**2
                if estimated > http.settings.max_derived_pdf_bytes:
                    raise InvalidDocument("Declared page bytes plus PDF overhead exceed max_derived_pdf_bytes.")
                check_space(manifest.directory, http.settings.disk_reserve_bytes, estimated)
                inputs = []
                try:
                    with pymupdf.open() as output:
                        for index, name in enumerate(plan["members"]):
                            http.budget.check()
                            data = read_member(archive, names[name], MAX_PAGE_BYTES, http.budget)
                            width, height = jpeg_dimensions(data)
                            page = output.new_page(width=width * 72 / DPI, height=height * 72 / DPI)
                            page.insert_image(page.rect, stream=data)
                            inputs.append({"member": name, "page_index": index,
                                           "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                                           "pixels": [width, height], "zip_crc32": f"{names[name].CRC:08x}"})
                        output.set_metadata({"title": observation["metadata"]["title"],
                                             "creator": "BooksCrawler textbook package assembler", "producer": RECIPE})
                        http.budget.check()
                        output.save(partial, garbage=3, deflate=True)
                    with partial.open("rb") as handle:
                        os.fsync(handle.fileno())
                    http.budget.check()
                    sha, md5, size = file_digests(partial)
                    if size > http.settings.max_derived_pdf_bytes:
                        raise InvalidDocument("Derived textbook PDF exceeds max_derived_pdf_bytes.")
                    with pymupdf.open(partial) as verified:
                        if len(verified) != plan["pages"]:
                            raise InvalidDocument("Derived PDF does not contain every declared reader page.")
                        verified.load_page(0)
                        verified.load_page(len(verified) - 1)
                    check_space(manifest.directory, http.settings.disk_reserve_bytes)
                    target = manifest.directory / "derived" / (sha + ".pdf")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(partial, target)
                    result = {"id": uuid4().hex, "kind": "derived_pdf", "created_at": now(),
                              "recipe": RECIPE, "assumed_dpi": DPI, "image_policy": "embed_original_jpeg",
                              "source_observation_id": observation["id"], "source_asset_id": asset["id"],
                              "archive_result_id": source["id"], "archive_sha256": source["sha256"],
                              "configuration_member": plan["configuration_member"],
                              "configuration_sha256": plan["configuration_sha256"], "inputs": inputs,
                              "input_fingerprint": fingerprint, "pages": plan["pages"],
                              "path": target.relative_to(manifest.directory).as_posix(),
                              "sha256": sha, "md5": md5, "size": size}
                    state["results"].append(result)
                    state["current_results"].append(result)
                    summary["pdf_assembled"] += 1
                    manifest.save()
                finally:
                    partial.unlink(missing_ok=True)
        state.update(status="complete", archive_sha256=source["sha256"],
                     source_observation_id=observation["id"], last_checked=now())
        state.pop("last_error", None)
        manifest.save()
    except (zipfile.BadZipFile, UnicodeError, EOFError, zlib.error) as error:
        raise InvalidDocument(f"Unsupported or corrupt textbook package: {error}") from None
