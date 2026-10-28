"""Miras periodical series and explicitly exposed original issue PDFs."""

from pathlib import PurePosixPath
import re
from urllib.parse import parse_qs, unquote, urlsplit

from . import miras
from .documents import canonical, same_origin


ARCHIVE_URL = "https://miras.info/projects/mirasxane/periodicals/"
PARSER_VERSION = 1
REQUIRES_SESSION = True
PERIODICAL_PATH = re.compile(r"/projects/mirasxane/periodicals/(\d+)-[^/]+\.html")
PAGE_PATH = re.compile(r"/projects/mirasxane/periodicals/(?:page/([1-9]\d*)/?)?")


def prepare_http(http, session_file):
    miras.prepare_http(http, session_file)
    http.session.headers["Referer"] = ARCHIVE_URL


def parse_listing(html, request, root):
    return miras.parse_listing(html, request, root, record_path=PERIODICAL_PATH,
                               page_path=PAGE_PATH, catalog="periodicals")


def option_pdf(value, page_url):
    """Accept explicit PDF/reader URLs, never infer URLs from year/issue IDs."""
    target = canonical(value, page_url)
    parsed = urlsplit(target)
    if parsed.path.endswith("/viewer.html"):
        values = parse_qs(parsed.query).get("file", [])
        if not same_origin(target, ARCHIVE_URL) or len(values) != 1 or not values[0]:
            return None
        target = canonical(values[0], target)
        parsed = urlsplit(target)
    if (parsed.scheme not in {"http", "https"}
            or PurePosixPath(unquote(parsed.path)).suffix.lower() != ".pdf"):
        return None
    return target


def record(html, page_url):
    metadata, assets = miras.record(
        html, page_url, record_path=PERIODICAL_PATH, kind="periodical",
        admission_reason="Periodical in the Miras catalog; acquisition requires an explicit Tatar language claim.",
    )
    area = miras.content(miras.check_page(html))
    descriptors = {a["url"]: a for a in assets}
    controls, unresolved = [], []
    for select in area.select("select"):
        options = []
        for option in select.select("option"):
            value = option.get("value", "").strip()
            label = option.get_text(" ", strip=True)
            options.append({"value_raw": value, "label_raw": label})
            if not value or option.has_attr("disabled"):
                continue
            target = option_pdf(value, page_url)
            if target is None:
                unresolved.append({"control_id": select.get("id"), "value_raw": value, "label_raw": label})
                continue
            outside = not same_origin(target, ARCHIVE_URL)
            descriptors.setdefault(target, {
                "url": target, "label": label or "Issue PDF", "extension": ".pdf",
                "unsupported_code": "external_origin" if outside else None,
                "unsupported_reason": "Original is outside the Miras origin." if outside else None,
            })
        controls.append({"id": select.get("id"), "name": select.get("name"), "options": options})
    assets = list(descriptors.values())
    metadata["reader_controls"] = controls
    metadata["unresolved_reader_options"] = unresolved
    metadata["reader_coverage"] = "unresolved" if unresolved else "explicit_links_only"
    # These are series-level source claims, not content verification of each PDF.
    evidence = []
    for field in ("language_raw", "details_raw"):
        value = metadata.get(field, "")
        if ((field == "language_raw" and value.strip().casefold() in {"татарский", "татар", "tat", "tt"})
                or re.search(r"\bна\s+татарском\b|\bтатар\s+телендә\b", value, re.IGNORECASE)):
            evidence.append({"field": field, "claim_raw": value})
    metadata["language_evidence"] = evidence
    metadata["language_selection"] = "selected" if evidence else "held"
    for asset in assets:
        if asset.get("unsupported_reason"):
            continue
        if unresolved:
            asset.update(unsupported_code="reader_unresolved",
                         unsupported_reason="Issue selector logic has not been resolved; do not acquire only the default reader issue.")
        elif not evidence:
            asset.update(unsupported_code="language_unknown",
                         unsupported_reason="No explicit series-level Tatar language claim; original remains held.")
    metadata["attachments"] = [{k: a[k] for k in ("url", "label", "unsupported_code")} for a in assets]
    return metadata, assets


def resolve_record(http, metadata, assets):
    return miras.resolve_record(http, metadata, assets)


def record_key(metadata):
    return "periodical:" + metadata["periodical_id"]


download = miras.download
