"""Discover Commons books and acquire their checksum-verified original files."""

import hashlib
import json
from pathlib import PurePosixPath
import re
from urllib.parse import parse_qs, parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from .documents import DOCUMENT_EXTENSIONS, canonical
from .network import BudgetStop, InvalidDocument, SourceAccessError
from .paging import CatalogChanged, ListingPage, PageRequest


ARCHIVE_URL = "https://commons.wikimedia.org/wiki/Category:Tatar-language_books"
API_URL = "https://commons.wikimedia.org/w/api.php"
ROOT_CATEGORY_ID = 70354556
PARSER_VERSION = 3
SUPPORTED_COMMANDS = {"discover", "download", "run", "status"}
DOCUMENT_FORMATS = DOCUMENT_EXTENSIONS - {".html", ".htm"}
BATCH_SIZE = 10
USER_AGENT = "BooksCrawlerBot/1.0 (https://github.com/tagay1n/books-crawler; local Commons acquisition)"
MIMES = {
    ".pdf": {"application/pdf"}, ".djvu": {"image/vnd.djvu", "image/x-djvu", "application/x-djvu"},
    ".djv": {"image/vnd.djvu", "image/x-djvu", "application/x-djvu"},
    ".epub": {"application/epub+zip"}, ".txt": {"text/plain"},
    ".rtf": {"application/rtf", "text/rtf"}, ".doc": {"application/msword"},
    ".ppt": {"application/vnd.ms-powerpoint"}, ".xls": {"application/vnd.ms-excel"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".odt": {"application/vnd.oasis.opendocument.text"},
    ".odp": {"application/vnd.oasis.opendocument.presentation"},
    ".ods": {"application/vnd.oasis.opendocument.spreadsheet"},
}


def api_url(**parameters):
    return API_URL + "?" + urlencode({"action": "query", "format": "json", "formatversion": 2,
                                      "maxlag": 5, **parameters})


def positive_id(value):
    if type(value) is not int or value < 1:
        raise ValueError("Commons returned an invalid native page ID.")
    return value


def parameters(url):
    parsed = urlsplit(url)
    if (parsed.scheme, parsed.netloc, parsed.path) != ("https", "commons.wikimedia.org", "/w/api.php"):
        raise ValueError("Commons discovery requests must target its metadata API.")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if any(len(values) != 1 for values in query.values()) or query.get("action") != ["query"]:
        raise ValueError("Invalid read-only Commons API request.")
    return {key: values[0] for key, values in query.items()}


def original_identity(url):
    parsed = urlsplit(url)
    match = re.fullmatch(r"/wikipedia/commons/([0-9a-f])/([0-9a-f]{2})/([^/]+)", parsed.path)
    if (parsed.scheme != "https" or parsed.netloc != "upload.wikimedia.org"
            or parsed.query or parsed.fragment or match is None or match[1] != match[2][0]):
        raise InvalidDocument("Commons downloads must use an original upload.wikimedia.org file URL.")
    name = unquote(match[3])
    if (name in {".", ".."} or any(c in name for c in "/\\")
            or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or extension(name) not in DOCUMENT_FORMATS):
        raise InvalidDocument("Commons original URL has an unsafe or unsupported filename.")
    return match[1], match[2], name


def source_hints(asset):
    size, sha1 = asset.get("reported_size"), asset.get("source_sha1")
    if type(size) is not int or size <= 0 or not isinstance(sha1, str) or not re.fullmatch(r"[0-9a-f]{40}", sha1):
        raise InvalidDocument("Commons original requires a valid reported size and hexadecimal SHA-1; refresh discovery.")
    return {"size": size, "sha1": sha1}


def source_version(asset):
    hints = source_hints(asset)
    return f"{hints['sha1']}:{hints['size']}"


def prepare_http(http, session_file):
    http.session.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})

    def route(url):
        if urlsplit(url).netloc == "upload.wikimedia.org":
            return ("file", *original_identity(url))
        return "api", tuple(sorted(parameters(url).items()))

    def validate_request(method, url, data):
        if method != "GET" or data:
            raise ValueError("Commons ingestion permits read-only GET requests only.")
        route(url)

    http.validate_request = validate_request

    def check_response(response, *args, **kwargs):
        try:
            current = route(response.url)
            if response.is_redirect and route(canonical(response.headers["Location"], response.url)) != current:
                raise ValueError("Commons redirect changed the requested resource.")
        except (ValueError, KeyError):
            response.close()
            raise SourceAccessError("Commons redirected outside its metadata endpoint or requested original upload.") from None
        return response

    http.session.hooks["response"].append(check_response)

    def validate_acquisition(asset):
        name = original_identity(asset["url"])[2]
        if (asset.get("unsupported_reason") or asset.get("extension") != extension(name)
                or asset.get("mime") not in MIMES.get(asset.get("extension"), set())):
            raise InvalidDocument("Invalid or ineligible Commons original-file descriptor.")
        hints = source_hints(asset)
        if hints["size"] > http.settings.max_file_bytes:
            raise InvalidDocument("Commons-reported original size exceeds max_file_bytes.")
        if hints["size"] > http.settings.max_download_bytes - http.budget.bytes:
            raise BudgetStop("download byte cap")

    def validate_response(response, asset):
        expected = original_identity(asset["url"])
        if any(original_identity(hop.url) != expected for hop in [*response.history, response]):
            raise InvalidDocument("Commons download response belongs to a different original file.")
        if response.status_code == 200:
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if mime not in MIMES[asset["extension"]]:
                raise InvalidDocument("Commons download MIME disagrees with its document format.")

    def validate_acquired(asset, actual):
        if any(actual.get(key) != expected for key, expected in source_hints(asset).items()):
            raise InvalidDocument("Commons original size or SHA-1 mismatch; refresh discovery before retrying.")
        return {"source_integrity_checks": ["size", "sha1"]}

    http.validate_acquisition = validate_acquisition
    http.validate_download_response = validate_response
    http.validate_acquired_asset = validate_acquired


