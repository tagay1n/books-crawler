"""Current Tatkniga library: direct documents and public image-based readers."""

import json
import re
from pathlib import PurePosixPath
from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup

from .documents import DOCUMENT_EXTENSIONS, canonical, same_origin
from .paging import CatalogChanged, ListingPage, PageRequest


ARCHIVE_URL = "https://tatkniga.ru/catalog/biblioteka/"
PARSER_VERSION = 2
BOOK_PATH = re.compile(r"/catalog/biblioteka/[^/]+\.html")
PRODUCT_ID = re.compile(r"bx_\d+_(\d+)")
DIRECT_FORMATS = DOCUMENT_EXTENSIONS - {".html", ".htm"}
TATAR_LABELS = {"тат", "татарский", "татарча", "татар", "tatar", "tt", "tat"}
OTHER_LANGUAGES = {"рус", "русский", "russian", "ru", "rus", "чув", "чувашский", "cv", "chv",
                   "баш", "башкирский", "ba", "bak", "англ", "английский", "english", "en", "eng",
                   "нем", "немецкий", "de", "deu", "араб", "арабский", "ar", "ara",
                   "крымско-татарский", "крымскотатарский", "crimean tatar", "crh"}


def page_number(url):
    query = parse_qs(urlsplit(url).query, keep_blank_values=True)
    if not query:
        return 1
    values = query.get("PAGEN_1")
    if (set(query) != {"PAGEN_1"} or len(values) != 1 or not values[0].isdecimal()
            or int(values[0]) < 1):
        raise ValueError("Unexpected Tatkniga listing query; only native page numbers are supported.")
    return int(values[0])


def parse_listing(html, request, root):
    if not same_origin(request.url, root) or urlsplit(request.url).path.rstrip("/") != urlsplit(root).path.rstrip("/"):
        raise ValueError("Listing is outside the configured Tatkniga library.")
    current = page_number(request.url)
    soup = BeautifulSoup(html, "html.parser")
    area = soup.select_one("#catalogSection > .items.productList")
    controls = soup.select(".bx-pagination")
    if area is None or soup.h1 is None or not controls:
        raise ValueError("Tatkniga library cards or pagination structure is missing.")
    last_pages, targets = set(), set()
    for control in controls:
        active = control.select_one(".bx-active")
        raw = active.get_text(strip=True) if active else ""
        if not raw.isdecimal() or int(raw) != current:
            raise ValueError("Tatkniga active page does not match the requested page.")
        numbers = [current]
        for anchor in control.select("a[href]"):
            label = anchor.get_text(strip=True)
            if label.isdecimal():
                url = canonical(anchor["href"], root)
                if (not same_origin(url, root) or urlsplit(url).path.rstrip("/") != urlsplit(root).path.rstrip("/")
                        or page_number(url) != int(label)):
                    raise ValueError("Unexpected numbered Tatkniga pagination link.")
                numbers.append(int(label))
        last_pages.add(max(numbers))
        following = control.select_one(".bx-pag-next a[href]")
        targets.add(canonical(following["href"], request.url) if following else None)
    if len(last_pages) != 1 or len(targets) != 1:
        raise ValueError("Tatkniga's duplicated pagination controls disagree.")
    last = last_pages.pop()
    if "last_page" in request.context and request.context["last_page"] != last:
        raise CatalogChanged("Tatkniga's advertised last page changed; next discovery starts a fresh scan.")
    cards = area.select(":scope > .item.product.sku")
    size_labels = {node.get_text(strip=True) for node in soup.select(".countElements .dropDownSelected")}
    if len(size_labels) != 1 or not next(iter(size_labels)).isdecimal():
        raise ValueError("Tatkniga's selected page-size control is missing or inconsistent.")
    size = int(size_labels.pop())
    if size < 1:
        raise ValueError("Invalid Tatkniga page size.")
    if "page_size" in request.context and request.context["page_size"] != size:
        raise CatalogChanged("Tatkniga's page size changed; next discovery starts a fresh scan.")
    if not cards or (current < last and len(cards) != size) or len(cards) > size:
        raise ValueError("Tatkniga returned an empty or incomplete listing page.")
    records, identities, contexts = [], [], {}
    for card in cards:
        anchor = card.select_one("a.name[href]")
        if anchor is None:
            raise ValueError("Tatkniga library card is missing its publication link.")
        url = canonical(anchor["href"], request.url)
        if not same_origin(url, root) or not BOOK_PATH.fullmatch(urlsplit(url).path) or urlsplit(url).query:
            raise ValueError("Library card points outside Tatkniga's publication catalog.")
        native = PRODUCT_ID.fullmatch(card.get("id", ""))
        identities.append(native.group(1) if native else url)
        records.append(url)
        contexts[url] = {"listing_url": request.url, "label_raw": anchor.get_text(" ", strip=True)}
    if len(set(records)) != len(cards) or len(set(identities)) != len(cards):
        raise ValueError("Tatkniga returned duplicate publication cards within a page.")
    next_url = targets.pop()
    if (current < last) != (next_url is not None):
        raise ValueError("Tatkniga next-page link disagrees with the advertised last page.")
    following = []
    if next_url:
        if (not same_origin(next_url, root) or urlsplit(next_url).path.rstrip("/") != urlsplit(root).path.rstrip("/")
                or page_number(next_url) != current + 1):
            raise ValueError("Tatkniga next-page link does not advance within the library.")
        following = [PageRequest(next_url, context={"last_page": last, "page_size": size})]
    return ListingPage(records, following, entries=len(cards), detect_repeats=True,
                       fingerprint=json.dumps(identities), record_context=contexts)


