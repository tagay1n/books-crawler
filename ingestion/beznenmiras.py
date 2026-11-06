"""Безнең мирас issue archive; covers are not complete journal documents."""
from .runtime_config import option as operational_option

import re
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

from .documents import DOCUMENT_EXTENSIONS, canonical, same_origin
from .network import install_native_get_guard
from .paging import ListingPage, PageRequest


PARSER_VERSION = 2
LISTING_PATH = re.compile(r"/categories/widget/list/svezii-vypusk(?:/page/([1-9]\d*))?/?")
ISSUE_PATH = re.compile(r"/categories/([\w-]+)/?")
DOCUMENT_FORMATS = DOCUMENT_EXTENSIONS - {".html", ".htm"}


def checked_url(href, base, pattern):
    url = canonical(href, base)
    parsed = urlsplit(url)
    if not same_origin(url, operational_option('beznenmiras', 'archive_url')) or parsed.query or not pattern.fullmatch(parsed.path):
        raise ValueError(f"Unexpected Безнең мирас archive URL: {url}")
    return url


def prepare_http(http, session_file):
    origin = operational_option('beznenmiras', 'archive_url')

    def source_url(href, base=None):
        url = canonical(href, base or origin)
        if not same_origin(url, origin):
            raise ValueError("Безнең мирас request left its configured HTTPS origin.")
        return url

    install_native_get_guard(http, source_url, "Безнең мирас",
                             redirect_allowed=lambda before, after: same_origin(before, after))


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
    url = checked_url(page_url, operational_option('beznenmiras', 'archive_url'), ISSUE_PATH)
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
    # Keep publisher evidence separate from normalized claims. In particular,
    # subscription indexes and the interface locale are not language evidence.
    metadata["content_html"] = content.decode_contents()
    lead = area.select_one(".single__lead")
    if lead is not None:
        metadata["lead_raw"] = lead.get_text(" ", strip=True)
    metadata["subscription_indexes_raw"] = [
        paragraph.get_text(" ", strip=True)
        for paragraph in content.select("p")
        if re.search(r"[ПP]\s*\d{4,}", paragraph.get_text(" ", strip=True))
    ]
    metadata["page_metadata"] = [
        {"name": tag.get("property") or tag.get("name"), "content": tag["content"]}
        for tag in soup.select("meta[content]")
        if (tag.get("property") or tag.get("name") or "").startswith((
            "og:", "article:", "description", "author", "keywords"))
    ]
    metadata["content_links"] = []
    for anchor in content.select("a[href]"):
        target = canonical(anchor["href"], url)
        if urlsplit(target).scheme in {"http", "https"} and not urlsplit(target).username:
            metadata["content_links"].append({
                "url": target, "label": anchor.get_text(" ", strip=True)})
    metadata["reader_links"] = []
    for embed in content.select("iframe[src], embed[src], object[data]"):
        target = canonical(embed.get("src") or embed["data"], url)
        if urlsplit(target).scheme in {"http", "https"} and not urlsplit(target).username:
            metadata["reader_links"].append({
                "url": target, "kind": embed.name,
                "unsupported_reason": "Embedded reader delivery has not been verified; not acquired.",
            })
    assets = {}
    for anchor in content.select("a[href]"):
        target = canonical(anchor["href"], url)
        extension = PurePosixPath(unquote(urlsplit(target).path)).suffix.lower()
        if extension not in DOCUMENT_FORMATS:
            continue
        assets[target] = {
            "url": target, "label": anchor.get_text(" ", strip=True) or title,
            "extension": extension,
            "unsupported_reason": None if same_origin(target, operational_option('beznenmiras', 'archive_url')) else "Attachment is outside the configured source origin.",
        }
    metadata["attachments"] = [{"url": a["url"], "label": a["label"]} for a in assets.values()]
    metadata["acquisition_note"] = (
        "Linked original document candidates; language and completeness unverified." if assets else
        "Metadata only: no original document link found in issue content; cover images are not acquired."
    )
    return metadata, list(assets.values())


def record_key(metadata):
    return "issue:" + metadata["issue_id"]