def download(http, manifest, summary, log, recheck):
    from .core import download as download_originals

    # Version hints also work for manifests produced by the discovery-only adapter.
    for asset in manifest.data["assets"].values():
        if asset.get("current", True) and asset["status"] != "unsupported":
            try:
                asset["source_version"] = source_version(asset)
            except InvalidDocument:
                pass  # The shared per-asset acquisition path reports invalid hints.
    manifest.save()

    def inspect_file(path):
        digest = hashlib.sha1()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                http.budget.check()
                digest.update(chunk)
        return {"sha1": digest.hexdigest()}

    download_originals(http, manifest, summary, log, recheck,
                       extensions=DOCUMENT_FORMATS, validate_file=inspect_file)


def category_request(category_id, continuation=None, seen=()):
    positive_id(category_id)
    params = {"list": "categorymembers", "cmpageid": category_id, "cmtype": "file|subcat",
              "cmprop": "ids|title|type", "cmlimit": BATCH_SIZE,
              "prop": "info|categoryinfo", "pageids": category_id}
    if continuation:
        params.update(continuation)
    context = {"validated_category_id": category_id, "seen_continuations": list(seen)} if continuation else {}
    return PageRequest(api_url(**params), context=context)


def initial_request(root):
    if root.rstrip("/") != ARCHIVE_URL:
        raise ValueError("Unexpected Commons seed category.")
    return category_request(ROOT_CATEGORY_ID)


def file_request(page_id):
    return api_url(pageids=positive_id(page_id), prop="imageinfo", iilimit=1,
                   iiprop="canonicaltitle|timestamp|url|size|mime|sha1|extmetadata",
                   iiextmetadatalanguage="en", iiextmetadatamultilang=1)


def payload(text):
    try:
        value = json.loads(text)
    except ValueError:
        raise ValueError("Commons metadata API did not return valid JSON.") from None
    if not isinstance(value, dict):
        raise ValueError("Commons API response must be an object.")
    if "error" in value or "errors" in value:
        error = value.get("error", {})
        code = error.get("code", "unknown") if isinstance(error, dict) else "unknown"
        if code in {"badcontinue", "invalidcontinue"}:
            raise CatalogChanged("Commons continuation expired; the next invocation starts a fresh scan.")
        raise ValueError(f"Commons API error: {code}; work remains retryable.")
    if not isinstance(value.get("query"), dict):
        raise ValueError("Commons API response is missing its query result.")
    return value


def single_page(data, page_id):
    pages = data["query"].get("pages")
    if (not isinstance(pages, list) or len(pages) != 1 or not isinstance(pages[0], dict)
            or pages[0].get("pageid") != page_id):
        raise ValueError("Commons API response does not match the requested native page ID.")
    return pages[0]


def extension(title):
    return PurePosixPath(title).suffix.lower()


