"""Local acquisition of the five public Isxaki book/work collections."""

from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from requests.utils import requote_uri

from .documents import DOCUMENT_EXTENSIONS, canonical, same_origin
from .network import InvalidDocument
from .paging import ListingPage, PageRequest


ARCHIVE_URL = "https://isxaki.com/ijat/"
PARSER_VERSION = 1
COLLECTION_PATHS = (
    "/ijat/kitaplar/", "/ijat/asarlar/", "/asarlar-1908-1918-ellar/",
    "/1919-1947/", "/ijat/about/kitaplar/",
)
DOCUMENT_FORMATS = DOCUMENT_EXTENSIONS - {".html", ".htm"}
ALIASES = {"/tt/ijat/asarlar/": "/ijat/asarlar/",
           "/tt/asarlar-1908-1918-ellar/": "/asarlar-1908-1918-ellar/"}


def normalize_url(href, base):
    url = canonical(href, base)
    parsed = urlsplit(url)
    if parsed.hostname == "isxaki.com" and parsed.netloc == "isxaki.com" and parsed.scheme in {"http", "https"}:
        path = ALIASES.get(parsed.path, parsed.path)
        url = urlunsplit(("https", "isxaki.com", path, parsed.query, ""))
    return requote_uri(url)


def prepare_http(http, session_file):
    def validate_request(method, url, data):
        if method != "GET" or data or not same_origin(url, ARCHIVE_URL):
            raise ValueError("Isxaki permits only same-origin, read-only HTTPS requests.")
    http.validate_request = validate_request

    def check_response(response, *args, **kwargs):
        target = canonical(response.headers.get("Location", ""), response.url) if response.is_redirect else response.url
        if not same_origin(response.url, ARCHIVE_URL) or not same_origin(target, ARCHIVE_URL):
            response.close()
            raise InvalidDocument("Isxaki redirected outside its HTTPS source origin.")
        return response
    http.session.hooks["response"].append(check_response)


def collection_content(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one('[data-elementor-type="wp-page"]')
    title = soup.select_one("h1, h2")
    if (urlsplit(page_url).path not in COLLECTION_PATHS or content is None
            or title is None or not content.select_one(".elementor-image-box-title")):
        raise ValueError(f"Isxaki collection structure is missing: {page_url}")
    return content, title.get_text(" ", strip=True)


def parse_listing(html, request, root):
    if request.url.rstrip("/") == root.rstrip("/"):
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.select_one("h1, h2")
        links = {normalize_url(a["href"], request.url) for a in soup.select("a[href]")}
        collections = [canonical(path, root) for path in COLLECTION_PATHS]
        if heading is None or heading.get_text(" ", strip=True) != "Иҗат" or not set(collections) <= links:
            raise ValueError("Isxaki works entry point is missing its expected collection links.")
        return ListingPage([], [PageRequest(url) for url in collections])
    collection_content(html, request.url)
    return ListingPage([request.url], [])


def record(html, page_url):
    content, title = collection_content(html, page_url)
    cards, assets = [], {}
    for heading in content.select(".elementor-image-box-title"):
        column = heading.find_parent(class_="elementor-column")
        if column is None:
            raise ValueError("Isxaki book card has no containing column.")
        card_title = heading.get_text(" ", strip=True)
        description = column.select_one(".elementor-image-box-description")
        card = {"title_raw": card_title,
                "description_raw": description.get_text(" ", strip=True) if description else None,
                "links": []}
        for anchor in column.select("a[href]"):
            original = urljoin(page_url, anchor["href"])
            url = normalize_url(anchor["href"], page_url)
            extension = PurePosixPath(unquote(urlsplit(url).path)).suffix.lower()
            if extension not in DOCUMENT_FORMATS:
                continue
            label = anchor.get_text(" ", strip=True)
            card["links"].append({"href_raw": anchor["href"], "original_url": original,
                                  "url": url, "label": label})
            asset = assets.setdefault(url, {"url": url, "label": card_title, "extension": extension,
                "unsupported_reason": None if same_origin(url, ARCHIVE_URL) else "Attachment is outside the configured source origin.",
                "card_titles": []})
            if card_title not in asset["card_titles"]:
                asset["card_titles"].append(card_title)
        cards.append(card)
    metadata = {"url": page_url, "title": title, "title_raw": title, "cards": cards,
                "description": content.get_text(" ", strip=True),
                "admission_reason": "Document linked from a configured Isxaki book/work collection; language and completeness unverified.",
                "attachments": [{"url": a["url"], "label": a["label"]} for a in assets.values()]}
    return metadata, list(assets.values())
