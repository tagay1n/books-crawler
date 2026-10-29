"""Tataroved publication pages and public original document files."""

import json
from pathlib import PurePosixPath
import re
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from . import language_reviews
from .documents import DOCUMENT_EXTENSIONS
from .languages import language_selection
from .network import InvalidDocument
from .paging import ListingPage, PageRequest


ORIGIN = "https://tataroved.ru"
ARCHIVE_URL = ORIGIN + "/publication/"
HOSTS = {"tataroved.ru", "www.tataroved.ru"}
FORMATS = DOCUMENT_EXTENSIONS - {".html", ".htm"}
PARSER_VERSION = 1
UNIQUE_RECORDS = True
DESCRIPTORS = ("url", "label", "extension", "filename_raw", "source_url_raw", "context_raw",
               "source_asset_key", "source_unsupported_code", "source_unsupported_reason")


def native_url(raw, base=ARCHIVE_URL):
    parsed = urlsplit(urljoin(base, raw))
    if parsed.scheme not in {"http", "https"} or parsed.netloc not in HOSTS:
        raise ValueError("Tataroved URLs must remain on the two native domain aliases.")
    path = unquote(parsed.path)
    if (not path.startswith("/") or "\\" in path
            or any(part in {".", ".."} for part in path.split("/"))
            or any(ord(c) < 32 or ord(c) == 127 for c in path)):
        raise ValueError("Unsafe Tataroved resource path.")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if path.startswith("/publication/") and not PurePosixPath(path).suffix:
        if not re.fullmatch(r"/publication/(?:[A-Za-z0-9_-]+/)*", path):
            raise ValueError("Unexpected Tataroved publication path.")
        if set(query) - {"bso_rewrite_url", "url"}:
            raise ValueError("Unexpected Tataroved catalog query.")
        for values in query.values():
            for value in values:
                if unquote(unquote(value)) != path:
                    raise ValueError("Tataroved rewrite query changed the publication path.")
    elif parsed.query:
        raise ValueError("Tataroved original-file requests must not include query parameters.")
    return urlunsplit(("https", "tataroved.ru", quote(path, safe="/-._~"), "", ""))


def document_url(url):
    normalized = native_url(url)
    parsed = urlsplit(normalized)
    if PurePosixPath(parsed.path).suffix.lower() not in FORMATS:
        raise ValueError("Expected a supported Tataroved original document URL.")
    return normalized


def page_area(html):
    soup = BeautifulSoup(html, "html.parser")
    areas = soup.select("#sso_page_content")
    if len(areas) != 1:
        raise ValueError("Tataroved native publication content is missing or ambiguous.")
    content = areas[0]
    main = content.find_parent("td")
    heading = main.select_one('p[align="right"] span.lnb') if main else None
    if heading is None or not heading.get_text(strip=True):
        raise ValueError("Tataroved publication heading is missing.")
    return soup, main, content, heading


def catalog(html):
    soup, main, content, heading = page_area(html)
    if heading.get_text(" ", strip=True) != "Публикации":
        raise ValueError("Expected the Tataroved publication catalog.")
    entries = {}
    for anchor in main.select("a.sbb[href]"):
        target = native_url(anchor["href"])
        if target == ARCHIVE_URL or not urlsplit(target).path.startswith("/publication/"):
            continue
        label = anchor.get_text(" ", strip=True)
        if not label:
            raise ValueError("Tataroved catalog entry has no title.")
        subtitle = anchor.find_next_sibling("i", class_="snb")
        entries[target] = {"catalog_title_raw": label,
                           "catalog_description_raw": subtitle.get_text(" ", strip=True) if subtitle else "",
                           "catalog_url": ARCHIVE_URL}
    if not entries:
        raise ValueError("Tataroved catalog contains no publication links.")
    return entries


def parse_listing(html, request, root):
    if native_url(request.url) != ARCHIVE_URL:
        raise ValueError("Unexpected Tataroved catalog listing URL.")
    entries = catalog(html)
    records = list(entries)
    # This count comes from the complete visible native link tree, not a separately
    # advertised total of books. Categories and HTML chapters are catalog records too.
    if request.context.get("verify"):
        return ListingPage(records, [], advertised=len(records), validation=True)
    return ListingPage(records, [], entries=len(records), advertised=len(records),
                       fingerprint=json.dumps(records), detect_repeats=True, record_context=entries)


def verification_request(root, count):
    return PageRequest(ARCHIVE_URL, context={"verify": True, "count": count})


def source_language(subtitle):
    """Use explicit bibliographic language claims, never topic or interface text."""
    evidence = []
    names = {"татарском": "tt", "русском": "ru", "английском": "en", "крымскотатарском": "crh"}
    word = "(?:" + "|".join(names) + ")"
    pattern = (r"(?:^|[.;(]\s*)(?P<claim>(?:на|текст на)\s+(?P<names>" + word
               + r"(?:\s*(?:,|и)\s*" + word + r")*)\s+язык(?:е|ах))\s*(?=$|[).;])")
    for match in re.finditer(pattern, subtitle, re.IGNORECASE):
        for name in re.findall(word, match["names"].casefold()):
            evidence.append({"language": names[name], "claim_raw": match["claim"], "field": "publication_subtitle"})
    for match in re.finditer(r"(?:^|[.;(]\s*)(татар телендә)\s*(?=$|[).;])", subtitle, re.IGNORECASE):
        evidence.append({"language": "tt", "claim_raw": match[1], "field": "publication_subtitle"})
    return list(dict.fromkeys(e["language"] for e in evidence)), evidence