def parse_listing(text, request, root):
    query = parameters(request.url)
    if query.get("list") != "categorymembers":
        raise ValueError("Expected a Commons category-members request.")
    try:
        category_id = positive_id(int(query["cmpageid"]))
    except (KeyError, ValueError):
        raise ValueError("Commons category request has no valid native ID.") from None
    data = payload(text)
    if "pages" in data["query"]:
        category = single_page(data, category_id)
        if category.get("missing") or category.get("ns") != 14:
            raise ValueError("Commons category is missing or is not a category page.")
    elif not query.get("cmcontinue") or request.context.get("validated_category_id") != category_id:
        raise ValueError("Commons category has not been validated before continuation.")
    members = data["query"].get("categorymembers")
    if not isinstance(members, list):
        raise ValueError("Commons category response is missing its member list.")
    following, records, contexts, ids = [], [], {}, []
    for member in members:
        if not isinstance(member, dict) or not isinstance(member.get("title"), str):
            raise ValueError("Malformed Commons category member.")
        page_id = positive_id(member.get("pageid"))
        ids.append(page_id)
        if member.get("ns") == 14:
            following.append(category_request(page_id))
        elif member.get("ns") == 6:
            if extension(member["title"]) not in DOCUMENT_FORMATS:
                continue  # Do not retain image IDs, titles, or metadata records.
            url = file_request(page_id)
            if url not in contexts:
                records.append(url)
                # Stable seed context avoids observation churn when the same file
                # is encountered via multiple categories or different cursors.
                contexts[url] = {"seed_category_id": ROOT_CATEGORY_ID, "listing_url": ARCHIVE_URL,
                                 "label_raw": member["title"]}
        else:
            raise ValueError("Unexpected namespace in the Commons category-member response.")
    if "continue" in data:
        cursor = data["continue"]
        if (not isinstance(cursor, dict) or not cursor.get("cmcontinue")
                or set(cursor) - {"cmcontinue", "continue"}
                or any(not isinstance(value, str) for value in cursor.values())):
            raise ValueError("Malformed Commons category continuation.")
        marker = json.dumps(cursor, sort_keys=True)
        current = {key: query[key] for key in ("continue", "cmcontinue") if key in query}
        previous = request.context.get("seen_continuations", [])
        if marker == json.dumps(current, sort_keys=True) or marker in previous:
            raise CatalogChanged("Commons continuation repeated or cycled; restart discovery.")
        seen = previous + ([json.dumps(current, sort_keys=True)] if current else [])
        following.insert(0, category_request(category_id, cursor, seen))
    return ListingPage(records, following, entries=len(records), record_context=contexts,
                       fingerprint=json.dumps([category_id, ids]), detect_repeats=bool(members))


def clean_url(url):
    if not isinstance(url, str):
        raise ValueError("Commons returned an invalid file URL.")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Commons file URL is not a public HTTPS locator.")
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if not key.lower().startswith("utm_")]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))


def record(text, request_url):
    query = parameters(request_url)
    try:
        page_id = positive_id(int(query["pageids"]))
    except (KeyError, ValueError):
        raise ValueError("Commons file request has no valid native ID.") from None
    data = payload(text)
    page = single_page(data, page_id)
    metadata = {"url": f"https://commons.wikimedia.org/w/index.php?curid={page_id}",
                "page_id": page_id, "seed_category_id": ROOT_CATEGORY_ID,
                "admission_reason": "Document-format file enumerated in Tatar-language books or a subcategory; language and completeness unverified."}
    if isinstance(page.get("title"), str) and page["title"]:
        metadata.update(title=page["title"].removeprefix("File:"), title_raw=page["title"])
    if page.get("missing"):
        metadata.update(availability="missing", upstream=page, attachments=[])
        return metadata, []
    if page.get("ns") != 6:
        raise ValueError("Commons file metadata is not from the File namespace.")
    information = page.get("imageinfo", [])
    if not isinstance(information, list) or len(information) > 1:
        raise ValueError("Expected only the current Commons file version.")
    if not information or (isinstance(information[0], dict) and "filehidden" in information[0]):
        metadata.update(availability="unavailable", upstream=page, attachments=[])
        return metadata, []
    info = information[0]
    if not isinstance(info, dict):
        raise ValueError("Malformed Commons original-file metadata.")
    suffix = extension(page.get("title", ""))
    if suffix not in DOCUMENT_FORMATS or info.get("mime") not in MIMES[suffix]:
        raise ValueError("Commons file format does not agree with its document filename.")
    if type(info.get("size")) is not int or info["size"] <= 0:
        raise ValueError("Commons did not report a valid original-file size.")
    for key in ("url", "descriptionurl", "descriptionshorturl"):
        if key in info:
            info[key] = clean_url(info[key])
    url = clean_url(info.get("url"))
    if extension(original_identity(url)[2]) != suffix:
        raise ValueError("Commons original URL does not agree with its document format.")
    asset = {"url": url, "label": metadata["title"], "source_asset_key": "original",
             "extension": suffix, "mime": info["mime"], "reported_size": info["size"],
             "unsupported_reason": None, "unsupported_code": None}
    for field, source in (("source_sha1", "sha1"), ("source_uploaded_at", "timestamp"),
                          ("source_page_count", "pagecount")):
        if source in info:
            asset[field] = info[source]
    asset["source_version"] = source_version(asset)
    metadata.update(availability="available", upstream=page,
                    attachments=[{key: value for key, value in asset.items() if key not in {"unsupported_reason"}}])
    return metadata, [asset]


def resolve_record(http, metadata, assets):
    if not metadata.get("title"):
        contexts = metadata.get("catalog_context", [])
        title = next((item["label_raw"] for item in contexts if item.get("label_raw")), None)
        if not title:
            raise ValueError("Missing Commons file has no retained catalog title.")
        metadata.update(title=title.removeprefix("File:"), title_raw=title)
    return metadata, assets


def record_key(metadata):
    return "file:" + str(metadata["page_id"])
