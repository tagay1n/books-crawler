"""Reviewed Tatar textbook PDFs from Obuchalka and public Fileskachat links."""

from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from . import language_reviews
from .network import BudgetStop, InvalidDocument
from .paging import ListingPage


ARCHIVE_URL = "https://obuchalka.org/knigi-po-tatarskomu-yaziku/"
PARSER_VERSION = 1
UNIQUE_RECORDS = True
BOOK_PATH = re.compile(r"/((?:19|20)\d{10,14})/[a-z0-9-]+\.html")
TOKEN = r"([1-9]\d*)_([a-f0-9]{32})"
FILE_PATH = re.compile(r"/file/" + TOKEN + r"\.html")
DOWNLOAD_PATH = re.compile(r"/download/" + TOKEN + r"\.html")
GET_PATH = re.compile(r"/getfile/" + TOKEN)
STATIC_PATH = re.compile(r"/download/[a-f0-9]/[a-f0-9]/([1-9]\d*)_[a-f0-9]{32}\.pdf")
DESCRIPTORS = ("url", "label", "extension", "source_asset_key", "delivery_provider",
               "hrefs_raw", "source_unsupported_code", "source_unsupported_reason")


def book_url(href, base=ARCHIVE_URL):
    p = urlsplit(urljoin(base, href))
    if (p.scheme not in {"http", "https"} or p.netloc not in {"obuchalka.org", "www.obuchalka.org"}
            or p.query or not (p.path == urlsplit(ARCHIVE_URL).path or BOOK_PATH.fullmatch(p.path))):
        raise ValueError("Expected the selected Obuchalka category or a native dated book record.")
    return urlunsplit(("https", "obuchalka.org", p.path, "", ""))


def file_url(href, base=ARCHIVE_URL):
    p = urlsplit(urljoin(base, href))
    if (p.scheme not in {"http", "https"} or p.netloc != "fileskachat.com"
            or p.query or p.fragment or not FILE_PATH.fullmatch(p.path)):
        raise ValueError("Expected an explicitly linked Fileskachat file page.")
    return urlunsplit(("https", "fileskachat.com", p.path, "", ""))


def route(url):
    p = urlsplit(url)
    if p.scheme != "https" or p.query or p.fragment:
        raise ValueError("Only the selected HTTPS retrieval routes are supported.")
    if p.netloc in {"obuchalka.org", "www.obuchalka.org"}:
        return "book", book_url(url)
    if p.netloc == "fileskachat.com":
        for kind, pattern in (("file", FILE_PATH), ("download", DOWNLOAD_PATH), ("getfile", GET_PATH)):
            match = pattern.fullmatch(p.path)
            if match:
                return kind, match[1] + "_" + match[2]
    match = STATIC_PATH.fullmatch(p.path)
    if re.fullmatch(r"static[1-9]\d*\.fileskachat\.com", p.netloc) and match:
        return "pdf", match[1]
    raise ValueError("Unexpected Obuchalka/Fileskachat origin or resource path.")


def parse_listing(html, request, root):
    if book_url(request.url) != ARCHIVE_URL:
        raise ValueError("Unexpected Obuchalka category route.")
    soup = BeautifulSoup(html, "html.parser")
    area = soup.select_one("#content .art")
    heading = area.select_one("h1") if area else None
    group = area.select_one("#groupdata") if area else None
    if heading is None or heading.get_text(" ", strip=True) != "Книги по татарскому языку" or group is None:
        raise ValueError("Obuchalka Tatar-subject category structure is missing.")
    entries = {}
    for anchor in group.select("li a[href]"):
        if not BOOK_PATH.fullmatch(urlsplit(urljoin(request.url, anchor["href"])).path):
            continue
        url = book_url(anchor["href"], request.url)
        title = anchor.get_text(" ", strip=True)
        if not title:
            raise ValueError("Obuchalka book link is missing its title.")
        entries.setdefault(url, {"catalog_url": ARCHIVE_URL, "title_raw": title})
    if not entries:
        raise ValueError("Obuchalka category has no recognizable book records.")
    if area.select_one('a[rel~="next"], .pagination a[href], .pager a[href]'):
        raise ValueError("Obuchalka category acquired pagination; traversal needs review.")
    return ListingPage(list(entries), [], record_context=entries)


def record(html, page_url):
    url = book_url(page_url)
    identity = BOOK_PATH.fullmatch(urlsplit(url).path)
    if identity is None:
        raise ValueError("Expected an Obuchalka book detail page.")
    soup = BeautifulSoup(html, "html.parser")
    area = soup.select_one("#content .art")
    heading = area.select_one("h1") if area else None
    content = area.select_one(".content-article-text") if area else None
    if heading is None or not heading.get_text(strip=True) or content is None:
        raise ValueError("Obuchalka book heading or description is missing.")
    title = heading.get_text(" ", strip=True)
    assets, links = {}, []
    for anchor in area.select("a[href]"):
        raw = anchor["href"]
        target = urljoin(url, raw)
        if urlsplit(target).netloc not in {"fileskachat.com", "yadi.sk", "disk.yandex.ru"}:
            continue
        links.append({"url_raw": target, "label_raw": anchor.get_text(" ", strip=True)})
        if not FILE_PATH.fullmatch(urlsplit(target).path) or urlsplit(target).netloc != "fileskachat.com":
            continue
        stable = file_url(target)
        asset = assets.setdefault(stable, {
            "url": stable, "label": title, "extension": ".pdf",
            "source_asset_key": "fileskachat:" + FILE_PATH.fullmatch(urlsplit(stable).path)[0],
            "delivery_provider": "fileskachat", "hrefs_raw": [],
            "source_unsupported_code": "language_unknown",
            "source_unsupported_reason": "Subject/title does not establish file language; an individual Tatar PDF review is required.",
            "unsupported_code": "language_unknown",
            "unsupported_reason": "Subject/title does not establish file language; an individual Tatar PDF review is required.",
        })
        if raw not in asset["hrefs_raw"]:
            asset["hrefs_raw"].append(raw)
    metadata = {"url": url, "record_id": identity[1][8:], "title": title, "title_raw": title,
                "description_raw": content.get_text(" ", strip=True), "delivery_links": links,
                "language_selection": "individual_file_review_required",
                "admission_reason": "Mixed Tatar-subject catalog; only individually reviewed, SHA-256-pinned Tatar textbook PDFs are acquired. Category, title and annotation do not grant admission."}
    return metadata, list(assets.values())


