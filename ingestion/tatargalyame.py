"""Tatar Galyame's public catalog API and explicitly listed hosted documents."""

import json
from pathlib import PurePosixPath
import re
from urllib.parse import parse_qs, quote, unquote, urlsplit

from requests.utils import requote_uri

from .documents import DOCUMENT_EXTENSIONS, canonical, same_origin
from .network import InvalidDocument
from .paging import ListingPage, PageRequest


ORIGIN = "https://tatargalyame.kpfu.ru"
ARCHIVE_URL = ORIGIN + "/catalogue"
PARSER_VERSION = 1
DOCUMENT_FORMATS = DOCUMENT_EXTENSIONS - {".html", ".htm"}
UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
CATEGORY = r"[a-z][a-z0-9_-]*"
HIDDEN_TYPES = {"QA", "HIDDEN"}


def filename(value):
    if (not isinstance(value, str) or not value.strip() or value in {".", ".."}
            or any(c in value for c in "/\\")
            or re.search(r"%[0-9a-fA-F]{2}", value)
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError("Unsafe or ambiguous Tatar Galyame attachment filename.")
    return value


def route(url):
    parsed = urlsplit(url)
    if not same_origin(url, ORIGIN) or parsed.fragment:
        raise ValueError("Tatar Galyame acquisition must stay on its HTTPS source origin.")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if parsed.path == "/api/struct" or parsed.path.startswith("/api/struct/"):
        path = parsed.path[len("/api/struct"):]
        parts = path[1:].split("/") if path else []
        if (len(parts) > 12 or any(not re.fullmatch(CATEGORY, p) for p in parts)
                or query != {"lang": ["tt"], "q": [""]}):
            raise ValueError("Invalid unfiltered Tatar Galyame category API URL.")
        return "category", tuple(parts)
    match = re.fullmatch(rf"/api/sid/({UUID})", parsed.path)
    if match and query == {"lang": ["tt"]}:
        return "resource", match[1]
    match = re.fullmatch(rf"/files/({UUID})/([^/]+)", parsed.path)
    if match and not parsed.query:
        return "file", match[1], filename(unquote(match[2]))
    raise ValueError("Unexpected Tatar Galyame API or hosted-file route.")


def category_url(parts):
    return ORIGIN + "/api/struct" + ("/" + "/".join(parts) if parts else "") + "?lang=tt&q="


def initial_request(root):
    return PageRequest(category_url([]))


def payload(raw, expected):
    data = json.loads(raw)
    if (not isinstance(data, dict) or data.get("name") != expected
            or not isinstance(data.get("list"), list) or not isinstance(data.get("parents"), list)):
        raise ValueError("Tatar Galyame returned an unexpected API payload.")
    for parent in data["parents"]:
        if (not isinstance(parent, dict) or not isinstance(parent.get("sid"), str)
                or not re.fullmatch(CATEGORY, parent["sid"]) or not isinstance(parent.get("name"), str)):
            raise ValueError("Malformed Tatar Galyame category ancestry.")
    for row in data["list"]:
        if not isinstance(row, dict) or not isinstance(row.get("document"), dict):
            raise ValueError("Malformed Tatar Galyame resource/category row.")
    return data


def parse_listing(raw, request, root):
    kind, parts = route(request.url)
    if kind != "category":
        raise ValueError("Expected a Tatar Galyame category request.")
    data = payload(raw, "struct")
    if [p["sid"] for p in data["parents"]] != list(parts):
        raise ValueError("Tatar Galyame category ancestry disagrees with its requested path.")
    records, following, contexts, seen = [], [], {}, set()
    for row in data["list"]:
        doc = row["document"]
        if doc.get("name") == "DUMMY___":
            continue  # The public UI marks this category as not yet available.
        sid, title = doc.get("sid"), doc.get("name")
        if not isinstance(sid, str) or not isinstance(title, str) or not title.strip() or sid in seen:
            raise ValueError("Tatar Galyame listing has a malformed or repeated identity.")
        seen.add(sid)
        if "nice" not in doc:
            if not re.fullmatch(CATEGORY, sid) or sid in parts or len(parts) >= 12:
                raise ValueError("Invalid or cyclic Tatar Galyame subcategory.")
            following.append(PageRequest(category_url([*parts, sid])))
        else:
            if not isinstance(doc["nice"], str):
                raise ValueError("Invalid Tatar Galyame resource identity/type.")
            if doc["nice"] in HIDDEN_TYPES:
                continue  # Match the public catalog's own visibility rule.
            if not re.fullmatch(UUID, sid):
                raise ValueError("Invalid Tatar Galyame resource identity/type.")
            url = f"{ORIGIN}/api/sid/{sid}?lang=tt"
            records.append(url)
            contexts[url] = {"category_url": ARCHIVE_URL + ("/" + "/".join(parts) if parts else ""),
                             "category_api_url": request.url, "parents_raw": data["parents"],
                             "listing_document_raw": doc}
    if not parts and not (records or following):
        raise ValueError("Tatar Galyame returned no visible root categories or resources.")
    return ListingPage(records, following, fingerprint=json.dumps({"path": parts, "rows": data["list"]}, sort_keys=True),
                       detect_repeats=True, record_context=contexts)


def strings(doc, key):
    values = doc.get(key, [])
    if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
        raise ValueError(f"Tatar Galyame {key} must be a list of strings.")
    return values


def record(raw, page_url):
    kind, sid = route(page_url)
    if kind != "resource":
        raise ValueError("Expected a Tatar Galyame resource API URL.")
    data = payload(raw, "sid")
    if len(data["list"]) != 1:
        raise ValueError("Tatar Galyame resource API must return one record.")
    doc = data["list"][0]["document"]
    if (doc.get("sid") != sid or not isinstance(doc.get("name"), str) or not doc["name"].strip()
            or not isinstance(doc.get("nice"), str)):
        raise ValueError("Tatar Galyame resource metadata is missing or mismatched.")
    timestamp = doc.get("timestamp")
    if timestamp is not None and (type(timestamp) is not int or timestamp < 0):
        raise ValueError("Invalid Tatar Galyame source modification timestamp.")
    files, references = strings(doc, "file"), strings(doc, "url")
    assets, inventory = {}, []

    def attachment(url, label, extension, code=None, reason=None):
        if doc["nice"] in HIDDEN_TYPES:
            code, reason = "source_hidden", "The public catalog no longer displays this resource."
        if extension not in DOCUMENT_FORMATS and code is None:
            code, reason = "unsupported_format", "Attachment is not a supported original document format."
        asset = {"url": url, "label": label, "extension": extension, "source_asset_key": url,
                 "kind": "hosted_document" if same_origin(url, ORIGIN) and not code else "reference",
                 "unsupported_code": code, "unsupported_reason": reason}
        if timestamp is not None:
            asset["source_version"] = str(timestamp)
        assets[url] = asset
        return code or "eligible"

    for name in files:
        if not name.strip():
            continue
        filename(name)
        url = f"{ORIGIN}/files/{sid}/{quote(name, safe='')}"
        extension = PurePosixPath(name).suffix.lower()
        decision = attachment(url, name, extension)
        inventory.append({"filename_raw": name, "url": url, "selection_reason": decision})
    reference_inventory = []
    for href in references:
        if not href.strip():
            continue
        url = requote_uri(canonical(href, ARCHIVE_URL))
        extension = PurePosixPath(unquote(urlsplit(url).path)).suffix.lower()
        decision = "reference_only"
        if extension in DOCUMENT_FORMATS and url not in assets:
            try:
                target = route(url)
                hosted = target[0] == "file"
            except ValueError:
                hosted = False
            if hosted:
                decision = attachment(url, target[2], extension)
            else:
                code = "external_origin" if not same_origin(url, ORIGIN) else "unsupported_route"
                decision = attachment(url, doc["name"], extension, code,
                                      "Only explicitly listed hosted /files/ documents are selected; retain this reference for follow-up.")
        elif url in assets:
            decision = assets[url]["unsupported_code"] or "eligible"
        reference_inventory.append({"url_raw": href, "url": url, "selection_reason": decision})
    metadata = {"url": f"{ARCHIVE_URL}/{sid}", "sid": sid, "title": " ".join(doc["name"].split()),
                "title_raw": doc["name"], "api_url": page_url, "document_raw": doc,
                "parents_raw": data["parents"], "catalog_locale": "tt", "language_selection": "unverified",
                "admission_reason": "Owner selected all hosted catalog documents; catalog locale and Tatar descriptions do not establish document language.",
                "files": inventory, "references": reference_inventory,
                "attachments": [{k: a[k] for k in ("url", "label", "unsupported_code")} for a in assets.values()]}
    return metadata, list(assets.values())


def record_key(metadata):
    return metadata["sid"]


def prepare_http(http, session_file):
    def validate_request(method, url, data):
        if method != "GET" or data:
            raise ValueError("Tatar Galyame ingestion permits read-only GET requests only.")
        route(url)

    def check_response(response, *args, **kwargs):
        try:
            current = route(response.url)
            if response.is_redirect and route(canonical(response.headers["Location"], response.url)) != current:
                raise ValueError("Redirect changed the source resource.")
        except (ValueError, KeyError):
            response.close()
            raise InvalidDocument("Tatar Galyame returned an unexpected route or login redirect.") from None
        return response

    def validate_acquisition(asset):
        if (asset.get("kind") != "hosted_document" or route(asset["url"])[0] != "file"
                or asset.get("extension") not in DOCUMENT_FORMATS):
            raise InvalidDocument("Only selected hosted Tatar Galyame documents can be acquired.")

    def validate_download(response, asset):
        expected = route(asset["url"])
        if any(route(hop.url) != expected for hop in [*response.history, response]):
            raise InvalidDocument("Tatar Galyame download response belongs to a different resource.")

    http.validate_request = validate_request
    http.validate_acquisition = validate_acquisition
    http.validate_download_response = validate_download
    http.session.hooks["response"].append(check_response)
