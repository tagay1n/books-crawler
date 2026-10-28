"""Public publisher-labelled Tatar PDF editions, excluding images and packages."""

from email.message import Message
from pathlib import PurePosixPath
import re
from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup
from requests.utils import requote_uri

from .documents import canonical, same_origin
from .network import InvalidDocument
from .paging import ListingPage, PageRequest


ARCHIVE_URL = "https://sarhaan.com/a/tatar-%d8%aa%d8%aa%d8%a7%d8%b1%d9%8a/"
PARSER_VERSION = 2
TATAR_LABEL = "Tatar - تتاري татар теле"


def category_page(url):
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    base = unquote(urlsplit(ARCHIVE_URL).path)
    match = re.fullmatch(re.escape(base) + r"page/([1-9]\d*)/", path)
    if path != base and match is None:
        return None
    value = parse_qs(parsed.query).get("paged", [match[1] if match else "1"])[0]
    if not value.isdigit() or int(value) < 1 or (match and int(value) != int(match[1])):
        raise ValueError("Invalid or conflicting category page number.")
    return int(value)


def native_url(href, base=ARCHIVE_URL):
    url = requote_uri(canonical(href, base))
    p = urlsplit(url)
    path = unquote(p.path)
    query = parse_qs(p.query, keep_blank_values=True)
    if (not same_origin(url, ARCHIVE_URL) or "\\" in path
            or {".", ".."}.intersection(path.split("/"))
            or any(len(v) != 1 for v in query.values())):
        raise ValueError("Sarhaan requires native HTTPS resource URLs.")
    if "wpdmdl" in query:
        if (not set(query) <= {"wpdmdl", "ind", "filename"}
                or not query["wpdmdl"][0].isdigit()
                or ("ind" in query and not query["ind"][0].isdigit())
                or not (path == "/" or re.fullmatch(r"/ab/[^/]+/", path))):
            raise ValueError("Unexpected native download identity.")
    elif category_page(url) is not None:
        if (not set(query) <= {"ir_search", "ir_sort", "ir_view", "paged"}
                or query.get("ir_search", [""]) != [""]
                or query.get("ir_sort", ["latest"]) != ["latest"]
                or query.get("ir_view", ["grid"]) != ["grid"]
                or not query.get("paged", ["1"])[0].isdigit()
                or int(query.get("paged", ["1"])[0]) < 1):
            raise ValueError("Unexpected Tatar category pagination.")
    elif not re.fullmatch(r"/ab/[^/]+/", path) or query:
        raise ValueError("Unexpected publisher book URL.")
    return url


def download_id(url):
    return parse_qs(urlsplit(native_url(url)).query).get("wpdmdl", [None])[0]


def resource_identity(url):
    parsed = urlsplit(native_url(url))
    if category_page(url) is not None:
        return "category", category_page(url)
    return unquote(parsed.path), parse_qs(parsed.query, keep_blank_values=True)


def prepare_http(http, session_file):
    def validate_request(method, url, data):
        if method != "GET" or data:
            raise ValueError("Sarhaan permits read-only GET retrieval only.")
        native_url(url)

    def check_response(response, *args, **kwargs):
        try:
            before = native_url(response.url)
            if response.is_redirect:
                after = native_url(response.headers["Location"], before)
                if (resource_identity(after) != resource_identity(before)
                        and (not download_id(before) or download_id(before) != download_id(after))):
                    raise ValueError("Redirect changed publisher identity.")
        except (ValueError, KeyError):
            response.close()
            raise InvalidDocument("Sarhaan redirected outside the selected native resource.") from None
        return response

    def validate_download(response, asset):
        identity = download_id(asset["url"])
        if not identity or any(download_id(r.url) != identity for r in [*response.history, response]):
            raise InvalidDocument("PDF delivery changed the selected package identity.")
        disposition = Message()
        disposition["Content-Disposition"] = response.headers.get("Content-Disposition", "")
        filename = disposition.get_filename()
        if filename and unquote(filename) != asset["filename_claim"]:
            raise InvalidDocument("Delivered filename differs from the individually selected PDF.")

    http.validate_request = validate_request
    http.session.hooks["response"].append(check_response)
    http.validate_download_response = validate_download


