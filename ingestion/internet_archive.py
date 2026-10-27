"""Tatar-labelled Internet Archive text items and their original uploads."""

import hashlib
import json
from pathlib import PurePosixPath
import re
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlsplit

from .documents import DOCUMENT_EXTENSIONS
from .network import BudgetStop, InvalidDocument
from .paging import CatalogChanged, ListingPage, PageRequest


ARCHIVE_URL = "https://archive.org"
SEARCH_URL = ARCHIVE_URL + "/advancedsearch.php"
QUERY = "mediatype:texts AND (language:tat OR language:tt OR language:tatar)"
BATCH_SIZE = 100
PARSER_VERSION = 1
UNIQUE_RECORDS = True
FORMATS = DOCUMENT_EXTENSIONS - {".html", ".htm"}
TATAR_LABELS = {"tat", "tt", "tatar"}


def identifier(value):
    if (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", value)
            or value in {".", ".."}):
        raise ValueError("Archive returned an invalid item identifier.")
    return value


def filename(value):
    if (not isinstance(value, str) or not value or "\\" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError("Archive returned an unsafe native filename.")
    return value


def metadata_url(item_id):
    return f"{ARCHIVE_URL}/metadata/{identifier(item_id)}"


def file_url(item_id, name):
    return f"{ARCHIVE_URL}/download/{identifier(item_id)}/{quote(filename(name), safe='/')}"


def listing_request(page=1, advertised=None, *, validation=False):
    params = {"q": QUERY, "output": "json", "rows": BATCH_SIZE, "page": page,
              "sort[]": "identifier asc", "fl[]": "identifier"}
    context = {"advertised": advertised} if advertised is not None else {}
    if validation:
        context["validation"] = True
    return PageRequest(SEARCH_URL + "?" + urlencode(params), context=context)


def initial_request(root):
    if root.rstrip("/") != ARCHIVE_URL:
        raise ValueError("Unexpected Archive source root.")
    return listing_request()


def verification_request(root, advertised):
    return listing_request(advertised=advertised, validation=True)


def search_page(url):
    parsed = urlsplit(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    expected = {"q": [QUERY], "output": ["json"], "rows": [str(BATCH_SIZE)],
                "sort[]": ["identifier asc"], "fl[]": ["identifier"]}
    pages = params.pop("page", [])
    if (parsed.scheme != "https" or parsed.netloc != "archive.org"
            or parsed.path != "/advancedsearch.php" or parsed.fragment or params != expected
            or len(pages) != 1 or not pages[0].isdecimal() or int(pages[0]) < 1):
        raise ValueError("Invalid bounded Archive search request.")
    return int(pages[0])


def payload(text):
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError("Archive did not return valid metadata JSON.") from None
    if not isinstance(data, dict) or not data or data.get("error") or data.get("errors"):
        raise ValueError("Archive metadata is unavailable or reports an API error; work remains unresolved.")
    return data


def parse_listing(text, request, root):
    page = search_page(request.url)
    data = payload(text)
    result = data.get("response")
    if not isinstance(result, dict):
        raise ValueError("Archive search response is missing its result object.")
    total, start, docs = result.get("numFound"), result.get("start"), result.get("docs")
    if (type(total) is not int or total < 0 or type(start) is not int
            or start != (page - 1) * BATCH_SIZE or not isinstance(docs, list)):
        raise ValueError("Archive search offset, total, or batch size is inconsistent.")
    if "advertised" in request.context and total != request.context["advertised"]:
        raise CatalogChanged("Archive search total changed; next discovery starts a fresh scan.")
    if len(docs) != min(BATCH_SIZE, max(0, total - start)) or (start >= total and page != 1):
        raise ValueError("Archive search returned an incomplete or out-of-range batch.")
    ids = []
    for doc in docs:
        if not isinstance(doc, dict):
            raise ValueError("Archive search returned a malformed item.")
        ids.append(identifier(doc.get("identifier")))
    if len(set(ids)) != len(ids):
        raise CatalogChanged("Archive search repeated an item within a batch.")
    following = [listing_request(page + 1, total)] if start + len(docs) < total else []
    return ListingPage([metadata_url(item) for item in ids], following,
                       entries=len(ids), advertised=total,
                       validation=bool(request.context.get("validation")),
                       fingerprint=json.dumps(ids), detect_repeats=bool(ids))


def language_selection(raw):
    values = [raw] if isinstance(raw, str) else raw
    if values is None or values == [] or values == "":
        return "review"
    if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
        return "review"
    labels = {v.strip().casefold() for v in values if v.strip()}
    if labels & TATAR_LABELS:
        return "selected"
    return "excluded" if labels else "review"


def flagged(value):
    return value is True or str(value).strip().casefold() in {"1", "true", "yes"}


def source_hints(file):
    size = file.get("size")
    if size is not None:
        if isinstance(size, str) and size.isdecimal():
            size = int(size)
        if type(size) is not int or size <= 0:
            raise ValueError("Archive original has malformed size metadata.")
    md5 = file.get("md5")
    if md5 is not None:
        if not isinstance(md5, str) or not re.fullmatch(r"[a-fA-F0-9]{32}", md5):
            raise ValueError("Archive original has malformed MD5 metadata.")
        md5 = md5.lower()
    mtime = file.get("mtime")
    if mtime is not None and type(mtime) not in {str, int, float}:
        raise ValueError("Archive original has malformed modification metadata.")
    version = hashlib.sha256(json.dumps([md5, size, mtime], allow_nan=False).encode()).hexdigest()
    return {"reported_size": size, "source_md5": md5, "source_mtime": mtime, "source_version": version}


def record(text, page_url):
    parsed = urlsplit(page_url)
    if parsed.scheme != "https" or parsed.netloc != "archive.org" or parsed.query or parsed.fragment:
        raise ValueError("Invalid Archive metadata URL.")
    match = re.fullmatch(r"/metadata/([^/]+)", parsed.path)
    item_id = identifier(match[1] if match else None)
    data = payload(text)
    upstream, files = data.get("metadata"), data.get("files")
    if (not isinstance(upstream, dict) or upstream.get("identifier") != item_id
            or not isinstance(files, list) or any(not isinstance(f, dict) for f in files)):
        raise ValueError("Archive item metadata or file inventory is missing or mismatched.")
    language = language_selection(upstream.get("language"))
    restricted = any(flagged(value) for value in (
        data.get("is_dark"), data.get("is_restricted"), upstream.get("access-restricted-item")))
    assets, decisions, seen = [], [], set()
    for file in files:
        name = file.get("name")
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("Archive file inventory has missing or repeated filenames.")
        seen.add(name)
        suffix = PurePosixPath(name).suffix.lower()
        code = None
        try:
            filename(name)
        except ValueError:
            code = "unsafe_filename"
        if code is None:
            if file.get("source") != "original":
                code = "derivative" if file.get("source") == "derivative" else "origin_unknown"
            elif suffix not in FORMATS or str(file.get("format", "")).casefold() == "metadata":
                code = "unsupported_format"
            elif flagged(file.get("private")):
                code = "private"
            elif restricted:
                code = "restricted"
            elif upstream.get("mediatype") != "texts":
                code = "mediatype_excluded"
            elif language != "selected":
                code = "language_unknown" if language == "review" else "language_excluded"
        decisions.append({"name": name, "reason": code or "eligible"})
        if code in {"unsafe_filename", "derivative", "origin_unknown", "unsupported_format"}:
            continue
        # Public, original document candidates remain inspectable even when held.
        hints = source_hints(file) if code is None else {}
        assets.append({"url": file_url(item_id, name), "source_asset_key": name,
                       "archive_identifier": item_id, "archive_filename": name,
                       "label": name, "extension": suffix, **hints,
                       "unsupported_code": code,
                       "unsupported_reason": f"Archive original held: {code}." if code else None})
    raw_title = upstream.get("title")
    title = raw_title if isinstance(raw_title, str) and raw_title else item_id
    metadata = {"url": f"{ARCHIVE_URL}/details/{item_id}", "identifier": item_id,
                "title": title, "title_raw": raw_title, "upstream": upstream, "files": files,
                "file_decisions": decisions, "language_selection": language,
                "admission_reason": (
                    "Explicit Archive Tatar language metadata; content language and completeness unverified."
                    if language == "selected" and upstream.get("mediatype") == "texts"
                    else "Held: current Archive language/media-type metadata does not establish eligibility."),
                "attachments": [{"url": a["url"], "label": a["label"]} for a in assets]}
    return metadata, assets


def record_key(metadata):
    return metadata["identifier"]


def download_identity(url):
    """Validate a canonical file URL or an Archive storage-server redirect."""
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.netloc != host or parsed.query or parsed.fragment
            or not (host == "archive.org" or host.endswith(".archive.org"))):
        raise InvalidDocument("Archive download left its allowed HTTPS hosts.")
    path = unquote(parsed.path)
    pattern = r"/download/([^/]+)/(.+)" if host == "archive.org" else r"/\d+/items/([^/]+)/(.+)"
    match = re.fullmatch(pattern, path)
    if not match:
        raise InvalidDocument("Archive download left its expected file route.")
    return identifier(match[1]), filename(match[2])


def prepare_http(http, session_file):
    def validate_request(method, url, data):
        if method != "GET" or data:
            raise ValueError("Archive ingestion permits only read-only GET requests.")
        parsed = urlsplit(url)
        if parsed.scheme == "https" and parsed.netloc == "archive.org":
            if parsed.path == "/advancedsearch.php":
                search_page(url)
                return
            match = re.fullmatch(r"/metadata/([^/]+)", parsed.path)
            if match and not parsed.query and not parsed.fragment:
                identifier(match[1])
                return
        download_identity(url)

    def check_response(response, *args, **kwargs):
        try:
            validate_request("GET", response.url, None)
            if response.is_redirect:
                current = download_identity(response.url)
                target = download_identity(urljoin(response.url, response.headers["Location"]))
                if current != target:
                    raise InvalidDocument("Archive redirect changed the item or filename.")
        except (ValueError, KeyError):
            response.close()
            raise InvalidDocument("Archive returned an unexpected response or redirect route.") from None
        return response

    def validate_response(response, asset):
        expected = (asset["archive_identifier"], asset["archive_filename"])
        for hop in [*response.history, response]:
            if download_identity(hop.url) != expected:
                raise InvalidDocument("Archive response belongs to a different item or filename.")
            if hop.is_redirect and download_identity(urljoin(hop.url, hop.headers["Location"])) != expected:
                raise InvalidDocument("Archive redirect belongs to a different file.")

    def validate_acquisition(asset):
        expected = (asset["archive_identifier"], asset["archive_filename"])
        if (urlsplit(asset["url"]).netloc != "archive.org" or download_identity(asset["url"]) != expected
                or asset.get("unsupported_reason")):
            raise InvalidDocument("Invalid or ineligible Archive acquisition descriptor.")
        size = asset.get("reported_size")
        if size is not None:
            if size > http.settings.max_file_bytes:
                raise InvalidDocument("Archive-reported file size exceeds max_file_bytes.")
            if size > http.settings.max_download_bytes - http.budget.bytes:
                raise BudgetStop("download byte cap")

    def validate_acquired(asset, actual):
        checks = []
        for supplied, measured in (("reported_size", "size"), ("source_md5", "md5")):
            expected = asset.get(supplied)
            if expected is not None:
                if expected != actual[measured]:
                    raise InvalidDocument(f"Archive source {measured} mismatch; refreshed discovery is required.")
                checks.append(measured)
        return {"source_integrity_checks": checks}

    http.validate_request = validate_request
    http.session.hooks["response"].append(check_response)
    http.validate_acquisition = validate_acquisition
    http.validate_download_response = validate_response
    http.validate_acquired_asset = validate_acquired
