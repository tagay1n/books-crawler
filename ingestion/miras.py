"""Miras books and exposed original PDFs, without a language filter."""

import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup

from .documents import DOCUMENT_EXTENSIONS, canonical, same_origin
from .miras_probe import validate_pdf
from .network import SourceAccessError
from .paging import CatalogChanged, ListingPage, PageRequest


ARCHIVE_URL = "https://miras.info/projects/mirasxane/books/"
PARSER_VERSION = 1
REQUIRES_SESSION = True
BOOK_PATH = re.compile(r"/projects/mirasxane/books/(\d+)-[^/]+\.html")
PAGE_PATH = re.compile(r"/projects/mirasxane/books/(?:page/([1-9]\d*)/?)?")
PROPERTIES = {"Автор": "author_raw", "Авторы": "authors_raw", "Страниц": "pages_raw",
              "Год выпуска": "publication_year_raw", "Место издания": "publication_place_raw",
              "Тематика": "subject_raw", "Язык": "language_raw", "Тип": "type_raw"}
PROPERTY = re.compile(r"(?<!\w)(" + "|".join(PROPERTIES) + r")\s*:\s*")
REFRESH_MESSAGE = ("Miras rejected browser access. Open Miras in your ordinary browser, "
                   "complete its security check, and export a fresh miras-session-v1 file "
                   "for --session-file. Existing checkpoints and downloads are preserved.")


def check_page(html):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True).casefold() if soup.title else ""
    if (soup.select_one("#slg-title, #sl-challenge, #challenge-form, #challenge-running")
            or any(marker in title for marker in ("safeline", "just a moment", "access denied",
                                                  "security verification", "debugging detected"))):
        raise SourceAccessError(REFRESH_MESSAGE)
    return soup


def prepare_http(http, session_file):
    # Imported at run time: the preserved probe itself uses the shared core.
    from .miras_session import load_session, read_json

    try:
        _, session = read_json(Path(session_file))
    except OSError:
        raise SourceAccessError("Cannot read the Miras --session-file export.") from None
    except ValueError as error:
        raise SourceAccessError(str(error)) from None
    try:
        load_session(http, session)
    except ValueError as error:
        raise SourceAccessError(str(error)) from None
    finally:
        session.clear()
    http.session.headers["Referer"] = ARCHIVE_URL
    http.summary["acquisition_method"] = "http_cookie_export"

    def validate_prefix(prefix):
        if prefix.lstrip().startswith(b"<"):
            check_page(prefix.decode("utf-8", errors="replace"))

    http.validate_document_prefix = validate_prefix

    def check_response(response, *args, **kwargs):
        location = response.headers.get("Location")
        outside = not same_origin(response.url, ARCHIVE_URL) or (
            response.is_redirect and location and not same_origin(canonical(location, response.url), ARCHIVE_URL))
        html_pdf = (response.status_code == 200 and urlsplit(response.url).path.lower().endswith(".pdf")
                    and response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                    in {"text/html", "application/xhtml+xml"})
        if outside or response.status_code in {401, 403, 468, 541} or html_pdf:
            response.close()
            raise SourceAccessError(REFRESH_MESSAGE)
        return response

    http.session.hooks["response"].append(check_response)


def page_number(url, *, page_path=PAGE_PATH, catalog="books"):
    parsed = urlsplit(url)
    match = page_path.fullmatch(parsed.path.rstrip("/") + "/")
    if not same_origin(url, ARCHIVE_URL) or not match or parsed.query:
        raise ValueError(f"Listing is outside the unfiltered Miras {catalog} catalog.")
    return int(match.group(1) or 1)


def content(soup):
    area = soup.select_one("#dle-content")
    if area is None:
        area = soup.select_one("main, article")
    if area is None:
        raise ValueError("Miras publication/catalog content is missing.")
    return area


def details(area):
    clean = BeautifulSoup(str(area), "html.parser")
    for node in clean.select("script, style, iframe, nav, footer"):
        node.decompose()
    for link in list(clean.select("a[href]")):
        parsed = urlsplit(link["href"])
        extension = PurePosixPath(unquote(parsed.path)).suffix.lower()
        if parsed.path.endswith("/viewer.html") or extension in DOCUMENT_EXTENSIONS - {".html", ".htm"}:
            link.decompose()
    raw = clean.get_text(" ", strip=True)
    matches = list(PROPERTY.finditer(raw))
    # Parse the smallest bibliographic blocks, so buttons or descriptions after
    # the property table do not become part of its final property value.
    block_tags = ("div", "p", "li", "tr", "section", "article", "main", "dl")
    blocks = [block for block in clean.find_all(block_tags)
              if PROPERTY.search(block.get_text(" ", strip=True))
              and not any(PROPERTY.search(child.get_text(" ", strip=True))
                          for child in block.find_all(block_tags))]
    properties, values = [], {}
    for block in blocks or [clean]:
        text = block.get_text(" ", strip=True)
        fields = list(PROPERTY.finditer(text))
        for index, match in enumerate(fields):
            value = text[match.end():fields[index + 1].start() if index + 1 < len(fields) else len(text)].strip()
            if value:
                label = match.group(1)
                properties.append({"name": label, "value": value})
                values.setdefault(PROPERTIES[label], value)
    values["properties_raw"] = properties
    values["details_raw"] = raw
    prefix = raw[:matches[0].start()].strip() if matches else ""
    if prefix:
        values["description"] = prefix
    return values


def book_target(href, base, *, record_path=BOOK_PATH):
    url = canonical(href, base)
    parsed = urlsplit(url)
    identity = record_path.fullmatch(parsed.path)
    if identity is None:
        return None
    if not same_origin(url, ARCHIVE_URL) or parsed.query:
        raise ValueError("Unexpected publication link in the Miras catalog.")
    return identity.group(1), url