def language_selection(values):
    if not values:
        return "review"
    tokens = [token.strip().strip(".") for value in values
              for token in re.split(r"[,;/+&]|\s+и\s+", value.casefold()) if token.strip()]
    if any(token in TATAR_LABELS or ("крым" not in token
           and (token.startswith("татарско-") or token.endswith("-татарский"))) for token in tokens):
        return "selected"
    return "excluded" if tokens and all(token in OTHER_LANGUAGES for token in tokens) else "review"


def record(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1.changeName")
    product = soup.select_one("#catalogElement")
    browse = product.select_one("#browse") if product else None
    if (heading is None or product is None or browse is None or not same_origin(page_url, ARCHIVE_URL)
            or not BOOK_PATH.fullmatch(urlsplit(page_url).path)):
        raise ValueError("Current Tatkniga publication structure is missing.")
    clean_heading = BeautifulSoup(str(heading), "html.parser")
    for marker in clean_heading.select(".marker"):
        marker.decompose()
    metadata = {"url": page_url, "title_raw": heading.get_text(" ", strip=True),
                "title": clean_heading.get_text(" ", strip=True),
                "admission_reason": "Publication listed in Tatkniga's current public library."}
    for parent in product.parents:
        native = PRODUCT_ID.fullmatch(parent.get("id", ""))
        if native:
            metadata["product_id"] = native.group(1)
            break
    properties, languages, authors = [], [], []
    for row in browse.select(".propertyTable"):
        name, value = row.select_one(".propertyName"), row.select_one(".propertyValue")
        if name is None or value is None:
            raise ValueError("Tatkniga bibliographic property is incomplete.")
        label, text = name.get_text(" ", strip=True), value.get_text(" ", strip=True)
        item = {"name": label, "value": text}
        if item not in properties:
            properties.append(item)
        key = label.casefold().rstrip(":")
        if key == "язык" and text and text not in languages:
            languages.append(text)
        if key in {"автор", "авторы"} and text:
            supplied = [a.get_text(" ", strip=True) for a in value.select("a")] or [text]
            authors.extend(a for a in supplied if a and a not in authors)
        for raw_key, field in (("издательство", "publisher_raw"), ("год издания", "publication_year_raw"),
                               ("isbn", "isbn_raw"), ("количество страниц", "pages_raw")):
            if key == raw_key and text:
                metadata[field] = text
    metadata["properties_raw"] = properties
    metadata["language_selection"] = language_selection(languages)
    if languages:
        metadata["language_raw"] = " / ".join(languages)
    if authors:
        metadata["authors_raw"] = authors
    description = browse.select_one(".description")
    if description and description.get_text(" ", strip=True):
        metadata["description"] = description.get_text(" ", strip=True)
    assets = {}
    for anchor in product.select("a[href]"):
        if anchor.find_parent(class_="sku") is not None:
            continue  # Related products are not attachment sources for this record.
        url = canonical(anchor["href"], page_url)
        path = unquote(urlsplit(url).path)
        extension = PurePosixPath(path).suffix.lower()
        label = anchor.get_text(" ", strip=True)
        reader = path.startswith(("/reader/", "/upload/interactive_books/"))
        explicit = bool(re.search(r"читать|скачать|укырга|йөклә", label.casefold()))
        if extension not in DIRECT_FORMATS and not explicit and not reader:
            continue
        reason, code = None, None
        if reader or extension in {".html", ".htm"}:
            code, reason = "reader_deferred", "Interactive readers are deferred to the next phase."
        elif extension not in DIRECT_FORMATS:
            code, reason = "format_unsupported", "No directly linked supported document file; audio and archive expansion are out of scope."
        elif not same_origin(url, page_url):
            code, reason = "external_origin", "Document is outside the configured Tatkniga origin."
        elif metadata["language_selection"] == "review":
            code, reason = "language_unknown", "An explicit recognized Tatar language label is required; record remains available for review."
        elif metadata["language_selection"] == "excluded":
            code, reason = "language_excluded", "Source language metadata does not identify a Tatar-containing edition."
        assets.setdefault(url, {"url": url, "label": label, "extension": extension,
                                "unsupported_reason": reason, "unsupported_code": code})
    metadata["attachments"] = [{k: a[k] for k in ("url", "label", "unsupported_code")} for a in assets.values()]
    return metadata, list(assets.values())


def record_key(metadata):
    return "product:" + metadata["product_id"] if metadata.get("product_id") else metadata["url"]


def resolve_record(http, metadata, assets):
    from .tatkniga_reader import resolve

    return resolve(http, metadata, assets)


def download(http, manifest, summary, log, recheck):
    from .core import download as download_documents
    from .image_issues import download as download_books

    summary.update(download_unit="file_or_book", pdf_assembled=0, pdf_reused=0)
    download_documents(http, manifest, summary, log, recheck)
    download_books(http, manifest, summary, log, recheck, unit="file_or_book")
