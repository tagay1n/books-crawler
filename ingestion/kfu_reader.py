"""Resolve KFU's advertised JPEG ranges against their public IIIF readers."""

import hashlib
import json
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .documents import canonical
from .kfu import ORIGIN, reader_reference
from .image_issues import COLOUR_POLICY


class UnsupportedReader(ValueError):
    """An image set whose original filenames cannot be enumerated safely."""


def image_range(reader):
    reference, first, last = reader_reference(reader["url"])
    match = re.fullmatch(r"(\d+)\.(jpe?g)\s*\.\.\.\s*(\d+)\.\2",
                         reader.get("filename_raw") or "", re.IGNORECASE)
    count = last - first + 1
    if (reader.get("format_raw") != "Set of JPEG" or match is None
            or len(match[1]) != len(match[3]) or int(match[3]) - int(match[1]) + 1 != count
            or reader.get("displayed_count_raw") != str(count) or count > 10000):
        raise UnsupportedReader("KFU JPEG set does not declare a consistent numbered filename range and count.")
    return reference, first, last, int(match[1]), len(match[1]), match[2]


def read_pages(http, reader):
    reference, first, last, number, width, extension = image_range(reader)
    html, final_url = http.text_response(reader["url"], origin=ORIGIN)
    soup = BeautifulSoup(html, "html.parser")
    candidates = set()
    for script in soup.select("script:not([src])"):
        candidates.update(re.findall(r"['\"]@id['\"]\s*:\s*['\"]([^'\"]+/info\.json)['\"]",
                                     script.get_text()))
    expected = f"{ORIGIN}/api/manifest/{reference}/{first}-{last}/info.json"
    if {canonical(url, final_url) for url in candidates} != {expected}:
        raise UnsupportedReader("KFU reader does not link exactly its expected IIIF manifest.")
    raw, final_manifest = http.text_response(expected, origin=ORIGIN)
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or manifest.get("@type") != "sc:Manifest":
        raise ValueError("Expected a KFU IIIF presentation manifest.")
    sequences = manifest.get("sequences")
    if not isinstance(sequences, list) or len(sequences) != 1 or not isinstance(sequences[0], dict):
        raise ValueError("KFU IIIF manifest must contain one ordered sequence.")
    canvases = sequences[0].get("canvases")
    if not isinstance(canvases, list) or len(canvases) != last - first + 1:
        raise ValueError("KFU IIIF page count disagrees with its advertised JPEG range.")
    pages, identities = [], set()
    for index, canvas in enumerate(canvases):
        if not isinstance(canvas, dict) or canvas.get("@type") != "sc:Canvas":
            raise ValueError("Invalid KFU IIIF canvas.")
        label = canvas.get("label")
        if not isinstance(label, str) or not re.match(rf"^\[{index + 1}\](?:\s|$)", label):
            raise ValueError("KFU IIIF canvas order disagrees with its numbered labels.")
        annotations = canvas.get("images")
        if isinstance(annotations, list) and len(annotations) == 1:
            annotations = annotations[0]
        resource = annotations.get("resource") if isinstance(annotations, dict) else None
        image = resource.get("@id") if isinstance(resource, dict) else None
        parsed = urlsplit(image) if isinstance(image, str) else None
        if (parsed is None or parsed.scheme not in {"http", "https"}
                or parsed.netloc != "repo.kpfu.ru" or parsed.query or parsed.fragment
                or not re.fullmatch(r"/iiif/2/\d+\.jpg/full/full/0/default\.jpg", parsed.path)
                or resource.get("format") != "image/jpeg" or image in identities):
            raise ValueError("KFU IIIF canvas has an unexpected or repeated full image resource.")
        identities.add(image)
        name = f"{number + index:0{width}d}.{extension}"
        # Expand only the record's declared filenames and bitstream sequence range.
        # IIIF validates count/order; native bitstreams retain original DPI and colour.
        url = f"{ORIGIN}/jspui/bitstream/{reference}/{first + index}/{name}"
        pages.append({"url": url, "label": f"Page {index + 1}: {label}",
                      "extension": "." + extension.lower(), "kind": "page_image",
                      "source_asset_key": f"bitstream:{first + index}:{name}",
                      "filename_raw": name, "page_index": index,
                      "reader_url": reader["url"], "iiif_image_url_raw": image,
                      "iiif_canvas_id": canvas.get("@id"), "iiif_label_raw": label,
                      "unsupported_code": None, "unsupported_reason": None})
    return {"reader_url": reader["url"], "iiif_manifest_url": final_manifest,
            "iiif_manifest_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "iiif_manifest": manifest, "expected_pages": len(pages)}, pages


def resolve(http, metadata, assets):
    readers = [a for a in assets if a.get("unsupported_code") == "kfu_reader"]
    if any(a.get("extension") == ".pdf" and not a.get("unsupported_reason") for a in assets):
        for reader in readers:
            reader.update(unsupported_code="reader_superseded",
                          unsupported_reason="An eligible public direct PDF is preferred over image assembly.")
    elif readers:
        try:
            ordered = sorted(readers, key=lambda r: reader_reference(r["url"])[1])
            ranges = [image_range(reader) for reader in ordered]
            if any(left[2] >= right[1] for left, right in zip(ranges, ranges[1:])):
                raise UnsupportedReader("KFU image-reader bitstream ranges overlap.")
            # Reject unsupported sets before any reader fetch or partial observation.
            details, pages = [], []
            for reader in ordered:
                evidence, images = read_pages(http, reader)
                for image in images:
                    image["page_index"] += len(pages)
                details.append(evidence)
                pages.extend(images)
        except UnsupportedReader as error:
            for reader in readers:
                reader.update(unsupported_code="reader_unsupported", unsupported_reason=str(error))
        else:
            metadata.update(image_readers=details, expected_pages=len(pages),
                            pdf_image_policy=dict(COLOUR_POLICY))
            assets = [a for a in assets if a not in readers] + pages
    metadata["attachments"] = [{k: a[k] for k in ("url", "label", "unsupported_code", "page_index") if k in a}
                               for a in assets]
    return metadata, assets