def record_key(metadata):
    return "book:" + metadata["record_id"]


resolve_record = language_reviews.resolve


def advertised_download(html, page_url, token):
    """Read literal link markup, including document.write strings; execute no JS."""
    targets = set()
    for href in re.findall(r'href\s*=\s*[\'"]([^\'"<>]+)[\'"]', html, re.I):
        url = urljoin(page_url, href)
        try:
            kind, identity = route(url)
        except ValueError:
            continue
        if kind == "download" and identity == token:
            targets.add(url)
    if len(targets) != 1:
        raise InvalidDocument("Fileskachat file page lacks its unique ordinary download link.")
    return targets.pop()


def delivery_info(html, stable):
    soup = BeautifulSoup(html, "html.parser")
    canonical = soup.select_one('link[rel="canonical"][href]')
    if canonical is None or canonical["href"] != stable:
        raise InvalidDocument("Fileskachat file page does not identify the selected file.")
    fields = {}
    for row in soup.select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) == 2:
            fields[cells[0].get_text(" ", strip=True).rstrip(":")] = cells[1].get_text(" ", strip=True)
    filename = fields.get("Файл", "")
    if Path(filename).suffix.lower() != ".pdf":
        raise InvalidDocument("Only standalone Fileskachat PDFs are supported.")
    return {"filename_raw": filename, "size_claim_raw": fields.get("Информация", "")}


def prepare_http(http, session_file):
    http.language_reviews = language_reviews.load(
        Path(__file__).with_name("obuchalka-language-reviews.json"), file_url, "Obuchalka")
    http.language_reviews.update(language_reviews.load(
        http.settings.artifacts_root / "obuchalka" / "language-reviews.json", file_url, "Obuchalka"))

    def validate_request(method, url, data):
        if method != "GET" or data:
            raise ValueError("Obuchalka retrieval permits read-only GET requests only.")
        route(url)

    def check_response(response, *args, **kwargs):
        try:
            before = route(response.url)
            if response.is_redirect:
                target = route(urljoin(response.url, response.headers["Location"]))
                if target != before and not (before[0] in {"getfile", "pdf"} and target[0] == "pdf"
                                             and target[1] == before[1].split("_")[0]):
                    raise ValueError("Redirect changed the file identity or provider.")
        except (ValueError, KeyError):
            response.close()
            raise InvalidDocument("Obuchalka/Fileskachat returned an unexpected resource redirect.") from None
        return response

    def validate_acquisition(asset):
        language_reviews.validate_acquisition(http, asset)
        if not asset.get("language_review") or asset.get("extension") != ".pdf":
            raise InvalidDocument("Only individually reviewed Tatar textbook PDFs may be acquired.")
        size = asset["language_review"].get("observed_size")
        if type(size) is int and size > 0:
            if size > http.settings.max_file_bytes:
                raise InvalidDocument("Reviewed PDF exceeds max_file_bytes; no request started.")
            if size > http.settings.max_download_bytes - http.budget.bytes:
                raise BudgetStop("download byte cap")

    original_get = http.get

    def get_pdf(url, headers=None):
        stable = file_url(url)
        token = route(stable)[1]
        info_html = http.text(stable)
        info = delivery_info(info_html, stable)
        download_url = advertised_download(info_html, stable, token)
        download_html = http.text(download_url)
        soup = BeautifulSoup(download_html, "html.parser")
        link = soup.select_one("a#direct_link[href]")
        target = urljoin(download_url, link["href"]) if link else ""
        if not link or route(target) != ("getfile", token):
            raise InvalidDocument("Fileskachat download page lacks the expected direct file link.")
        response = original_get(target, headers=headers)
        response.obuchalka_file = stable
        response.obuchalka_delivery = {"file_page_url": stable, "download_page_url": download_url,
                                       "direct_link_url": target, **info}
        return response

    def validate_download(response, asset):
        kind, identity = route(response.url)
        expected = route(asset["url"])[1]
        if (getattr(response, "obuchalka_file", None) != asset["url"]
                or (kind, identity) not in {("getfile", expected), ("pdf", expected.split("_")[0])}):
            raise InvalidDocument("Download is not the selected Fileskachat PDF.")
        http.delivery_provenance = response.obuchalka_delivery

    def validate_acquired(asset, result):
        return {**language_reviews.validate_acquired(asset, result),
                "delivery_provenance": http.delivery_provenance}

    http.validate_request = validate_request
    http.session.hooks["response"].append(check_response)
    http.validate_acquisition = validate_acquisition
    http.validate_download_response = validate_download
    http.validate_acquired_asset = validate_acquired
    http.get = get_pdf


def download(http, manifest, summary, log, recheck):
    from .core import download as download_originals
    language_reviews.refresh(http, manifest, PARSER_VERSION, DESCRIPTORS)
    download_originals(http, manifest, summary, log, recheck, extensions={".pdf"})
