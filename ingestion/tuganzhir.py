"""Original issue PDFs explicitly linked in the bilingual Tugan Zhir archive."""

import re
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from requests.utils import requote_uri

from .documents import canonical
from .network import InvalidDocument, install_native_get_guard
from .paging import ListingPage


ARCHIVE_URL = "https://tuganzhir.org/archive/"
PARSER_VERSION = 1
PUBLICATION_TITLE = "Туган җир. Родной край"
# These storage hosts are advertised by the archive, not inferred mirrors.
PDF_ROOTS = ("https://tuganzhir.org/wp-content/uploads/",
             "https://tatar-congress.org/wp-content/uploads/",
             "https://tatarcongress.firsts3.ru/uploads/")
LANGUAGE_EVIDENCE = {
    "scope": "Publisher-declared Tatar/Russian series; individual issue proportions unverified.",
    "claim_raw": "Татар һәм рус телләрендә",
    "url": "https://tuganzhir.org/wp-content/uploads/2022/03/tuganzhir-N-1-2022.pdf",
    "pdf_page": 5,
    "sha256": "70c572cd1cdb747214419b9dd6711394eee8165b4f1bd4ef698700cc3af2412b",
}


def normalized_url(href, base=ARCHIVE_URL):
    return requote_uri(canonical(href.strip(), base))


def native_url(href, base=ARCHIVE_URL):
    url = normalized_url(href, base)
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    if (parsed.query or parsed.fragment or "\\" in path
            or {".", ".."}.intersection(path.split("/"))
            or not (url == ARCHIVE_URL or
                    (any(url.startswith(root) for root in PDF_ROOTS)
                     and path.lower().endswith(".pdf")))):
        raise ValueError("Only the native Tugan Zhir archive and its advertised PDF storage paths are supported.")
    return url


def prepare_http(http, session_file):
    # Exact resource identity is retained across redirects; no guessed mirrors.
    install_native_get_guard(http, native_url, "Tugan Zhir")

    def validate_download(response, asset):
        selected = native_url(asset["url"])
        if selected == ARCHIVE_URL or any(native_url(r.url) != selected
                                          for r in [*response.history, response]):
            raise InvalidDocument("Delivered PDF changed the selected archive file identity.")

    http.validate_download_response = validate_download


def catalog(html, page_url):
    if page_url != ARCHIVE_URL:
        raise ValueError("Unexpected Tugan Zhir archive URL.")
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1.entry-title")
    areas = soup.select(".td-main-content .td-page-content")
    if (heading is None or heading.get_text(" ", strip=True) != "Архив журнала"
            or len(areas) != 1):
        raise ValueError("Tugan Zhir archive heading or content structure is missing.")
    area = areas[0]
    if area.select_one('.page-numbers, .page-nav, .pagination, a[rel~="next"]'):
        raise ValueError("Tugan Zhir archive acquired pagination; traversal needs review.")
    cards = []
    for row in area.select("li"):
        links = [a for a in row.select("a[href]")
                 if unquote(urlsplit(a["href"]).path).lower().endswith(".pdf")]
        if not links:
            continue
        if len(links) != 1:
            raise ValueError("Tugan Zhir archive row must advertise one issue PDF.")
        anchor = links[0]
        label = anchor.get_text(" ", strip=True)
        year_heading = row.find_previous("h3")
        year_raw = year_heading.get_text(" ", strip=True) if year_heading else ""
        year = re.fullmatch(r"((?:19|20)\d{2})\s+ел", year_raw)
        if not label.startswith("«Туган җир»,") or year is None or year[1] not in label:
            raise ValueError("Tugan Zhir issue label or archive year is unrecognized.")
        target = normalized_url(anchor["href"], page_url)
        cards.append({"url": target, "title_raw": label, "year_claim": int(year[1]),
                      "year_heading_raw": year_raw, "row_raw": row.get_text(" ", strip=True),
                      "href_raw": anchor["href"]})
    if not cards:
        raise ValueError("Tugan Zhir archive has no recognizable issue PDFs.")
    return cards


def parse_listing(html, request, root):
    catalog(html, request.url)
    return ListingPage([ARCHIVE_URL], [])


def record(html, page_url):
    cards = catalog(html, page_url)
    assets = {}
    for card in cards:
        url = card["url"]
        reason = None
        try:
            native_url(url)
        except ValueError:
            reason = "Advertised issue PDF is outside the reviewed publisher storage paths."
        asset = assets.setdefault(url, {"url": url, "label": card["title_raw"],
                                       "extension": ".pdf", "unsupported_reason": reason,
                                       "issue_cards": [], "language_evidence": LANGUAGE_EVIDENCE})
        if card not in asset["issue_cards"]:
            asset["issue_cards"].append(card)
    return {"url": ARCHIVE_URL, "title": PUBLICATION_TITLE, "cards": cards,
            "language_evidence": LANGUAGE_EVIDENCE,
            "admission_reason": "Linked full issues of the publisher-declared Tatar/Russian series; article HTML, covers and unrelated library books excluded.",
            "coverage_note": "Observed archive only. Raw issue labels and size claims are retained; missing issues and dates are not synthesized.",
            "attachments": [{"url": a["url"], "label": a["label"]} for a in assets.values()]}, list(assets.values())
