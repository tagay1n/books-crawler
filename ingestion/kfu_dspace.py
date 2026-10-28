"""Public academic KFU PDFs, discovered through the native Tatar topic search."""

import copy
import json
from email.message import Message
from pathlib import PurePosixPath
import re
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit

from bs4 import BeautifulSoup
import pymupdf

from .documents import canonical, same_origin
from .kfu import language_selection
from .network import InvalidDocument
from .paging import CatalogChanged, ListingPage, PageRequest


ORIGIN = "https://dspace.kpfu.ru"
ARCHIVE_URL = ORIGIN + "/xmlui/discover"
QUERY = "татар"
PARSER_VERSION = 2
UNIQUE_RECORDS = True
SEARCH = {"query": QUERY, "rpp": "10", "group_by": "none", "etal": "0"}


def search_url(page=1):
    return ARCHIVE_URL + "?" + urlencode({**SEARCH, "page": str(page)})


def search_page(url):
    parsed = urlsplit(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    page = query.pop("page", ["1"])
    if (not same_origin(url, ORIGIN) or parsed.path != "/xmlui/discover" or parsed.fragment
            or query != {key: [value] for key, value in SEARCH.items()}
            or len(page) != 1 or not re.fullmatch(r"[1-9]\d*", page[0])):
        raise ValueError("Academic KFU search lost its fixed query or native pagination settings.")
    return int(page[0])


def handle(url):
    parsed = urlsplit(url)
    match = re.fullmatch(r"/xmlui/handle/(net/[1-9]\d*)", parsed.path)
    if (not same_origin(url, ORIGIN) or parsed.fragment or match is None
            or parse_qs(parsed.query, keep_blank_values=True) not in ({}, {"show": ["full"]})):
        raise ValueError("Invalid academic KFU handle URL.")
    return match[1]


def safe_filename(name):
    if (not name or name in {".", ".."} or any(c in name for c in "/\\")
            or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError("Unsafe academic KFU filename.")
    return name


def original_url(viewer, identity):
    parsed = urlsplit(viewer)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (not same_origin(viewer, ORIGIN) or parsed.path not in {"/xmlui/viewer", "/xmlui/viewer-img"} or parsed.fragment
            or set(query) != {"file", "sequence", "isAllowed"}
            or any(len(values) != 1 for values in query.values())):
        raise ValueError("Unexpected academic KFU viewer route.")
    parts = query["file"][0].split(";")
    if len(parts) != 2 or "net/" + parts[0] != identity:
        raise ValueError("Academic KFU viewer belongs to another record.")
    name = safe_filename(parts[1])
    if not re.fullmatch(r"-1|[1-9]\d*", query["sequence"][0]) or query["isAllowed"][0] not in {"y", "n"}:
        raise ValueError("Invalid academic KFU viewer sequence or access flag.")
    # PDF paths follow the site's linked PDF.js script; other formats remain inventory.
    url = (f"{ORIGIN}/xmlui/bitstream/handle/{identity}/{quote(name, safe='')}?"
           + urlencode({"sequence": query["sequence"][0], "isAllowed": query["isAllowed"][0]}))
    return url, name, query["isAllowed"][0] == "y"


def bitstream(url, *, public_only=True):
    parsed = urlsplit(url)
    match = re.fullmatch(r"/xmlui/bitstream/handle/(net/[1-9]\d*)/([^/]+)", parsed.path)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (not same_origin(url, ORIGIN) or parsed.fragment or match is None
            or set(query) != {"sequence", "isAllowed"}
            or query["isAllowed"] not in (["y"], ["n"]) or (public_only and query["isAllowed"] != ["y"])
            or len(query["sequence"]) != 1 or not re.fullmatch(r"-1|[1-9]\d*", query["sequence"][0])):
        raise ValueError("Unexpected academic KFU original-file route.")
    return match[1], safe_filename(unquote(match[2])), query["sequence"][0]


def initial_request(root):
    return PageRequest(search_url())


def verification_request(root, count):
    return PageRequest(search_url(), context={"verify": True, "count": count})


def parse_listing(html, request, root):
    page_number = search_page(request.url)
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("#ds-body")
    counter = re.search(r"Отображаемые элементы\s+(\d+)-(\d+)\s+из\s+(\d+)",
                        main.get_text(" ", strip=True) if main else "")
    if main is None or counter is None:
        raise ValueError("Academic KFU search result range is missing.")
    first, last, count = map(int, counter.groups())
    if "count" in request.context and request.context["count"] != count:
        raise CatalogChanged("Academic KFU result count changed; restart discovery.")
    records = []
    for anchor in main.select("#aspect_discovery_SimpleSearch_div_search-results .artifact-title a[href]"):
        target = canonical(anchor["href"], request.url)
        identity = handle(target)
        if urlsplit(target).query:
            raise ValueError("Unexpected academic KFU result handle query.")
        records.append(f"{ORIGIN}/xmlui/handle/{identity}?show=full")
    offset = (page_number - 1) * 10
    if (not records or first != offset + 1 or last != offset + len(records)
            or len(records) != min(10, count - offset)):
        raise ValueError("Academic KFU displayed range disagrees with its records.")
    if len(set(records)) != len(records):
        raise CatalogChanged("Academic KFU search repeated an item.")
    if request.context.get("verify"):
        return ListingPage([], [], advertised=count, validation=True)
    following = []
    if last < count:
        links = {search_page(canonical(a["href"], request.url))
                 for a in main.select("a.next-page-link[href]")}
        if links != {page_number + 1}:
            raise ValueError("Academic KFU native next-page link is missing or inconsistent.")
        following = [PageRequest(search_url(page_number + 1), context={"count": count})]
    return ListingPage(records, following, entries=len(records), advertised=count,
                       fingerprint=json.dumps(records), detect_repeats=True,
                       record_context={url: {"query": QUERY, "listing_url": request.url} for url in records})


def record(html, page_url):
    identity = handle(page_url)
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("#ds-body")
    table = main.select_one("table.detailtable") if main else None
    dc = [{"name": m["name"], "content": m.get("content")} for m in soup.select('meta[name^="DC."]')]
    identifiers = [m["content"] for m in dc if m["name"] == "DC.identifier"]
    expected = f"{ORIGIN}/xmlui/handle/{identity}"
    self_links = {canonical(a["href"], page_url) for a in main.select("p.item-view-toggle a[href]")} if main else set()
    item_identifiers = {value.replace("http:", "https:", 1) for value in identifiers
                        if isinstance(value, str) and re.match(r"https?://dspace\.kpfu\.ru/xmlui/handle/", value)}
    # Older thesis records omit dc.identifier.uri. Their native full/short-view
    # toggle still identifies the item; unrelated identifier fields are not URIs.
    if table is None or self_links != {expected} or (item_identifiers and item_identifiers != {expected}):
        raise ValueError("Academic KFU full item metadata is missing or belongs to another record.")
    fields = []
    for row in table.select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 3:
            raise ValueError("Malformed academic KFU full metadata row.")
        fields.append({"name": cells[0].get_text(strip=True), "value": cells[1].get_text(" ", strip=True),
                       "metadata_locale": cells[2].get_text(strip=True)})
    def values(name):
        return [f["value"] for f in fields if f["name"] == name and f["value"]]
    titles = values("dc.title")
    if len(titles) != 1:
        raise ValueError("Academic KFU item does not declare one title.")
    languages = values("dc.language.iso") + values("dc.language")
    languages += [m["content"] for m in dc if m["name"] == "DC.language" and m["content"]]
    languages = list(dict.fromkeys(languages))
    selection = language_selection(languages)
    rights = values("dc.rights")
    restricted = any(any(label in value.casefold() for label in
                     ("только для кфу", "закрытый доступ", "ограниченный доступ", "restricted access", "closed access"))
                     for value in rights)
    inventory, assets = [], {}
    for block in main.select(".file-wrapper"):
        area = block.select_one(".file-metadata")
        if area is None:
            raise ValueError("Academic KFU attachment lacks its file metadata.")
        filename = area.select_one("span[title]")
        raw_name = filename["title"] if filename else None
        links = list(dict.fromkeys(canonical(a["href"], page_url) for a in block.select(".file-link a[href]")))
        entry = {"description_raw": area.get_text(" ", strip=True), "filename_raw": raw_name,
                 "links": links, "restricted_by_record": restricted}
        inventory.append(entry)
        for viewer in links:
            if urlsplit(viewer).path.startswith("/xmlui/bitstream/"):
                reference, name, sequence = bitstream(viewer, public_only=False)
                if reference != identity:
                    raise ValueError("Academic KFU original belongs to another record.")
                url, allowed = viewer, parse_qs(urlsplit(viewer).query)["isAllowed"] == ["y"]
            else:
                url, name, allowed = original_url(viewer, identity)
            if raw_name is not None and name != raw_name:
                raise ValueError("Academic KFU viewer filename disagrees with item metadata.")
            extension = PurePosixPath(name).suffix.lower()
            code = ("kfu_restricted" if restricted or not allowed else "unsupported_format" if extension != ".pdf"
                    else "language_excluded" if selection == "excluded" else "language_unknown" if selection != "selected" else None)
            reasons = {"kfu_restricted": "Source marks this item/file as restricted; access follow-up is deferred.",
                       "unsupported_format": "This academic KFU adapter acquires original PDFs only.",
                       "language_excluded": "Source language metadata does not identify Tatar content.",
                       "language_unknown": "Document language is missing or unknown; an explicit file review is required."}
            assets[url] = {"url": url, "label": name, "extension": extension, "filename_raw": name,
                           "viewer_url": viewer, "source_asset_key": "original:" + url,
                           "source_unsupported_code": code, "source_unsupported_reason": reasons.get(code),
                           "unsupported_code": code, "unsupported_reason": reasons.get(code)}
    metadata = {"url": expected, "handle": identity, "title": titles[0], "title_raw": titles[0],
                "full_metadata_url": page_url, "fields_raw": fields, "dc_metadata": dc,
                "language_raw": languages, "language_selection": selection, "rights_raw": rights,
                "authors_raw": values("dc.contributor.author"), "dates_raw": values("dc.date.issued"),
                "series_raw": values("dc.relation.ispartofseries"), "files": inventory,
                "admission_reason": "Tatar topic search is discovery only; acquisition requires explicit item-language metadata or a hash-pinned manual file review."}
    return metadata, list(assets.values())


def record_key(metadata):
    return metadata["handle"]


def load_reviews(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("files"), dict):
        raise ValueError("Academic KFU language-reviews.json must contain version=1 and a files mapping.")
    for url, review in data["files"].items():
        bitstream(url)
        if (not isinstance(review, dict) or not re.fullmatch(r"[a-f0-9]{64}", str(review.get("sha256", "")))
                or not isinstance(review.get("languages"), list)
                or not all(isinstance(label, str) and label.strip() for label in review["languages"])
                or language_selection(review["languages"]) != "selected"
                or not all(isinstance(review.get(key), str) and review[key].strip() for key in ("reviewer", "reason"))):
            raise ValueError("Each academic KFU file review requires SHA-256, Tatar language labels, reviewer and reason.")
    return data["files"]


def resolve_record(http, metadata, assets):
    for asset in assets:
        asset.update(language_review=None, source_version=None,
                     unsupported_code=asset["source_unsupported_code"],
                     unsupported_reason=asset["source_unsupported_reason"])
        review = http.language_reviews.get(asset["url"])
        if review and asset.get("unsupported_code") in {"language_unknown", "language_excluded"}:
            asset.update(language_review=review, source_version=review["sha256"],
                         unsupported_code=None, unsupported_reason=None)
    metadata["language_reviews"] = [{**a["language_review"], "url": a["url"]} for a in assets if a.get("language_review")]
    metadata["attachments"] = [{k: a[k] for k in ("url", "label", "unsupported_code")} for a in assets]
    return metadata, assets


def prepare_http(http, session_file):
    http.language_reviews = load_reviews(http.settings.artifacts_root / "kfu_dspace" / "language-reviews.json")
    http.session.headers.update({"Accept-Language": "ru,en;q=0.5", "Cache-Control": "no-cache"})
    def route(url):
        if urlsplit(url).path == "/xmlui/discover":
            return ("search", search_page(url))
        if urlsplit(url).path.startswith("/xmlui/bitstream/"):
            return ("file", *bitstream(url))
        identity = handle(url)
        return ("record", identity, bool(urlsplit(url).query))
    def validate_request(method, url, data):
        if method != "GET" or data:
            raise ValueError("Academic KFU acquisition permits read-only GET requests only.")
        route(url)
    def check_response(response, *args, **kwargs):
        try:
            current = route(response.url)
            if response.is_redirect and route(canonical(response.headers["Location"], response.url)) != current:
                raise ValueError("Academic KFU redirect changed the source resource.")
        except (ValueError, KeyError):
            response.close()
            raise InvalidDocument("Academic KFU returned a login redirect or unexpected resource route.") from None
        return response
    def validate_download(response, asset):
        expected = bitstream(asset["url"])
        for hop in [*response.history, response]:
            if bitstream(hop.url) != expected:
                raise InvalidDocument("Academic KFU download response belongs to another file.")
        disposition = Message()
        disposition["Content-Disposition"] = response.headers.get("Content-Disposition", "")
        filename = disposition.get_filename()
        if filename is not None and filename != asset["filename_raw"]:
            raise InvalidDocument("Academic KFU response filename disagrees with item metadata.")
    def validate_acquisition(asset):
        if asset.get("language_review") != http.language_reviews.get(asset["url"]) and asset.get("language_review"):
            raise InvalidDocument("File language review changed or was withdrawn; rediscover before acquisition.")
    def validate_acquired(asset, result):
        review = asset.get("language_review")
        if review and result["sha256"] != review["sha256"]:
            raise InvalidDocument("Downloaded PDF differs from its language-reviewed SHA-256; manual review is required.")
        return {"language_review_sha256": review["sha256"]} if review else {}
    http.validate_request = validate_request
    http.session.hooks["response"].append(check_response)
    http.validate_download_response = validate_download
    http.validate_acquisition = validate_acquisition
    http.validate_acquired_asset = validate_acquired


def validate_pdf(path):
    try:
        with pymupdf.open(path) as pdf:
            if pdf.needs_pass or pdf.page_count < 1:
                raise ValueError("PDF is encrypted or has no readable pages.")
            return {"pages": pdf.page_count}
    except (RuntimeError, ValueError) as error:
        raise InvalidDocument(f"Invalid academic KFU PDF: {error}") from error


def download(http, manifest, summary, log, recheck):
    from .core import download as download_originals
    # Reapply current reviews without requiring a full catalog rescan. Observation
    # history preserves granted/withdrawn reviews and the original source decision.
    keys = ("url", "label", "extension", "filename_raw", "viewer_url", "source_asset_key",
            "source_unsupported_code", "source_unsupported_reason")
    grouped = {}
    for asset in manifest.data["assets"].values():
        if asset.get("current", True):
            grouped.setdefault(asset.get("record_key", asset["record_url"]), []).append(asset)
    for key, record_state in list(manifest.data["records"].items()):
        http.budget.check()
        metadata = copy.deepcopy(record_state["observations"][-1]["metadata"])
        current_assets = grouped.get(key, [])
        descriptors = [{field: asset[field] for field in keys} for asset in current_assets]
        metadata, descriptors = resolve_record(http, metadata, descriptors)
        changed = (metadata != record_state["observations"][-1]["metadata"]
                   or record_state["observations"][-1]["parser_version"] != PARSER_VERSION
                   or any(any(asset.get(field) != value for field, value in descriptor.items())
                          for asset, descriptor in zip(current_assets, descriptors)))
        if changed:
            manifest.observe(metadata, descriptors, PARSER_VERSION, record_key=key)
    download_originals(http, manifest, summary, log, recheck, extensions={".pdf"}, validate_file=validate_pdf)
