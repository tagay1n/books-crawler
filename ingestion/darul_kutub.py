"""Darul-Kutub publications and exposed original files, across all languages."""

import ast
import json
import re
from pathlib import PurePosixPath
from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup

from .documents import DOCUMENT_EXTENSIONS, canonical, same_origin
from .paging import CatalogChanged, ListingPage, PageRequest


ARCHIVE_URL = "https://darul-kutub.com/search"
PARSER_VERSION = 1
BOOK_PATH = re.compile(r"/books/(\d+)/?")


def parse_listing(html, request, root):
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("#search-results")
    counter = soup.select_one(".search-count strong")
    if container is None or counter is None:
        raise ValueError("Darul-Kutub catalog structure or result count is missing.")
    raw_count = re.sub(r"\s+", "", counter.get_text())
    if not raw_count.isdecimal():
        raise ValueError("Darul-Kutub result count is not an integer.")
    count = int(raw_count)
    if request.context.get("verify"):
        return ListingPage([], [], advertised=count, validation=True)
    if "count" in request.context and count != request.context["count"]:
        raise CatalogChanged("Darul-Kutub result count changed during discovery; another scan is required.")
    parameters = parse_qs(urlsplit(request.url).query)
    page_raw = parameters.get("page", ["1"])
    if len(page_raw) != 1 or not page_raw[0].isdecimal() or int(page_raw[0]) < 1:
        raise ValueError("Invalid Darul-Kutub catalog page number.")
    page_number = int(page_raw[0])
    cards = container.select(".book-card")
    page_size = request.context.get("page_size", len(cards))
    if count and not page_size:
        raise ValueError("Darul-Kutub returned no rows before catalog exhaustion.")
    expected = min(page_size, max(0, count - (page_number - 1) * page_size))
    if len(cards) != expected:
        raise ValueError(f"Incomplete Darul-Kutub page {page_number}: expected {expected} rows, got {len(cards)}.")
    records, rows = [], []
    for card in cards:
        title = card.select_one("a.book-title[href]")
        parent = card.select_one("a.book-source-link[href]")
        link = parent if parent is not None else title
        if link is None:
            raise ValueError("Catalog result is missing its publication reference.")
        target = canonical(link["href"], root)
        book_id = BOOK_PATH.fullmatch(urlsplit(target).path)
        if not same_origin(target, root) or book_id is None:
            raise ValueError(f"Unexpected publication URL: {target}")
        # Reader page hints locate articles inside an original, not new publications.
        records.append(canonical(f"/books/{book_id.group(1)}/", root))
        details = card.select_one(".book-details")
        author = card.select_one(".book-author")
        rows.append({"entry_url": canonical(title["href"], root) if title else target,
                     "entry_title": title.get_text(" ", strip=True) if title else "",
                     "publication_url": target, "publication_label": link.get_text(" ", strip=True),
                     "details": details.get_text(" ", strip=True) if details else "",
                     "author": author.get_text(" ", strip=True) if author else ""})
    following = []
    next_link = soup.select_one('.pagination a[rel~="next"][href]')
    more_expected = page_number * page_size < count
    if more_expected != (next_link is not None):
        raise ValueError("Darul-Kutub pagination does not agree with the advertised result count.")
    if next_link is not None:
        next_url = canonical(next_link["href"], root)
        query = parse_qs(urlsplit(next_url).query)
        if (not same_origin(next_url, root) or urlsplit(next_url).path.rstrip("/") != "/search"
                or query.get("page") != [str(page_number + 1)]):
            raise ValueError("Darul-Kutub next-page link does not advance within the catalog.")
        following.append(PageRequest(next_url, context={"count": count, "page_size": page_size}))
    return ListingPage(list(dict.fromkeys(records)), following, entries=len(cards), advertised=count,
                       fingerprint=json.dumps(rows, ensure_ascii=False, sort_keys=True), detect_repeats=True)