def parse_listing(html, request, root, *, record_path=BOOK_PATH, page_path=PAGE_PATH, catalog="books"):
    current = page_number(request.url, page_path=page_path, catalog=catalog)
    soup = check_page(html)
    area = content(soup)
    entries = {}
    for anchor in area.select("a[href]"):
        target = book_target(anchor["href"], request.url, record_path=record_path)
        if target is None:
            continue
        identity, url = target
        item = entries.setdefault(identity, {"url": url, "anchor": anchor, "label": ""})
        label = anchor.get_text(" ", strip=True)
        if label and not item["label"]:
            item.update(label=label, anchor=anchor)
    if not entries:
        raise ValueError(f"Miras returned no recognizable {catalog} cards; discovery remains incomplete.")
    targets = {}
    for anchor in soup.select("a[href]"):
        url = canonical(anchor["href"], request.url)
        match = page_path.fullmatch(urlsplit(url).path.rstrip("/") + "/")
        if match and match.group(1):
            targets[page_number(url, page_path=page_path, catalog=catalog)] = url
    controls = soup.select(".navigation, .pagination")
    if not targets and not controls:
        raise ValueError("Miras catalog pagination structure is missing.")
    for active in soup.select(".navigation .current, .pagination .active, .pagination [aria-current='page']"):
        text = active.get_text(strip=True)
        if text.isdecimal() and int(text) != current:
            raise ValueError("Miras active page does not match the requested page.")
    following = targets.get(current + 1)
    if any(number > current for number in targets) and following is None:
        raise ValueError("Miras forward pagination skips the next page.")
    size = request.context.get("page_size", len(entries))
    if len(entries) > size or (following and len(entries) != size):
        raise CatalogChanged("Miras page size changed or a listing is incomplete; restart discovery.")
    contexts = {}
    for item in entries.values():
        card = item["anchor"]
        while card.parent is not None and card.parent is not area:
            parent = card.parent
            siblings = {target[0] for link in parent.select("a[href]")
                        if (target := book_target(link["href"], request.url, record_path=record_path)) is not None}
            if len(siblings) != 1:
                break
            card = parent
        contexts[item["url"]] = {"listing_url": request.url, "label_raw": item["label"], **details(card)}
    return ListingPage([item["url"] for item in entries.values()],
                       [PageRequest(following, context={"page_size": size})] if following else [],
                       entries=len(entries), detect_repeats=True,
                       fingerprint=json.dumps(list(entries)), record_context=contexts)


def record(html, page_url, *, record_path=BOOK_PATH, kind="book", admission_reason=None):
    identity = book_target(page_url, ARCHIVE_URL, record_path=record_path)
    if identity is None:
        raise ValueError(f"Unrecognized Miras {kind} URL.")
    area = content(check_page(html))
    metadata = {"url": page_url, kind + "_id": identity[0], **details(area),
                "admission_reason": admission_reason or "Book linked by the unfiltered Miras books catalog; all languages eligible."}
    heading = area.select_one("h1, h2, .fullstory-title, .full-title")
    direct_pdf = any(urlsplit(link["href"]).path.lower().endswith(".pdf") for link in area.select("a[href]"))
    if not metadata["properties_raw"] and not heading and not area.select("iframe[src]") and not direct_pdf:
        raise ValueError(f"Miras {kind} properties or reader structure is missing.")
    if heading and heading.get_text(" ", strip=True):
        metadata.update(title=heading.get_text(" ", strip=True), title_raw=heading.get_text(" ", strip=True))
    assets, readers = {}, []
    for node in area.select("iframe[src], a[href]"):
        target = canonical(node.get("src", node.get("href")), page_url)
        parsed = urlsplit(target)
        viewer = parsed.path.endswith("/viewer.html")
        if viewer:
            readers.append(target)
            values = parse_qs(parsed.query).get("file", [])
            if same_origin(target, ARCHIVE_URL) and len(values) == 1 and values[0]:
                target = canonical(values[0], target)
                parsed = urlsplit(target)
        extension = PurePosixPath(unquote(parsed.path)).suffix.lower()
        if not viewer and node.name != "iframe" and extension not in DOCUMENT_EXTENSIONS:
            continue
        code, reason = None, None
        if not same_origin(target, ARCHIVE_URL):
            code, reason = "external_origin", "Original is outside the Miras origin."
        elif extension != ".pdf":
            code, reason = "format_unsupported", "Reader/link does not expose a supported original PDF."
        assets.setdefault(target, {"url": target, "label": node.get_text(" ", strip=True) or "PDF reader",
                                   "extension": extension, "unsupported_code": code, "unsupported_reason": reason})
    if readers:
        metadata["reader_links"] = list(dict.fromkeys(readers))
    metadata["attachments"] = [{k: a[k] for k in ("url", "label", "unsupported_code")} for a in assets.values()]
    return metadata, list(assets.values())


def resolve_record(http, metadata, assets):
    contexts = metadata.get("catalog_context", [])
    if not metadata.get("title"):
        label = next((item["label_raw"] for item in contexts if item.get("label_raw")), None)
        if not label:
            raise ValueError("Miras publication title is missing from both record and catalog.")
        metadata.update(title=label, title_raw=label)
    if metadata.get("description", "").startswith(metadata["title"]):
        metadata["description"] = metadata["description"][len(metadata["title"]):].strip()
    return metadata, assets


def record_key(metadata):
    return "book:" + metadata["book_id"]


def validate_original(path):
    return {"pages": validate_pdf(path), "acquisition_method": "http_cookie_export"}


def download(http, manifest, summary, log, recheck):
    from .core import download as download_originals

    download_originals(http, manifest, summary, log, recheck, extensions={".pdf"}, validate_file=validate_original)