def parse_listing(html, request, root):
    url = native_url(request.url)
    if category_page(url) is None:
        raise ValueError("Expected the native Tatar category.")
    soup = BeautifulSoup(html, "html.parser")
    breadcrumb = soup.select_one(".irhp-language-breadcrumb")
    if breadcrumb is None or TATAR_LABEL not in breadcrumb.get_text(" ", strip=True):
        raise ValueError("Tatar category identification is missing.")
    entries = {}
    for card in soup.select("article.irhp-book-card"):
        heading = card.select_one("h2 a[href], h3 a[href]")
        if heading is None or not card.get("data-book-id", "").isdigit():
            raise ValueError("Book card identity or title is missing.")
        target = native_url(heading["href"], url)
        if urlsplit(target).query or not urlsplit(target).path.startswith("/ab/"):
            raise ValueError("Book card does not identify a detail page.")
        label = card.select_one(".irhp-book-card__badge--language")
        entries[target] = {"catalog_url": url, "book_id_claim": card["data-book-id"],
                           "title_raw": heading.get_text(" ", strip=True),
                           "language_raw": label.get_text(" ", strip=True) if label else None}
    if not entries:
        raise ValueError("Tatar category has no recognizable book cards.")
    page = category_page(url)
    following = {}
    for a in soup.select(".irhp-language-pagination a[href]"):
        target = native_url(a["href"], url)
        if category_page(target) is None:
            raise ValueError("Pager changed category.")
        number = category_page(target)
        if number == page + 1:
            following[target] = PageRequest(target)
        elif number > page + 1 and not soup.select_one('.irhp-language-pagination a.next'):
            raise ValueError("Pager skips the next category page.")
    return ListingPage(list(entries), list(following.values()), record_context=entries,
                       detect_repeats=True)


def record(html, page_url):
    url = native_url(page_url)
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main.irhp-book-page")
    hero = main.select_one(".irhp-book-hero__content") if main else None
    heading = hero.select_one("h1") if hero else None
    label = hero.select_one(".irhp-book-hero__term") if hero else None
    if heading is None or not heading.get_text(strip=True):
        raise ValueError("Publisher book detail heading is missing.")
    title = heading.get_text(" ", strip=True)
    language = label.get_text(" ", strip=True) if label else None
    details = {}
    for detail in main.select(".irhp-book-detail"):
        key, value = detail.select_one("small"), detail.select_one("strong")
        if key and value:
            details[key.get_text(" ", strip=True)] = value.get_text(" ", strip=True)
    admitted = language == TATAR_LABEL and details.get("Language") == TATAR_LABEL
    alphabet_lesson = re.search(r"гарәп.*(?:хәреф|алфавит)|арабск.*(?:букв|алфавит)", title, re.I)
    reason = ("Arabic alphabet teaching material requires individual file-language review."
              if alphabet_lesson else "Book lacks consistent explicit Tatar language labels.")
    admitted = admitted and not alphabet_lesson
    description = main.select_one(".irhp-book-description__content")
    assets, excluded = {}, []
    for card in main.select(".irhp-book-file-card"):
        name, kind, anchor = card.select_one("strong"), card.select_one("small"), card.select_one("a[data-irhp-download-file][href]")
        if name is None or kind is None or anchor is None:
            raise ValueError("Individual publisher file descriptor is missing.")
        filename = name.get_text(" ", strip=True)
        target = native_url(anchor["href"], url)
        identity = download_id(target)
        if not identity or identity != anchor.get("data-package"):
            raise ValueError("File link disagrees with its package identifier.")
        descriptor = {"url": target, "filename_claim": filename,
                      "file_description_raw": kind.get_text(" ", strip=True), "href_raw": anchor["href"]}
        if (PurePosixPath(filename).suffix.lower() != ".pdf"
                or not kind.get_text(strip=True).startswith("PDF")):
            excluded.append({**descriptor, "reason": "Not an individually advertised PDF; no images, office files or bundles acquired."})
            continue
        query = parse_qs(urlsplit(target).query)
        if query.get("filename", [filename])[0] != filename:
            raise ValueError("File link filename conflicts with its label.")
        assets[target] = {**descriptor, "label": filename, "extension": ".pdf",
                          "source_asset_key": "pdf:" + identity + ":" + query.get("ind", [filename])[0],
                          "unsupported_reason": None if admitted else reason}
    return {"url": url, "title": title, "language_raw": language,
            "language_selection": "selected" if admitted else "excluded",
            "details_raw": details, "excluded_files": excluded,
            "description_raw": description.get_text(" ", strip=True) if description else None,
            "admission_reason": "Explicit publisher item-language claims; actual composition is not inferred from category membership."}, list(assets.values())


def download(http, manifest, summary, log, recheck):
    from .core import download as originals
    originals(http, manifest, summary, log, recheck, extensions={".pdf"})