def record(html, page_url):
    url = native_url(page_url)
    if url == ARCHIVE_URL or not urlsplit(url).path.startswith("/publication/"):
        raise ValueError("Expected a Tataroved publication record.")
    soup, main, content, heading = page_area(html)
    title = heading.get_text(" ", strip=True)
    subtitle_node = heading.parent.select_one("span.snb")
    subtitle = subtitle_node.get_text(" ", strip=True) if subtitle_node else ""
    languages, evidence = source_language(subtitle)
    selection = language_selection(languages)
    assets, inventory, html_links = {}, [], []
    for anchor in content.select("a[href]"):
        raw = urljoin(url, anchor["href"])
        parsed = urlsplit(raw)
        extension = PurePosixPath(unquote(parsed.path)).suffix.lower()
        label = anchor.get_text(" ", strip=True)
        image = anchor.select_one("img[alt]")
        if not label and image:
            label = image["alt"]
        if extension in {".html", ".htm"} or (parsed.path.startswith("/publication/") and parsed.path.endswith("/")):
            html_links.append({"url": raw, "label": label})
            continue
        if extension not in DOCUMENT_EXTENSIONS | {".zip", ".rar", ".7z"}:
            continue
        code, reason = None, None
        try:
            target = native_url(raw, url)
        except ValueError:
            target = raw
            code = "external_origin" if parsed.netloc not in HOSTS else "unsupported_url"
            reason = "Attachment is outside the native source or has an unsupported resource URL."
        if code is None and extension not in FORMATS:
            code, reason = "unsupported_format", "Archive expansion is deferred; only directly linked document originals are acquired."
        if code is None and selection != "selected":
            code = "language_excluded" if selection == "excluded" else "language_unknown"
            reason = ("Bibliographic language metadata does not identify Tatar content." if selection == "excluded"
                      else "No explicit Tatar language claim; an individual file review is required.")
        paragraph = anchor.find_parent("p")
        context = paragraph.get_text(" ", strip=True) if paragraph else label
        filename = PurePosixPath(unquote(parsed.path)).name
        descriptor = {"url": target, "label": label or filename, "extension": extension,
                      "filename_raw": filename, "source_url_raw": raw, "context_raw": context,
                      "source_asset_key": "original:" + target,
                      "source_unsupported_code": code, "source_unsupported_reason": reason,
                      "unsupported_code": code, "unsupported_reason": reason}
        assets.setdefault(target, descriptor)
        inventory.append({"url_raw": raw, "url": target, "label": label, "extension": extension,
                          "context_raw": context, "selection_reason": code or "eligible"})
    metadata = {"url": url, "publication_path": urlsplit(url).path, "title": title, "title_raw": title,
                "subtitle_raw": subtitle, "language_raw": languages, "language_evidence": evidence,
                "language_selection": selection, "description_raw": content.get_text(" ", strip=True),
                "files": inventory, "html_links": html_links,
                "representation": "linked_files" if assets else "html_or_catalog_metadata",
                "admission_reason": "Native publication entry; acquisition requires an explicit bibliographic Tatar language claim or a hash-pinned individual file review."}
    return metadata, list(assets.values())


def record_key(metadata):
    return metadata["publication_path"]


resolve_record = language_reviews.resolve


def prepare_http(http, session_file):
    http.language_reviews = language_reviews.load(
        http.settings.artifacts_root / "tataroved" / "language-reviews.json", document_url, "Tataroved")
    http.session.headers.update({"Accept-Language": "ru,en;q=0.5"})
    def route(url):
        normalized = native_url(url)
        if urlsplit(normalized).path.startswith("/publication/") and urlsplit(normalized).path.endswith("/"):
            # The native CMS redirects these public pages to equivalent HTTP
            # routes with rewrite parameters. No authenticated sessions are used.
            return ("page", normalized)
        return ("file", document_url(url))
    def validate_request(method, url, data):
        if method != "GET" or data:
            raise ValueError("Tataroved acquisition permits read-only GET requests only.")
        route(url)
    def check_response(response, *args, **kwargs):
        try:
            identity = route(response.url)
            if response.is_redirect and route(urljoin(response.url, response.headers["Location"])) != identity:
                raise ValueError("Tataroved redirect changed the source resource.")
        except (ValueError, KeyError):
            response.close()
            raise InvalidDocument("Tataroved returned an unexpected redirect or resource route.") from None
        return response
    def validate_download(response, asset):
        expected = document_url(asset["url"])
        if any(document_url(hop.url) != expected for hop in [*response.history, response]):
            raise InvalidDocument("Tataroved download belongs to another original file.")
    http.validate_request = validate_request
    http.session.hooks["response"].append(check_response)
    http.validate_download_response = validate_download
    http.validate_acquisition = lambda asset: language_reviews.validate_acquisition(http, asset)
    http.validate_acquired_asset = language_reviews.validate_acquired


def download(http, manifest, summary, log, recheck):
    from .core import download as download_originals
    language_reviews.refresh(http, manifest, PARSER_VERSION, DESCRIPTORS)
    download_originals(http, manifest, summary, log, recheck, extensions=FORMATS)