def verification_request(root, _count):
    return PageRequest(root, context={"verify": True})


def record(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one("div.book-title")
    book_id = BOOK_PATH.fullmatch(urlsplit(page_url).path)
    if title is None or book_id is None or soup.select_one(".book-files, .book-viewer-col") is None:
        raise ValueError(f"Darul-Kutub publication structure is missing: {page_url}")
    raw_title = title.get_text(" ", strip=True)
    metadata = {"url": page_url, "book_id": book_id.group(1), "title_raw": raw_title,
                "title": " ".join(raw_title.split()),
                "admission_reason": "Publication exposed by Darul-Kutub's public catalog."}
    for key, selector in (("publisher_raw", ".book-publisher"), ("details_raw", ".book-meta"),
                          ("description", ".book-annotation")):
        element = soup.select_one(selector)
        if element is not None and element.get_text(" ", strip=True):
            metadata[key] = element.get_text(" ", strip=True)
    authors = [a.get_text(" ", strip=True) for a in soup.select(".book-author") if a.get_text(" ", strip=True)]
    if authors:
        metadata["authors_raw"] = authors
    alternatives = [a.get_text(" ", strip=True) for a in soup.select(".book-title-ar, .book-title-tt")
                    if a.get_text(" ", strip=True)]
    if alternatives:
        metadata["alternate_titles_raw"] = alternatives
    assets = {}

    def original(href, label, part_label=None, extension=None):
        target = canonical(href, page_url)
        suffix = extension or PurePosixPath(unquote(urlsplit(target).path)).suffix.lower()
        reason = None
        if not same_origin(target, page_url):
            reason = "Original is outside the configured source origin."
        elif suffix not in DOCUMENT_EXTENSIONS:
            reason = "Reader does not expose a supported direct document; assembly/conversion is not implemented."
        descriptor = {"url": target, "label": label, "extension": suffix, "unsupported_reason": reason}
        if part_label:
            descriptor["part_label"] = part_label
        assets.setdefault(target, descriptor)

    part_labels = [a.get_text(" ", strip=True) for a in soup.select(".book-parts .tab")]
    tomes = soup.select(".book-parts-tab .tome")
    for index, tome in enumerate(tomes):
        part_label = part_labels[index] if index < len(part_labels) else None
        for link in tome.select(".book-read a[href]"):
            if link["href"].startswith(("#", "javascript:")):
                continue
            original(link["href"], link.get_text(" ", strip=True), part_label)
    # The viewer binding exposes a literal URL; never evaluate JavaScript expressions.
    for viewer in soup.find_all("pdf-viewer"):
        try:
            href = ast.literal_eval(viewer.get(":initial-pdf", ""))
        except (SyntaxError, ValueError):
            continue
        if isinstance(href, str) and href:
            original(href, "PDF")
    represented = {a["extension"] for a in assets.values() if not a["unsupported_reason"]}
    download_links = []
    for link in soup.select(".book-download a[href]"):
        target = canonical(link["href"], page_url)
        path = urlsplit(target).path
        offered = re.fullmatch(r"/books/\d+/download/([a-zA-Z0-9]+)", path)
        extension = ("." + offered.group(1).lower()) if offered else PurePosixPath(unquote(path)).suffix.lower()
        if not offered and extension not in DOCUMENT_EXTENSIONS:
            continue
        label = link.get_text(" ", strip=True)
        download_links.append({"url": target, "label": label})
        # Keep button routes as evidence. A directly exposed original is preferred;
        # byte equivalence with a server-generated download is not asserted.
        if extension not in represented:
            original(target, label, extension=extension)
    if download_links:
        metadata["download_links"] = download_links
    metadata["attachments"] = [{k: asset[k] for k in ("url", "label", "part_label") if k in asset}
                               for asset in assets.values()]
    return metadata, list(assets.values())


def record_key(metadata):
    return "book:" + metadata["book_id"]
