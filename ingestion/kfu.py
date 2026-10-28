"""KFU historical collections: public documents and colour page-image PDFs."""

import json
from email.message import Message
from pathlib import PurePosixPath
import re
from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup
from requests.utils import requote_uri

from .documents import DOCUMENT_EXTENSIONS, canonical, same_origin
from .network import InvalidDocument
from .paging import CatalogChanged, ListingPage, PageRequest


ORIGIN = "https://repo.kpfu.ru"
COLLECTIONS = {"27574": "books", "18503": "manuscripts", "28060": "il", "25046": "shura"}
PERIODICALS = {"28060": ("Ил", "newspaper"), "25046": ("Шура", "journal")}
DOCUMENT_FORMATS = DOCUMENT_EXTENSIONS - {".html", ".htm"}
TATAR_LABELS = {"tt", "tat", "tatar", "татарский", "татарча", "татар теле"}
OTHER_LANGUAGE_LABELS = {"ru", "rus", "russian", "русский", "ar", "ara", "arabic", "арабский",
                         "fa", "fas", "per", "persian", "персидский", "ba", "bak", "bashkir", "башкирский",
                         "crh", "crimean tatar", "крымскотатарский", "tr", "tur", "turkish", "турецкий",
                         "en", "eng", "english", "английский", "de", "deu", "ger", "german", "немецкий"}


def language_selection(values):
    labels = {" ".join(value.casefold().split()) for value in values if isinstance(value, str) and value.strip()}
    if labels & TATAR_LABELS:
        return "selected"
    return "excluded" if labels and labels <= OTHER_LANGUAGE_LABELS else "review"


def select_tatar(metadata, assets, *, publication="Il"):
    selection = language_selection(metadata.get("language_raw", []))
    metadata.update(language_selection=selection,
                    admission_reason=f"{publication} issue acquisition requires an explicit source Tatar language label; metadata remains an unverified source claim.")
    if selection != "selected":
        code = "language_excluded" if selection == "excluded" else "language_unknown"
        reason = ("Source language metadata does not identify a Tatar-containing issue." if selection == "excluded"
                  else "Missing or unrecognized source language metadata requires review before acquisition.")
        for asset in assets:
            # Keep restrictions as the primary access decision on restricted assets.
            if asset.get("unsupported_code") in {None, "kfu_reader"}:
                asset.update(unsupported_code=code, unsupported_reason=reason)
        for entry in metadata["files"]:
            if entry["selection_reason"] in {"eligible", "kfu_reader"}:
                entry["selection_reason"] = code
    return metadata, assets


def handle(url):
    parsed = urlsplit(url)
    match = re.fullmatch(r"/jspui/handle/(net/[1-9]\d*)/?", parsed.path)
    if not same_origin(url, ORIGIN) or parsed.fragment or match is None:
        raise ValueError("Invalid KFU record handle URL.")
    return match[1]


