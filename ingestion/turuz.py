"""Direct originals from Turuz's Tatar-labelled dictionary listing rows."""

import re
import unicodedata
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from requests.utils import requote_uri

from .documents import canonical, same_origin
from .network import InvalidDocument
from .paging import ListingPage


ARCHIVE_URL = "https://turuz.com/index/pitik/category/2"
PARSER_VERSION = 1
FORMATS = {".pdf", ".djvu", ".djv", ".doc", ".docx"}


def normalized_title(title):
    return "".join(c for c in unicodedata.normalize("NFKD", title.casefold())
                   if not unicodedata.combining(c)).replace("ı", "i")


def selection(title):
    text = normalized_title(title).replace("_", " ")
    if re.search(r"\b(?:kirim|crimean|qirim)\b", text):
        return False, "Crimean Tatar is outside the selected Kazan-Tatar scope."
    if not re.match(r"(?:tatar(?:ca|ça)?\b|lehceyi[ _-]+tatari\b)", text):
        return False, "No explicit Tatar dictionary title prefix; general multilingual and topic matches are excluded."
    return True, "Tatar dictionary title in the native dictionary category; source claim only, content language unverified."


def file_url(href, base):
    url = canonical(href, base)
    parsed = urlsplit(url)
    if parsed.scheme == "http" and parsed.netloc == "turuz.com":
        url = urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))
    return requote_uri(url)


def allowed_url(url):
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    return (same_origin(url, ARCHIVE_URL) and not parsed.query and not parsed.fragment
            and (parsed.path == urlsplit(ARCHIVE_URL).path
                 or (path.startswith("/storage/") and "\\" not in path
                     and not {".", ".."}.intersection(path.split("/")))))


def prepare_http(http, session_file):
    def validate_request(method, url, data):
        if method != "GET" or data or not allowed_url(url):
            raise ValueError("Turuz permits only read-only HTTPS dictionary-listing and hosted-file requests.")
    http.validate_request = validate_request

    def check_response(response, *args, **kwargs):
        target = canonical(response.headers.get("Location", ""), response.url) if response.is_redirect else response.url
        if not allowed_url(response.url) or not allowed_url(target):
            response.close()
            raise InvalidDocument("Turuz redirected outside the selected HTTPS source paths.")
        return response
    http.session.hooks["response"].append(check_response)


def catalog(html, page_url):
    if page_url.rstrip("/") != ARCHIVE_URL:
        raise ValueError("Unexpected Turuz dictionary listing URL.")
    soup = BeautifulSoup(html, "html.parser")
    heading = next((h for h in soup.select("h1") if h.get_text(" ", strip=True) == "Sözlük"), None)
    table = soup.select_one("table")
    if heading is None or table is None:
        raise ValueError("Turuz dictionary category heading or table is missing.")
    headers = [h.get_text(" ", strip=True) for h in table.select("th")]
    if headers != ["#", "Başlık", "Dosya Türü", "Boyut"]:
        raise ValueError("Turuz dictionary table columns changed.")
    rows = []
    for row in table.select("tr"):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        if len(cells) != 4:
            raise ValueError("Turuz dictionary row has unexpected columns.")
        anchor = cells[1].select_one("a.cat-make-link-download[href]")
        if anchor is None or not cells[0].get_text(strip=True).isdigit():
            raise ValueError("Turuz dictionary row is missing its native number or file link.")
        title = anchor.get_text(" ", strip=True)
        if not title:
            raise ValueError("Turuz dictionary row has an empty title.")
        # Retain all keyword leads, including explicit exclusions, for review.
        if "tatar" not in normalized_title(title):
            continue
        admitted, reason = selection(title)
        rows.append({"row_number_raw": cells[0].get_text(strip=True),
                     "title_raw": title, "format_raw": cells[2].get_text(" ", strip=True),
                     "size_raw": cells[3].get_text(" ", strip=True),
                     "href_raw": anchor["href"], "url": file_url(anchor["href"], page_url),
                     "selected": admitted, "selection_reason": reason})
    if not rows or not any(row["selected"] for row in rows):
        raise ValueError("Turuz dictionary listing contains no recognizable Tatar dictionary rows.")
    return rows


def parse_listing(html, request, root):
    catalog(html, request.url)
    # Like Isxaki, one native collection observation retains individual book cards.
    return ListingPage([ARCHIVE_URL], [])


def record(html, page_url):
    rows = catalog(html, page_url)
    assets = {}
    for row in rows:
        if not row["selected"]:
            continue
        url = row["url"]
        extension = PurePosixPath(unquote(urlsplit(url).path)).suffix.lower()
        reason = None
        if not allowed_url(url) or not unquote(urlsplit(url).path).startswith("/storage/"):
            reason = "Dictionary file is outside the selected hosted-file paths."
        elif extension not in FORMATS:
            reason = "Only direct PDF, DjVu and Word originals are selected; archive expansion is unsupported."
        asset = assets.setdefault(url, {"url": url, "label": row["title_raw"],
                                       "extension": extension, "unsupported_reason": reason,
                                       "catalog_rows": []})
        asset["catalog_rows"].append(row)
    metadata = {"url": ARCHIVE_URL, "title": "Turuz: Tatar dictionary selection",
                "title_raw": "Sözlük", "cards": rows,
                "admission_reason": "Native Tatar dictionary title claims; bilingual works included, Crimean Tatar and general multilingual titles excluded. Document language and edition completeness remain unverified.",
                "scope": "Dictionary category only; no whole-site search, reader conversion or package expansion.",
                "attachments": [{"url": a["url"], "label": a["label"]} for a in assets.values()]}
    return metadata, list(assets.values())
