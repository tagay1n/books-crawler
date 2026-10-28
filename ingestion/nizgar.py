"""Original bilingual magazine PDFs from Nizgar's native archive page."""

from pathlib import PurePosixPath
import re
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from requests.utils import requote_uri

from .documents import canonical, same_origin
from .network import InvalidDocument
from .paging import ListingPage


ARCHIVE_URL = "https://nizgar.ru/zhurnal-nizhegorodskie-tatary-nizhgar-tatarlary/"
PUBLICATION_TITLE = "Нижегородские татары. Нижгар татарлары"
PARSER_VERSION = 1
MONTHS = {"январь": 1, "февраль": 2, "март": 3, "апрель": 4,
          "май": 5, "июнь": 6, "июль": 7, "август": 8, "сентябрь": 9,
          "октябрь": 10, "ноябрь": 11, "декабрь": 12}


def normalized_url(href, base=ARCHIVE_URL):
    return requote_uri(canonical(href, base))


def allowed_url(url):
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    return (same_origin(url, ARCHIVE_URL) and not parsed.query and not parsed.fragment
            and "\\" not in path and not {".", ".."}.intersection(path.split("/"))
            and (parsed.path == urlsplit(ARCHIVE_URL).path
                 or (path.startswith("/wp-content/uploads/") and path.lower().endswith(".pdf"))))


def prepare_http(http, session_file):
    def validate_request(method, url, data):
        if method != "GET" or data or not allowed_url(url):
            raise ValueError("Nizgar permits only native read-only HTTPS archive and PDF requests.")

    def check_response(response, *args, **kwargs):
        target = normalized_url(response.headers.get("Location", ""), response.url) if response.is_redirect else response.url
        if not allowed_url(response.url) or not allowed_url(target):
            response.close()
            raise InvalidDocument("Nizgar redirected outside the selected HTTPS source paths.")
        return response

    http.validate_request = validate_request
    http.session.hooks["response"].append(check_response)


def catalog(html, page_url):
    if page_url != ARCHIVE_URL:
        raise ValueError("Unexpected Nizgar magazine archive URL.")
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1")
    areas = soup.select(".wrap.post-wrap")
    if (heading is None or heading.get_text(" ", strip=True) != f"Журнал «{PUBLICATION_TITLE}»"
            or len(areas) != 1):
        raise ValueError("Nizgar magazine archive heading or content structure is missing.")
    content = areas[0]
    if content.select_one('a[rel~="next"], .pagination a[href], .page-links a[href]'):
        raise ValueError("Nizgar archive acquired pagination; traversal needs review.")
    cards = []
    for block in content.select(".wp-block-file"):
        links = [a for a in block.select("a[href]")
                 if PurePosixPath(unquote(urlsplit(a["href"]).path)).suffix.lower() == ".pdf"]
        labels = [a for a in links if "wp-block-file__button" not in a.get("class", [])]
        if len(labels) != 1:
            raise ValueError("Nizgar file block must have one labelled issue PDF.")
        label = labels[0].get_text(" ", strip=True)
        match = re.fullmatch(r"Выпуск\s*№\s*([1-9]\d*)\s*(.*?)\s*" + re.escape(PUBLICATION_TITLE), label)
        if match is None:
            raise ValueError(f"Unrecognized Nizgar issue label: {label}")
        url = normalized_url(labels[0]["href"], page_url)
        if any(normalized_url(a["href"], page_url) != url for a in links):
            raise ValueError("Nizgar issue label and download button refer to different PDFs.")
        date_raw = match[2].strip()
        years = set(re.findall(r"\b(?:19|20)\d{2}\b", date_raw))
        dated = re.fullmatch(r"\((" + "|".join(MONTHS) + r")\s+((?:19|20)\d{2})\)", date_raw, re.I)
        cards.append({"issue_number_claim": int(match[1]), "title_raw": label,
                      "date_raw": date_raw, "year_claim": int(next(iter(years))) if len(years) == 1 else None,
                      "month_claim": MONTHS[dated[1].lower()] if dated else None,
                      "url": url, "links_raw": [{"href_raw": a["href"],
                                                  "label_raw": a.get_text(" ", strip=True)} for a in links]})
    if not cards:
        raise ValueError("Nizgar archive has no recognizable issue PDF blocks.")
    return cards


def parse_listing(html, request, root):
    catalog(html, request.url)
    # There are no issue detail pages: keep the native archive as one observation.
    return ListingPage([ARCHIVE_URL], [])


def record(html, page_url):
    cards = catalog(html, page_url)
    assets = {}
    for card in cards:
        url = card["url"]
        asset = assets.setdefault(url, {"url": url, "label": card["title_raw"], "extension": ".pdf",
                                       "unsupported_reason": None if allowed_url(url) else
                                       "Issue PDF is outside the configured native HTTPS file paths.",
                                       "issue_cards": []})
        if card not in asset["issue_cards"]:
            asset["issue_cards"].append(card)
    metadata = {"url": ARCHIVE_URL, "title": f"Журнал «{PUBLICATION_TITLE}»",
                "publication_title": PUBLICATION_TITLE, "cards": cards,
                "language_scope": "Tatar-containing bilingual magazine series; individual issue language/proportion unverified.",
                "admission_reason": "Issue PDF explicitly listed in the selected bilingual magazine archive; no inference from geography or upload date.",
                "coverage_note": "Observed listing only; missing issue numbers are not synthesized, and publication dates are source claims.",
                "attachments": [{"url": a["url"], "label": a["label"]} for a in assets.values()]}
    return metadata, list(assets.values())