def bitstream(url):
    parsed = urlsplit(url)
    match = re.fullmatch(r"/jspui/bitstream/(net/[1-9]\d*)/([1-9]\d*)/(.+)", parsed.path)
    if not same_origin(url, ORIGIN) or parsed.query or parsed.fragment or match is None:
        raise ValueError("Invalid KFU bitstream URL.")
    name = unquote(match[3])
    if ("\\" in name or any(part in {"", ".", ".."} for part in name.split("/"))
            or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError("Unsafe KFU bitstream filename.")
    return match[1], match[2], name


def reader_reference(url):
    parsed = urlsplit(url)
    match = re.fullmatch(r"(net/[1-9]\d*)/([1-9]\d*)-([1-9]\d*)/view", parsed.query)
    if (not same_origin(url, ORIGIN) or parsed.path != "/jspui/bitstream.jsp"
            or parsed.fragment or match is None or int(match[3]) < int(match[2])):
        raise ValueError("Invalid KFU image-reader URL.")
    return match[1], int(match[2]), int(match[3])


def offset(url, root):
    if handle(url) != handle(root):
        raise ValueError("KFU listing is outside the selected collection.")
    query = parse_qs(urlsplit(url).query, keep_blank_values=True)
    if not query:
        return 0
    values = query.get("offset", [])
    if set(query) != {"offset"} or len(values) != 1 or not values[0].isdecimal():
        raise ValueError("KFU collection pagination requires a nonnegative native offset.")
    return int(values[0])


def parse_listing(html, request, root):
    start = offset(request.url, root)
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main#content")
    table = main.select_one('table[summary="This table browses all dspace content"]') if main else None
    counter = re.search(r"Ресурсы коллекции с (\d+) по (\d+) из (\d+)",
                        " ".join(main.get_text(" ", strip=True).split()) if main else "")
    if table is None or counter is None:
        raise ValueError("KFU collection table or advertised range is missing.")
    first, last, count = map(int, counter.groups())
    if "count" in request.context and count != request.context["count"]:
        raise CatalogChanged("KFU collection count changed; the next invocation starts a fresh scan.")
    records = []
    for row in table.select("tr"):
        if not row.select_one("td"):
            continue
        anchor = row.select_one('td[headers~="t3"] a[href]')
        if anchor is None:
            raise ValueError("KFU collection row has no title/record link.")
        url = canonical(anchor["href"], request.url)
        item_handle = handle(url)
        if urlsplit(url).query or item_handle.rsplit("/", 1)[1] in COLLECTIONS:
            raise ValueError("KFU catalog row is not an item record.")
        records.append(f"{ORIGIN}/jspui/handle/{item_handle}")
    if not records or first != start + 1 or last != start + len(records) or last > count:
        raise ValueError("KFU collection range disagrees with its rows or requested offset.")
    if len(set(records)) != len(records):
        raise CatalogChanged("KFU collection repeats a record within a page.")
    page_size = request.context.get("page_size", len(records))
    if len(records) != min(page_size, count - start):
        raise ValueError("KFU collection returned an incomplete pagination batch.")
    if request.context.get("verify"):
        return ListingPage([], [], advertised=count, validation=True)
    forward = set()
    for anchor in main.select('a[href*="offset="]'):
        url = canonical(anchor["href"], request.url)
        if not same_origin(url, root) or urlsplit(url).path.rstrip("/") != urlsplit(root).path.rstrip("/"):
            continue
        position = offset(url, root)
        if position > start:
            forward.add(position)
    if forward != ({last} if last < count else set()):
        raise ValueError("KFU next-page link does not agree with the displayed range.")
    following = [PageRequest(root + f"?offset={last}",
                             context={"count": count, "page_size": page_size})] if last < count else []
    context = {"collection_url": root, "collection_handle": handle(root)}
    return ListingPage(records, following, entries=len(records), advertised=count,
                       fingerprint=json.dumps(records), detect_repeats=True,
                       record_context={url: context for url in records})


def verification_request(root, count):
    return PageRequest(root, context={"verify": True, "count": count})


def record(html, page_url):
    item_handle = handle(page_url)
    if urlsplit(page_url).query or item_handle.rsplit("/", 1)[1] in COLLECTIONS:
        raise ValueError("KFU metadata URL is not an item record.")
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main#content")
    table = main.select_one("table.itemDisplayTable") if main else None
    dc = [{"name": tag["name"], "content": tag.get("content")}
          for tag in soup.select('meta[name^="DC."]')]
    title = next((entry["content"] for entry in dc if entry["name"] == "DC.title" and entry["content"]), None)
    identifiers = [entry["content"] for entry in dc if entry["name"] == "DC.identifier"]
    canonical_url = f"{ORIGIN}/jspui/handle/{item_handle}"
    if table is None or title is None or canonical_url not in identifiers:
        raise ValueError("KFU item metadata is missing, mismatched, or replaced by a login page.")
    bibliography = []
    for row in table.select("tr"):
        label, value = row.select_one(".metadataFieldLabel"), row.select_one(".metadataFieldValue")
        if label is None or value is None:
            raise ValueError("KFU bibliographic row is malformed.")
        bibliography.append({"label_raw": label.get_text(" ", strip=True),
                             "value_raw": value.get_text("\n", strip=True),
                             "field_classes": value.get("class", [])})
    inventory, assets = [], {}
    for block in main.select(".fileBlock"):
        info = block.select_one(".fileInfo, .fileInfo-full")
        if info is None:
            raise ValueError("KFU file block has no file-information area.")
        descriptions = {}
        for detail in info.select(".fileDesc"):
            label = detail.select_one(".labelHeading")
            if label is not None:
                value = label.find_next_sibling("span")
                descriptions[label.get_text(" ", strip=True)] = value.get_text(" ", strip=True) if value else None
        links = [{"label_raw": a.get_text(" ", strip=True), "url": requote_uri(canonical(a["href"], page_url))}
                 for a in info.select("a[href]") if not a["href"].startswith(("javascript:", "#"))]
        copy_requests = [link["url"] for link in links if urlsplit(link["url"]).path == "/jspui/request-item"]
        restricted = bool(copy_requests or info.select_one(".glyphicon-lock")
                          or "Ограниченный доступ" in info.get_text(" ", strip=True))
        entry = {"description_fields": descriptions, "description_raw": info.get_text(" ", strip=True),
                 "restricted": restricted, "links": links, "copy_request_urls": copy_requests}
        inventory.append(entry)
        documents = [link for link in links if urlsplit(link["url"]).path.startswith("/jspui/bitstream/")]
        entry["selection_reason"] = "reader_or_metadata_only"
        for link in links:
            target = link["url"]
            if urlsplit(target).path != "/jspui/bitstream.jsp":
                continue
            reference, first, last = reader_reference(target)
            if reference != item_handle:
                raise ValueError("KFU image reader belongs to another record.")
            code = "kfu_restricted" if restricted else "kfu_reader"
            assets[target] = {"url": target, "label": descriptions.get("Файл:") or "Image reader",
                              "source_asset_key": f"reader:{first}-{last}",
                              "filename_raw": descriptions.get("Файл:"),
                              "displayed_count_raw": descriptions.get("Объем:"),
                              "format_raw": descriptions.get("Формат:"),
                              "unsupported_code": code,
                              "unsupported_reason": "Restricted KFU image reader." if restricted else "Reader awaits page enumeration."}
            entry["selection_reason"] = code
        for link in documents:
            target = link["url"]
            reference, sequence, name = bitstream(target)
            if reference != item_handle:
                raise ValueError("KFU file link belongs to another record.")
            extension = PurePosixPath(name).suffix.lower()
            if extension not in DOCUMENT_FORMATS:
                entry["selection_reason"] = "unsupported_format"
                continue
            code = "kfu_restricted" if restricted else None
            entry["selection_reason"] = code or "eligible"
            assets[target] = {"url": target, "label": descriptions.get("Файл:") or name,
                              "source_asset_key": f"bitstream:{sequence}:{name}", "extension": extension,
                              "filename_raw": name, "displayed_size_raw": descriptions.get("Объем:"),
                              "format_raw": descriptions.get("Формат:"), "copy_request_urls": copy_requests,
                              "unsupported_code": code,
                              "unsupported_reason": "KFU marks this document as restricted; copy/access follow-up is deferred." if code else None}
    if not inventory and main.select_one('a[href*="/bitstream/"]'):
        raise ValueError("KFU file links exist outside the expected per-file structure.")
    metadata = {"url": canonical_url, "handle": item_handle, "title": " ".join(title.split()),
                "title_raw": title, "dc_metadata": dc, "bibliography_raw": bibliography,
                "files": inventory,
                "admission_reason": "Record in the selected KFU historical collection; all supplied language labels are retained without filtering.",
                "attachments": [{"url": a["url"], "label": a["label"], "restricted": bool(a["unsupported_reason"])}
                                for a in assets.values()]}
    languages = [entry["content"] for entry in dc if entry["name"] == "DC.language"]
    if languages:
        metadata["language_raw"] = languages
    return metadata, list(assets.values())


def record_key(metadata):
    return metadata["handle"]


def resolve_record(http, metadata, assets):
    from .kfu_reader import resolve

    return resolve(http, metadata, assets)


def download(http, manifest, summary, log, recheck, *, unit="file_or_book"):
    from .core import download as download_documents
    from .image_issues import download as download_images

    summary.update(download_unit=unit, pdf_assembled=0, pdf_reused=0)
    download_documents(http, manifest, summary, log, recheck)
    download_images(http, manifest, summary, log, recheck, unit=unit)


def prepare_http(http, session_file, *, listing_route=None):
    http.session.headers.update({"Accept-Language": "ru,en;q=0.5"})

    def route(url):
        if not same_origin(url, ORIGIN):
            raise ValueError("KFU acquisition must stay on its HTTPS source origin.")
        if urlsplit(url).path.startswith("/jspui/bitstream/"):
            return ("file", *bitstream(url))
        if urlsplit(url).path == "/jspui/bitstream.jsp":
            return ("reader", *reader_reference(url))
        parsed = urlsplit(url)
        manifest = re.fullmatch(r"/api/manifest/(net/[1-9]\d*)/([1-9]\d*)-([1-9]\d*)/info.json", parsed.path)
        if manifest and not parsed.query and not parsed.fragment and int(manifest[3]) >= int(manifest[2]):
            return ("manifest", manifest[1], int(manifest[2]), int(manifest[3]))
        if listing_route is not None and urlsplit(url).path == urlsplit(http.settings.archive_url).path:
            return ("listing", listing_route(url))
        native = handle(url)
        if native.rsplit("/", 1)[1] in COLLECTIONS:
            offset(url, http.settings.archive_url)
        elif urlsplit(url).query:
            raise ValueError("KFU record requests must not include query parameters.")
        return ("record", native)

    def validate_request(method, url, data):
        if method != "GET" or data:
            raise ValueError("KFU ingestion permits read-only GET requests only.")
        route(url)

    def check_response(response, *args, **kwargs):
        try:
            current = route(response.url)
            if response.is_redirect and route(canonical(response.headers["Location"], response.url)) != current:
                raise ValueError("KFU redirect changed the source resource.")
        except (ValueError, KeyError):
            response.close()
            raise InvalidDocument("KFU returned a login redirect or an unexpected resource route.") from None
        return response

    def validate_download(response, asset):
        expected = bitstream(asset["url"])
        for hop in [*response.history, response]:
            if bitstream(hop.url) != expected:
                raise InvalidDocument("KFU download response belongs to a different file.")
        if asset.get("kind") == "page_image":
            disposition = Message()
            disposition["Content-Disposition"] = response.headers.get("Content-Disposition", "")
            filename = disposition.get_filename()
            if filename is not None and filename != asset["filename_raw"]:
                raise InvalidDocument("KFU original image filename disagrees with the advertised numbered range.")

    http.validate_request = validate_request
    http.session.hooks["response"].append(check_response)
    http.validate_download_response = validate_download


class CollectionAdapter:
    PARSER_VERSION = 3
    UNIQUE_RECORDS = True
    parse_listing = staticmethod(parse_listing)
    verification_request = staticmethod(verification_request)
    record_key = staticmethod(record_key)
    prepare_http = staticmethod(prepare_http)
    resolve_record = staticmethod(resolve_record)

    def __init__(self, collection_id, *, tatar_only=False):
        if collection_id not in COLLECTIONS:
            raise ValueError("Unknown KFU collection.")
        self.ARCHIVE_URL = f"{ORIGIN}/jspui/handle/net/{collection_id}"
        self.tatar_only = tatar_only
        self.collection_id = collection_id

    def record(self, html, page_url):
        metadata, assets = record(html, page_url)
        if self.collection_id in PERIODICALS:
            title, kind = PERIODICALS[self.collection_id]
            metadata["publication"] = {
                "title": title, "kind": kind, "issue_title_raw": metadata["title_raw"],
                "publication_dates_raw": [row["value_raw"] for row in metadata["bibliography_raw"]
                                          if "dc_date_issued" in row["field_classes"]],
                "series_raw": [row["value_raw"] for row in metadata["bibliography_raw"]
                               if "dc_relation_ispartofseries" in row["field_classes"]],
            }
        return (select_tatar(metadata, assets, publication="Shura" if self.collection_id == "25046" else "Il")
                if self.tatar_only else (metadata, assets))

    def download(self, http, manifest, summary, log, recheck):
        return download(http, manifest, summary, log, recheck,
                        unit="file_or_issue" if self.collection_id in PERIODICALS else "file_or_book")
