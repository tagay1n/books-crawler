"""The Writers' Union's Yazuchy publisher catalog and direct book PDFs."""

from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from requests.utils import requote_uri

from . import language_reviews
from .documents import canonical, same_origin
from .network import InvalidDocument
from .paging import ListingPage


ARCHIVE_URL = "https://sptatar.com/yazuchy-n-shriyaty/"
PARSER_VERSION = 1
UNIQUE_RECORDS = True
DESCRIPTORS = ("url", "label", "extension", "href_raw", "source_asset_key",
               "source_unsupported_code", "source_unsupported_reason")


def native_url(href, base=ARCHIVE_URL):
    url = requote_uri(canonical(href, base))
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    if (not same_origin(url, ARCHIVE_URL) or parsed.query
            or "\\" in path or {".", ".."}.intersection(path.split("/"))
            or not (re.fullmatch(r"/[a-z0-9-]+/", path)
                    or (path.startswith("/wp-content/uploads/") and path.lower().endswith(".pdf")))):
        raise ValueError("Yazuchy resources must be native HTTPS book pages or uploaded PDFs.")
    return url


def document_url(url):
    url = native_url(url)
    if not urlsplit(url).path.startswith("/wp-content/uploads/"):
        raise ValueError("Expected a hosted Yazuchy original PDF.")
    return url


def parse_listing(html, request, root):
    if native_url(request.url) != ARCHIVE_URL:
        raise ValueError("Unexpected Yazuchy publisher listing URL.")
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1")
    if heading is None or heading.get_text(" ", strip=True) != "«Язучы» нәшрияты":
        raise ValueError("Yazuchy publisher catalog heading is missing.")
    entries = {}
    for card in soup.select(".row.long-post"):
        title = card.select_one(".title-holder h5.post-title")
        if title is None or title.parent.name != "a" or not title.parent.get("href"):
            raise ValueError("Yazuchy book card is missing its title or native record link.")
        url = native_url(title.parent["href"], request.url)
        if url == ARCHIVE_URL or url in entries:
            raise ValueError("Yazuchy catalog repeats a native book identity.")
        entries[url] = {"catalog_url": request.url,
                        "title_raw": title.get_text(" ", strip=True),
                        "description_raw": card.select_one(".title-holder").get_text(" ", strip=True),
                        "pdf_links_raw": [a["href"] for a in card.select('a[href]')
                                          if PurePosixPath(urlsplit(a["href"]).path).suffix.lower() == ".pdf"]}
    if not entries:
        raise ValueError("Yazuchy catalog has no recognizable book cards.")
    if soup.select_one('a[rel~="next"], .pagination a[href]'):
        raise ValueError("Yazuchy catalog acquired pagination; traversal needs review.")
    return ListingPage(list(entries), [], record_context=entries)


def record(html, page_url):
    url = native_url(page_url)
    if url == ARCHIVE_URL or urlsplit(url).path.startswith("/wp-content/"):
        raise ValueError("Expected a Yazuchy book detail page.")
    soup = BeautifulSoup(html, "html.parser")
    area = soup.select_one(".single-blog-post")
    heading = soup.select_one(".blog-single-area h1")
    content = area.select_one(".text article") if area else None
    if heading is None or content is None:
        raise ValueError("Yazuchy book heading or article body is missing.")
    title = heading.get_text(" ", strip=True)
    if not title:
        raise ValueError("Yazuchy book title is empty.")
    description = content.get_text(" ", strip=True)
    # A Tatar interface, author name or annotation does not identify file language.
    positive = re.search(r"татар теленә тәрҗемә", description, re.I)
    negative = re.search(r"на русский язык|на русском языке|рус теленә тәрҗемә", description, re.I)
    selected = positive is not None and negative is None
    language = "selected" if selected else "excluded" if negative else "unknown"
    code = None if selected else "language_excluded" if negative else "language_unknown"
    reason = None if selected else ("Record describes a Russian edition." if negative else
                                   "No explicit target-language claim; an individual file-language review is required.")
    assets = {}
    for anchor in content.select("a[href]"):
        raw = anchor["href"]
        target = canonical(raw, url)
        if PurePosixPath(unquote(urlsplit(target).path)).suffix.lower() != ".pdf":
            continue
        asset_code, asset_reason = code, reason
        try:
            target = document_url(target)
        except ValueError:
            asset_code, asset_reason = "unsupported_url", "PDF is outside the configured hosted-file paths."
        assets.setdefault(target, {"url": target, "label": title, "extension": ".pdf",
                                   "href_raw": raw, "source_asset_key": "original:" + target,
                                   "source_unsupported_code": asset_code,
                                   "source_unsupported_reason": asset_reason,
                                   "unsupported_code": asset_code, "unsupported_reason": asset_reason})
    metadata = {"url": url, "title": title, "title_raw": title,
                "description_raw": description, "language_selection": language,
                "language_evidence": [{"language": language, "claim_raw": match.group()}
                                      for language, match in (("tt", positive), ("ru", negative)) if match],
                "admission_reason": "Publisher book record; acquisition requires an explicit Tatar target-language claim or a SHA-256-pinned file review."}
    return metadata, list(assets.values())


resolve_record = language_reviews.resolve


def prepare_http(http, session_file):
    reviews = language_reviews.load(Path(__file__).with_name("yazuchy-language-reviews.json"), document_url, "Yazuchy")
    reviews.update(language_reviews.load(http.settings.artifacts_root / "yazuchy" / "language-reviews.json",
                                         document_url, "Yazuchy"))
    http.language_reviews = reviews

    def validate_request(method, url, data):
        if method != "GET" or data:
            raise ValueError("Yazuchy permits only read-only GET requests.")
        native_url(url)

    def check_response(response, *args, **kwargs):
        try:
            before = native_url(response.url)
            if response.is_redirect and native_url(canonical(response.headers["Location"], response.url)) != before:
                raise ValueError("Redirect changed the native resource.")
        except (ValueError, KeyError):
            response.close()
            raise InvalidDocument("Yazuchy returned an unexpected origin or resource redirect.") from None
        return response

    http.validate_request = validate_request
    http.session.hooks["response"].append(check_response)
    http.validate_acquisition = lambda asset: language_reviews.validate_acquisition(http, asset)
    http.validate_acquired_asset = language_reviews.validate_acquired


def download(http, manifest, summary, log, recheck):
    from .core import download as download_originals
    language_reviews.refresh(http, manifest, PARSER_VERSION, DESCRIPTORS)
    download_originals(http, manifest, summary, log, recheck, extensions={".pdf"})
