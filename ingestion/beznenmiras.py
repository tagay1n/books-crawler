"""Безнең мирас issue archive; covers are not complete journal documents."""

import re
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

from .documents import DOCUMENT_EXTENSIONS, canonical, same_origin
from .network import InvalidDocument
from .paging import ListingPage, PageRequest


ARCHIVE_URL = "https://beznenmiras.ru/categories/widget/list/svezii-vypusk"
PARSER_VERSION = 1
LISTING_PATH = re.compile(r"/categories/widget/list/svezii-vypusk(?:/page/([1-9]\d*))?/?")
ISSUE_PATH = re.compile(r"/categories/([\w-]+)/?")
DOCUMENT_FORMATS = DOCUMENT_EXTENSIONS - {".html", ".htm"}


def checked_url(href, base, pattern):
    url = canonical(href, base)
    parsed = urlsplit(url)
    if not same_origin(url, ARCHIVE_URL) or parsed.query or not pattern.fullmatch(parsed.path):
        raise ValueError(f"Unexpected Безнең мирас archive URL: {url}")
    return url


def prepare_http(http, session_file):
    def validate_request(method, url, data):
        if method != "GET" or data or not same_origin(url, ARCHIVE_URL):
            raise ValueError("Безнең мирас permits only same-origin read-only HTTPS requests.")
    http.validate_request = validate_request

    def check_response(response, *args, **kwargs):
        target = canonical(response.headers.get("Location", ""), response.url) if response.is_redirect else response.url
        if not same_origin(response.url, ARCHIVE_URL) or not same_origin(target, ARCHIVE_URL):
            response.close()
            raise InvalidDocument("Безнең мирас redirected outside its HTTPS source origin.")
        return response
    http.session.hooks["response"].append(check_response)


def parse_listing(html, request, root):
    path = LISTING_PATH.fullmatch(urlsplit(checked_url(request.url, root, LISTING_PATH)).path)
    current_page = int(path.group(1) or 1)
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("section.list")
    heading = container.select_one("h1.list-page__title") if container else None
    items = container.select_one("ul.list__list") if container else None
    if heading is None or heading.get_text(" ", strip=True) != "Саннар" or items is None:
        raise ValueError("Безнең мирас issue archive structure is missing.")
    records = {}
    for item in items.select("li.list__item"):
        anchor = item.select_one("a.list__link[href]")
        title = item.select_one(".list__title")
        if anchor is None or title is None:
            raise ValueError("Безнең мирас issue card is missing its title or link.")
        url = checked_url(anchor["href"], request.url, ISSUE_PATH)
        date = item.select_one("time")
        cover = item.select_one("img[src]")
        if url in records:
            raise ValueError("Безнең мирас archive repeats an issue card.")
        records[url] = {"listing_url": request.url,
                        "issue_label_raw": title.get_text(" ", strip=True),
                        "date_raw": date.get_text(" ", strip=True) if date else None,
                        "cover_url": canonical(cover["src"], request.url) if cover else None}
    if not records:
        raise ValueError("Безнең мирас listing contains no recognizable issue cards.")
    following = {}
    for anchor in container.select("a.pagination__link[href]"):
        url = checked_url(anchor["href"], request.url, LISTING_PATH)
        target = LISTING_PATH.fullmatch(urlsplit(url).path)
        number = int(target.group(1) or 1)
        if number == current_page + 1:
            following[url] = PageRequest(url)
        elif number != current_page - 1:
            raise ValueError("Безнең мирас archive pagination does not advance by one page.")
    return ListingPage(list(records), list(following.values()), entries=len(records),
                       record_context=records, detect_repeats=True)


def record(html, page_url):
    url = checked_url(page_url, ARCHIVE_URL, ISSUE_PATH)
    soup = BeautifulSoup(html, "html.parser")
    area = soup.select_one(".single-page__main")
    heading = area.select_one("h1.single__title") if area else None
    content = area.select_one(".single__content") if area else None
    if heading is None or content is None:
        raise ValueError("Безнең мирас issue structure is missing.")
    title = heading.get_text(" ", strip=True)
    issue = re.fullmatch(r"№\s*(\d{1,2})\s*\.\s*(\d{4})", title)
    if issue is None or not 1 <= int(issue.group(1)) <= 12:
        raise ValueError(f"Unrecognized Безнең мирас issue title: {title}")
    date = area.select_one(".single__date time")
    cover = area.select_one("img.single__image[src]")
    metadata = {
        "url": url, "issue_id": ISSUE_PATH.fullmatch(urlsplit(url).path).group(1),
        "publication_title": "Безнең мирас", "title": title, "title_raw": title,
        "issue_number_claim": int(issue.group(1)), "year_claim": int(issue.group(2)),
        "date_raw": date.get_text(" ", strip=True) if date else None,
        "description": content.get_text(" ", strip=True),
        "cover_url": canonical(cover["src"], url) if cover else None,
        "admission_reason": "Issue in the configured Безнең мирас archive; document language and completeness unverified.",
    }
    assets = {}
    for anchor in content.select("a[href]"):
        target = canonical(anchor["href"], url)
        extension = PurePosixPath(unquote(urlsplit(target).path)).suffix.lower()
        if extension not in DOCUMENT_FORMATS:
            continue
        assets[target] = {
            "url": target, "label": anchor.get_text(" ", strip=True) or title,
            "extension": extension,
            "unsupported_reason": None if same_origin(target, ARCHIVE_URL) else "Attachment is outside the configured source origin.",
        }
    metadata["attachments"] = [{"url": a["url"], "label": a["label"]} for a in assets.values()]
    metadata["acquisition_note"] = (
        "Linked original document candidates; language and completeness unverified." if assets else
        "Metadata only: no original document link found in issue content; cover images are not acquired."
    )
    return metadata, list(assets.values())


def record_key(metadata):
    return "issue:" + metadata["issue_id"]
