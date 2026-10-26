"""Tatarica library catalog and edition links; no content-language inference."""

import re
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

from .documents import DOCUMENT_EXTENSIONS, canonical, same_origin
from .paging import ListingPage, PageRequest


ARCHIVE_URL = "https://tatarica.org/tat/razdely/tatarika-kitaphanse"
PARSER_VERSION = 1
LIBRARY_PATHS = ("/tat/razdely/tatarika-kitaphanse/", "/tat/razdely/biblioteka-tatarika/")


def variable(html, name):
    match = re.search(r"\bvar\s+" + re.escape(name) + r"\s*=\s*['\"]?(\d+)['\"]?\s*;", html)
    if match is None:
        raise ValueError(f"Tatarica catalog is missing {name}.")
    return int(match.group(1))


def parse_listing(html, request, root):
    soup = BeautifulSoup(html, "html.parser")
    batch = request.method == "POST"
    container = soup if batch else soup.select_one("#articles")
    if container is None:
        raise ValueError("Tatarica catalog structure is missing (#articles).")
    count = int(request.context["count"]) if batch else variable(html, "count")
    if request.context.get("verify"):
        return ListingPage([], [], advertised=count, validation=True)
    cid = int(request.data["cID"]) if batch else variable(html, "CCM_CID")
    offset = int(request.data["offset"]) if batch else 0
    anchors = container.select(".tat-grid-block:not(.show-more) a[href]")
    records = []
    for anchor in anchors:
        url = canonical(anchor["href"], root)
        if not same_origin(url, root) or not urlsplit(url).path.startswith(LIBRARY_PATHS):
            raise ValueError(f"Unexpected record URL in the library catalog: {url}")
        records.append(url)
    if batch:
        expected = min(int(request.data["limit"]), count - offset)
        if len(records) != expected:
            raise ValueError(f"Incomplete Tatarica batch at offset {offset}: expected {expected}, got {len(records)}.")
    elif len(records) > count or (count > 0 and not records):
        raise ValueError("Tatarica catalog entries do not agree with the advertised count.")
    next_offset = offset + len(records)
    following = []
    if next_offset < count:
        following.append(PageRequest(
            canonical("/chapter/get_more_articles", root), "POST",
            {"cID": cid, "offset": next_offset, "limit": 9}, {"count": count},
        ))
    return ListingPage(records, following, entries=len(records), advertised=count)


def verification_request(root, _count):
    return PageRequest(root, context={"verify": True})


def record(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1.inner-page-top__title")
    area = soup.select_one(".inner-page-content")
    if heading is None or area is None:
        raise ValueError(f"Tatarica record structure is missing: {page_url}")
    raw_title = heading.get_text(" ", strip=True)
    metadata = {"url": page_url, "title_raw": raw_title, "title": " ".join(raw_title.split()),
                "admission_reason": "Document edition linked by the configured Tatarica library."}
    native_id = re.search(r"\bvar\s+CCM_CID\s*=\s*['\"]?(\d+)['\"]?\s*;", html)
    if native_id:
        metadata["cms_page_id"] = native_id.group(1)
    subtitle = soup.select_one(".inner-page-top__subtitle")
    if subtitle and subtitle.get_text(" ", strip=True):
        metadata["subtitle"] = subtitle.get_text(" ", strip=True)
    contents = area.select(".copy-content")
    description = "\n".join(body.get_text(" ", strip=True) for body in contents).strip()
    if description:
        metadata["description"] = description
    assets, bibliography = {}, []
    for body in contents:
        for anchor in body.select("a[href]"):
            url = canonical(anchor["href"], page_url)
            extension = PurePosixPath(unquote(urlsplit(url).path)).suffix.lower()
            file_id = re.fullmatch(r"/download_file/view/(\d+)(?:/\d+)?/?", urlsplit(url).path)
            if not file_id and extension not in DOCUMENT_EXTENSIONS:
                continue
            paragraph = anchor.find_parent("p")
            context = paragraph.get_text(" ", strip=True) if paragraph else anchor.get_text(" ", strip=True)
            asset = {"url": url, "label": anchor.get_text(" ", strip=True), "extension": extension,
                     "unsupported_reason": None if same_origin(url, page_url) else "Attachment is outside the configured source origin."}
            if context:
                asset["context"] = context
                if context not in bibliography:
                    bibliography.append(context)
            if file_id:
                asset["source_asset_key"] = "file:" + file_id.group(1)
            assets[url] = asset
    if bibliography:
        metadata["bibliography_raw"] = bibliography
    metadata["attachments"] = [
        {k: asset[k] for k in ("url", "label", "context") if k in asset}
        for asset in assets.values()
    ]
    return metadata, list(assets.values())


def record_key(metadata):
    return "cms:" + metadata["cms_page_id"] if metadata.get("cms_page_id") else metadata["url"]
