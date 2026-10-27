"""Resolve public FlipHTML5 readers into explicitly listed, ordered JPEG pages."""

import json
import re
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

from .documents import canonical, same_origin
from .tatkniga import ARCHIVE_URL


class UnsupportedReader(ValueError):
    """A reader format we do not yet understand; retain its link for review."""


def parse_configuration(configuration, reader_url):
    assignments = list(re.finditer(r"\b(?:var\s+)?fliphtml5_pages\s*=\s*", configuration))
    if len(assignments) != 1:
        raise UnsupportedReader("Expected one recognizable FlipHTML5 page list.")
    try:
        pages, _ = json.JSONDecoder().raw_decode(configuration, assignments[0].end())
    except ValueError as error:
        raise ValueError("Invalid FlipHTML5 page-list JSON.") from error
    counts = re.findall(r"\btotalPageCount\s*:\s*(\d+)\s*[,}]", configuration)
    if len(counts) != 1:
        raise ValueError("Expected one declared FlipHTML5 totalPageCount.")
    expected = int(counts[0])
    if not isinstance(pages, list) or not 0 < expected <= 10000 or len(pages) != expected:
        raise ValueError("FlipHTML5 page list does not match its declared page count.")
    assets = []
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise ValueError("Invalid FlipHTML5 page descriptor.")
        href = page.get("l") or page.get("n")
        if not isinstance(href, str) or not href.strip():
            raise ValueError("Reader page has no listed large or normal image.")
        url = canonical(href, reader_url)
        extension = PurePosixPath(unquote(urlsplit(url).path)).suffix.lower()
        if not same_origin(url, ARCHIVE_URL):
            raise UnsupportedReader("Reader page image is outside the Tatkniga origin.")
        if extension not in {".jpg", ".jpeg"}:
            raise UnsupportedReader("Reader page is not a supported JPEG image.")
        # Repeated image URLs can represent distinct blank pages in the reader.
        assets.append({"url": url, "label": f"Reader page {index + 1}", "extension": extension,
                       "source_asset_key": f"{reader_url}#page={index}:{url}", "page_index": index,
                       "kind": "page_image", "unsupported_reason": None, "unsupported_code": None})
    return assets


def read_pages(http, reader_url):
    html, final_reader_url = http.text_response(reader_url, origin=ARCHIVE_URL)
    soup = BeautifulSoup(html, "html.parser")
    configurations = set()
    for script in soup.select("script[src]"):
        url = urlsplit(canonical(script["src"], final_reader_url))
        # PageSpeed can replace config.js with config.js+LoadingJS.js.pagespeed...
        # The bundle explicitly names its original source; fetch that source rather
        # than evaluating the bundle's mod_pagespeed_* JavaScript strings.
        optimized = re.fullmatch(r"(.*/javascript/config\.js)(?:\+[^/]+)?"
                                 r"\.pagespeed\.(?:jc|jm|ce)\.[\w-]+\.js", url.path)
        if optimized:
            url = url._replace(path=optimized.group(1))
        if unquote(url.path).endswith("/javascript/config.js"):
            configurations.add(url.geturl())
    if len(configurations) != 1:
        raise UnsupportedReader("Reader does not link one recognized FlipHTML5 configuration.")
    configuration_url = configurations.pop()
    if not same_origin(configuration_url, ARCHIVE_URL):
        raise UnsupportedReader("Reader configuration is outside the Tatkniga origin.")
    configuration, final_configuration_url = http.text_response(configuration_url, origin=ARCHIVE_URL)
    pages = parse_configuration(configuration, final_reader_url)
    return {"reader_url": reader_url, "reader_final_url": final_reader_url,
            "reader_configuration_url": final_configuration_url,
            "reader_configuration_raw": configuration, "expected_pages": len(pages)}, pages


def resolve(http, metadata, assets):
    readers = [a for a in assets if a.get("unsupported_code") == "reader_deferred"]
    eligible = []
    has_pdf = any(a.get("extension") == ".pdf" and not a.get("unsupported_reason") for a in assets)
    for reader in readers:
        code, reason = None, None
        if not same_origin(reader["url"], ARCHIVE_URL):
            code, reason = "external_origin", "Reader is outside the Tatkniga origin."
        elif has_pdf:
            code, reason = "reader_superseded", "An eligible direct PDF is preferred over image assembly."
        elif metadata["language_selection"] == "excluded":
            code, reason = "language_excluded", "Source metadata does not identify a Tatar-containing edition."
        elif metadata["language_selection"] == "review" and metadata.get("language_raw"):
            code, reason = "language_unknown", "Unrecognized language metadata requires review."
        elif urlsplit(reader["url"]).path.startswith("/upload/interactive_books/"):
            eligible.append(reader)
        if code:
            reader.update(unsupported_code=code, unsupported_reason=reason)
    if len(eligible) > 1:
        for reader in eligible:
            reader.update(unsupported_code="reader_ambiguous",
                          unsupported_reason="Multiple distinct reader links require review before assembly.")
    elif eligible:
        reader = eligible[0]
        try:
            details, pages = read_pages(http, reader["url"])
        except UnsupportedReader as error:
            reader.update(unsupported_code="reader_unsupported", unsupported_reason=str(error))
        else:
            metadata.update(details, reader_language_selection=(
                "selected" if metadata["language_selection"] == "selected" else "missing_label_allowed"))
            assets = [a for a in assets if a is not reader] + pages
    metadata["attachments"] = [{k: a[k] for k in ("url", "label", "unsupported_code", "page_index") if k in a}
                               for a in assets]
    return metadata, assets
