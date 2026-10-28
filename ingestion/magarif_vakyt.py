"""Publisher-linked original PDFs and ZIPs with derived textbook PDFs."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
from urllib.parse import parse_qs, urlencode, urlsplit

from bs4 import BeautifulSoup
import requests
from urllib3.exceptions import HTTPError as TransportError

from .network import BudgetStop, InvalidDocument
from .paging import ListingPage, PageRequest


ARCHIVE_URL = "https://magarif-vakyt.ru/online2"
API = "https://cloud-api.yandex.net/v1/disk/public/resources"
PARSER_VERSION = 2
CATALOGS = {ARCHIVE_URL: "Электронный формат",
            "https://magarif-vakyt.ru/reading": "Литература на татарском языке"}
TATAR_TITLE = re.compile(r"^(?:Әдәби\s+уку|Әдәби\s+ярдәмлек|Туган\s+телдәге\s+әдәбият|Татар\s+Теле|Татар\s+әдәбияты)\b", re.IGNORECASE)
UPSTREAM_FIELDS = ("name", "type", "size", "md5", "sha256", "resource_id", "created",
                   "modified", "mime_type", "media_type", "path", "public_url")


class DeliveryStream:
    """Keep transport errors from exposing temporary signed download locators."""

    def __init__(self, raw):
        self.raw = raw

    def read(self, *args, **kwargs):
        try:
            return self.raw.read(*args, **kwargs)
        except (requests.RequestException, TransportError):
            raise requests.ConnectionError("Yandex original stream interrupted; temporary delivery URL omitted.") from None

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def stream(self, *args, **kwargs):
        try:
            yield from self.raw.stream(*args, **kwargs)
        except (requests.RequestException, TransportError):
            raise requests.ConnectionError("Yandex original stream interrupted; temporary delivery URL omitted.") from None


def public_share(url):
    p = urlsplit(url)
    if (p.scheme != "https" or p.netloc not in {"disk.yandex.ru", "yadi.sk"}
            or p.query or p.fragment or not re.fullmatch(r"/[di]/[A-Za-z0-9_-]+/?", p.path)):
        raise ValueError("Expected a publisher-linked public Yandex Disk share.")
    return "https://disk.yandex.ru" + p.path.rstrip("/")


def metadata_url(share):
    return API + "?" + urlencode({"public_key": public_share(share)})


def share_from_request(url):
    p = urlsplit(url)
    query = parse_qs(p.query)
    if (p.scheme != "https" or p.netloc != "cloud-api.yandex.net"
            or p.path != "/v1/disk/public/resources" or set(query) != {"public_key"}
            or len(query["public_key"]) != 1):
        raise ValueError("Unexpected Yandex metadata request.")
    return public_share(query["public_key"][0])


def parse_listing(html, request, root):
    if request.url not in CATALOGS:
        raise ValueError("Unexpected publisher catalog route.")
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if CATALOGS[request.url] != title:
        raise ValueError("Мәгариф–Вакыт electronic-textbook catalog is missing.")
    records, contexts = [], {}
    for anchor in soup.select("a[href]"):
        label = " ".join(anchor.get_text(" ", strip=True).split())
        if not TATAR_TITLE.search(label):
            continue
        if urlsplit(anchor["href"]).netloc not in {"disk.yandex.ru", "yadi.sk"}:
            continue
        share = public_share(anchor["href"])
        url = metadata_url(share)
        if url not in contexts:
            records.append(url)
            contexts[url] = {"listing_url": request.url, "title_raw": label,
                             "public_share_url": share, "href_raw": anchor["href"]}
        elif contexts[url]["title_raw"] != label:
            raise ValueError("One publisher share has conflicting textbook titles.")
    if not records:
        raise ValueError("Publisher catalog exposes no recognizable Tatar textbook originals.")
    following = [PageRequest(url) for url in CATALOGS if url != root] if request.url == root else []
    return ListingPage(records, following, entries=len(records), record_context=contexts)


def parse_resource(raw):
    try:
        data = json.loads(raw)
    except ValueError:
        raise ValueError("Yandex returned invalid resource JSON.") from None
    if not isinstance(data, dict) or not isinstance(data.get("name"), str) or data.get("error"):
        raise ValueError("Yandex resource metadata is unavailable or malformed.")
    if data.get("type") == "file":
        if type(data.get("size")) is not int or data["size"] <= 0:
            raise ValueError("Yandex did not report a valid file size.")
        if not re.fullmatch(r"[a-f0-9]{32}", str(data.get("md5", ""))):
            raise ValueError("Yandex did not report a valid MD5 checksum.")
        if data.get("sha256") and not re.fullmatch(r"[a-f0-9]{64}", str(data["sha256"])):
            raise ValueError("Yandex reported an invalid SHA-256 checksum.")
    return {k: data[k] for k in UPSTREAM_FIELDS if k in data}


def version(data):
    return hashlib.sha256(json.dumps({k: data.get(k) for k in ("resource_id", "size", "md5", "sha256")},
                                     sort_keys=True).encode()).hexdigest()


def record(raw, request_url):
    share = share_from_request(request_url)
    upstream = parse_resource(raw)
    extension = PurePosixPath(upstream["name"]).suffix.lower()
    supported = upstream.get("type") == "file" and extension in {".zip", ".pdf"}
    package = extension == ".zip"
    asset = {"url": share, "source_asset_key": "package" if package else "original",
             "kind": "textbook_package" if package else "original_document",
             "label": upstream["name"], "extension": extension,
             "source_version": version(upstream), "upstream": upstream,
             "unsupported_code": None if supported else "unsupported_package",
             "unsupported_reason": None if supported else "Only standalone publisher-linked ZIPs and PDFs are supported."}
    metadata = {"url": share, "api_url": request_url, "title": upstream["name"],
                "title_raw": upstream["name"], "upstream": upstream,
                "publisher_catalog_url": ARCHIVE_URL, "language_selection": "source_context_unverified",
                "admission_reason": "Publisher-labelled Tatar language/literature/reading textbook; document language and edition completeness remain unverified.",
                "attachments": [{k: asset[k] for k in ("url", "label", "unsupported_code")}]}
    return metadata, [asset]


def resolve_record(http, metadata, assets):
    contexts = metadata.get("catalog_context", [])
    if not contexts or any(not TATAR_TITLE.search(c.get("title_raw", "")) for c in contexts):
        raise ValueError("Yandex package lacks its publisher textbook admission evidence.")
    metadata["title"] = metadata["title_raw"] = contexts[0]["title_raw"]
    metadata["publisher_catalog_urls"] = sorted({c["listing_url"] for c in contexts})
    for asset in assets:
        asset["label"] = metadata["title"]
    return metadata, assets


def record_key(metadata):
    return "yandex:" + urlsplit(metadata["url"]).path.split("/")[-1]


def delivery_url(url):
    p = urlsplit(url)
    host = p.hostname or ""
    if (p.scheme != "https" or p.username or p.password or p.port not in {None, 443}
            or not (host == "downloader.disk.yandex.ru" or host.endswith(".disk.yandex.net")
                    or host.endswith(".storage.yandex.net"))):
        raise InvalidDocument("Yandex returned an unexpected delivery origin.")


def check_file_budget(http, upstream):
    if upstream["size"] > http.settings.max_file_bytes:
        raise InvalidDocument("Source original exceeds max_file_bytes; no download was started.")
    if upstream["size"] > http.settings.max_download_bytes - http.budget.bytes:
        raise BudgetStop("download byte cap")


def prepare_http(http, session_file):
    def validate_request(method, url, data):
        if method != "GET" or data:
            raise ValueError("Publisher ingestion permits read-only GET requests only.")
        if url in CATALOGS or url.startswith(API + "?") or url.startswith(API + "/download?"):
            return
        delivery_url(url)

    def check_response(response, *args, **kwargs):
        for url in [response.url, *([response.headers.get("Location", "")] if response.is_redirect else [])]:
            if url in CATALOGS or url.startswith(API + "?") or url.startswith(API + "/download?"):
                continue
            try:
                delivery_url(url)
            except ValueError:
                response.close()
                raise InvalidDocument("Publisher/Yandex retrieval redirected outside supported origins.") from None
        return response

    def validate_acquisition(asset):
        expected_kind = {".zip": "textbook_package", ".pdf": "original_document"}.get(asset.get("extension"))
        if expected_kind is None or asset.get("kind") != expected_kind:
            raise InvalidDocument("Only selected publisher PDF or ZIP originals may be acquired.")
        check_file_budget(http, asset["upstream"])
        http.package_asset = asset

    original_get = http.get

    def get_package(url, headers=None):
        share = public_share(url)
        asset = http.package_asset
        if share != asset["url"]:
            raise InvalidDocument("Yandex package identity mismatch.")
        current = parse_resource(http.text(metadata_url(share)))
        if version(current) != asset["source_version"]:
            raise InvalidDocument("Yandex package changed; run discovery again before acquisition.")
        check_file_budget(http, current)
        raw = http.text(API + "/download?" + urlencode({"public_key": share}))
        try:
            route = json.loads(raw)
            href = route["href"]
            delivery_url(href)
            if route.get("method") != "GET":
                raise ValueError("Unexpected download method.")
        except (ValueError, KeyError, TypeError):
            raise InvalidDocument("Yandex did not provide a valid GET download route.") from None
        try:
            response = original_get(href, headers=headers)
        except requests.RequestException as error:
            status = error.response.status_code if error.response is not None else None
            if status is not None and status not in {408, 429, 500, 502, 503, 504}:
                raise InvalidDocument(f"Yandex original download failed (HTTP {status}).") from None
            raise requests.ConnectionError("Yandex original transfer failed; temporary delivery URL omitted.") from None
        # Never persist the signed delivery locator as provenance or diagnostics.
        response.url = share
        response.raw = DeliveryStream(response.raw)
        response.package_share = share
        return response

    def validate_download(response, asset):
        if getattr(response, "package_share", None) != asset["url"]:
            raise InvalidDocument("Download did not resolve the expected public Yandex share.")

    def validate_acquired(asset, result):
        expected = asset["upstream"]
        if (result["size"] != expected["size"] or result["md5"] != expected["md5"]
                or (expected.get("sha256") and result["sha256"] != expected["sha256"])):
            raise InvalidDocument("Downloaded original does not match Yandex size/checksums.")
        return {"source_md5_verified": True, "source_sha256_verified": bool(expected.get("sha256"))}

    http.validate_request = validate_request
    http.session.hooks["response"].append(check_response)
    http.validate_acquisition = validate_acquisition
    http.validate_download_response = validate_download
    http.validate_acquired_asset = validate_acquired
    http.get = get_package


def download(http, manifest, summary, log, recheck):
    from .core import acquire, valid_local
    from .discovery import READ_ERRORS
    from .textbook_package import RECIPE, assemble, validate_zip

    summary.update(download_unit="publication", pdf_assembled=0, pdf_reused=0)
    workspace = manifest.directory / ".tmp"
    workspace.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="run-", dir=workspace) as folder:
        for asset in manifest.data["assets"].values():
            http.budget.check()
            if not asset.get("current", True) or asset["status"] == "unsupported":
                continue
            record = manifest.data["records"][asset.get("record_key", asset["record_url"])]
            previous = asset["results"][-1] if asset["results"] else None
            ready = (asset["status"] == "downloaded" and bool(previous)
                     and asset.get("verified_source_version") == asset.get("source_version")
                     and valid_local(manifest.directory, previous))
            package = asset.get("kind") == "textbook_package"
            if not package and ready and not recheck:
                summary["skipped"] += 1
                continue
            if (package and not recheck and ready and record.get("package_pdf", {}).get("status") == "complete"
                    and record["package_pdf"].get("archive_sha256") == previous["sha256"]
                    and record["package_pdf"].get("source_observation_id") == record["observations"][-1]["id"]
                    and all(r.get("recipe") == RECIPE for r in record["package_pdf"].get("current_results", []))
                    and all(valid_local(manifest.directory, r, folder="derived") for r in record["package_pdf"].get("current_results", []))
                    and record["package_pdf"].get("current_results")):
                summary["skipped"] += 1
                summary["pdf_reused"] += len(record["package_pdf"]["current_results"])
                continue
            http.budget.start_item()
            try:
                if not ready or recheck:
                    acquire(http, manifest, asset, Path(folder), summary, extensions={".zip", ".pdf"},
                            validate_file=(lambda p: validate_zip(p, http.budget)) if package else None)
                else:
                    summary["skipped"] += 1
                if package:
                    assemble(http, manifest, record, asset, Path(folder), summary)
                log(f"Textbook original ready: {record['observations'][-1]['metadata']['title']}")
            except (*READ_ERRORS, RuntimeError) as error:
                if not asset["results"] or not valid_local(manifest.directory, asset["results"][-1]):
                    asset.update(status="failed", last_error=str(error))
                if package:
                    record.setdefault("package_pdf", {}).update(status="failed", last_error=str(error))
                summary["errors"].append({"url": asset["url"], "stage": "package" if package else "download", "error": str(error)})
                log(f"Textbook package failed: {asset['label']}: {error}")
            finally:
                manifest.save()
