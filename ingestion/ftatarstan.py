"""Native OJS full-issue PDFs explicitly labelled Tatar by Fänni Tatarstan."""

import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .documents import canonical, same_origin
from .network import InvalidDocument, install_native_get_guard
from .paging import ListingPage, PageRequest


BASE = "https://ftatarstan.ru/index.php/ftat/ru/issue/"
ARCHIVE_URL = BASE + "archive"
PARSER_VERSION = 1
ISSUE = re.compile(r"view/([1-9]\d*)")
GALLEY = re.compile(r"(?:view|download)/([1-9]\d*)/([1-9]\d*)(?:/[1-9]\d*)?")


def native_url(href, base=ARCHIVE_URL):
    url = canonical(href.strip(), base).rstrip("/")
    parsed = urlsplit(url)
    if (not same_origin(url, BASE) or parsed.query or not url.startswith(BASE)
            or not re.fullmatch(r"archive(?:/[1-9]\d*)?|view/[1-9]\d*|(?:view|download)/[1-9]\d*/[1-9]\d*(?:/[1-9]\d*)?", url[len(BASE):])):
        raise ValueError("Only native journal archive, issue and PDF-galley routes are supported.")
    return url


def galley_identity(url):
    match = GALLEY.fullmatch(native_url(url)[len(BASE):])
    if match is None:
        raise ValueError("Expected a native issue PDF galley.")
    return match[1], match[2]


def prepare_http(http, session_file):
    install_native_get_guard(http, native_url, "Fänni Tatarstan",
                             redirect_allowed=lambda before, after: galley_identity(before) == galley_identity(after))

    def validate_download(response, asset):
        identity = galley_identity(asset["url"])
        if any(galley_identity(r.url) != identity for r in [*response.history, response]):
            raise InvalidDocument("Delivered PDF belongs to a different issue galley.")

    http.validate_download_response = validate_download


def parse_listing(html, request, root):
    url = native_url(request.url)
    if not re.fullmatch(r"archive(?:/[1-9]\d*)?", url[len(BASE):]):
        raise ValueError("Expected the native journal archive.")
    soup = BeautifulSoup(html, "html.parser")
    area = soup.select_one(".page_issue_archive")
    if area is None or soup.title is None or "Фәнни Татарстан" not in soup.title.get_text():
        raise ValueError("Journal archive identity or structure is missing.")
    entries = {}
    for card in area.select(".obj_issue_summary"):
        anchor = card.select_one("h2 a.title[href]")
        if anchor is None or not anchor.get_text(strip=True):
            raise ValueError("Journal archive issue title is missing.")
        target = native_url(anchor["href"], url)
        if ISSUE.fullmatch(target[len(BASE):]) is None:
            raise ValueError("Archive card does not identify a native issue.")
        entries[target] = {"catalog_url": url, "title_raw": anchor.get_text(" ", strip=True),
                           "href_raw": anchor["href"]}
    if not entries:
        raise ValueError("Archive page contains no recognizable issues.")
    page = int(url.rsplit("/", 1)[1]) if url != ARCHIVE_URL else 1
    following = {}
    for anchor in area.select(".cmp_pagination a[href]"):
        target = native_url(anchor["href"], url)
        match = re.fullmatch(r"archive/([1-9]\d*)", target[len(BASE):])
        if match is None and target != ARCHIVE_URL:
            raise ValueError("Archive pager left its native archive.")
        number = int(match[1]) if match else 1
        if number == page + 1:
            following[target] = PageRequest(target)
        elif number > page + 1:
            raise ValueError("Archive pager skipped an intermediate page.")
    return ListingPage(list(entries), list(following.values()), record_context=entries,
                       detect_repeats=True)


def record(html, page_url):
    url = native_url(page_url)
    identity = ISSUE.fullmatch(url[len(BASE):])
    soup = BeautifulSoup(html, "html.parser")
    area = soup.select_one(".page_issue .obj_issue_toc")
    heading = soup.select_one(".page_issue h1")
    if (identity is None or area is None or heading is None
            or soup.title is None or "Фәнни Татарстан" not in soup.title.get_text()):
        raise ValueError("Native journal issue identity, title or contents are missing.")
    title = heading.get_text(" ", strip=True)
    date = area.select_one(".heading .published .value")
    doi = area.select_one(".heading .doi .id")
    assets = {}
    for anchor in area.select(":scope > .galleys a.obj_galley_link.pdf[href]"):
        target = native_url(anchor["href"], url)
        issue_id, galley_id = galley_identity(target)
        if issue_id != identity[1]:
            raise ValueError("Full-issue PDF link belongs to another issue.")
        label = anchor.get_text(" ", strip=True)
        selected = re.fullmatch(r"PDF\s*\(татарский\)", label, re.I) is not None
        assets[target] = {"url": target, "label": title, "extension": ".pdf",
                          "source_asset_key": "galley:" + galley_id,
                          "galley_view_url": target, "href_raw": anchor["href"],
                          "language_claim_raw": label,
                          "unsupported_reason": None if selected else "Full-issue galley lacks an explicit Tatar PDF label."}
    return {"url": url, "issue_id": identity[1], "title": title,
            "publication_date_raw": date.get_text(" ", strip=True) if date else None,
            "doi_raw": doi.get_text(" ", strip=True) if doi else None,
            "representation": "full_issue_pdf" if assets else "issue_metadata_only",
            "article_count_claim": len(area.select(".obj_article_summary")),
            "admission_reason": "Only full-issue galleys explicitly labelled Tatar are acquired; article PDFs and covers are excluded."}, list(assets.values())


def record_key(metadata):
    return "issue:" + metadata["issue_id"]


def resolve_record(http, metadata, assets):
    for asset in assets:
        if asset.get("unsupported_reason"):
            continue
        html = http.text(asset["galley_view_url"])
        soup = BeautifulSoup(html, "html.parser")
        targets = {}
        for anchor in soup.select("a.download[href]"):
            target = native_url(anchor["href"], asset["galley_view_url"])
            if not target.startswith(BASE + "download/") or galley_identity(target) != galley_identity(asset["galley_view_url"]):
                raise ValueError("Native viewer download link changed its issue or galley identity.")
            targets[target] = anchor["href"]
        if len(targets) != 1:
            raise ValueError("Native PDF viewer must advertise one unique original download.")
        asset["url"], asset["download_href_raw"] = next(iter(targets.items()))
    return metadata, assets


def download(http, manifest, summary, log, recheck):
    from .core import download as originals
    originals(http, manifest, summary, log, recheck, extensions={".pdf"})
