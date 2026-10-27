"""Kazan Utları's linked archive and the JPEG pages supplied by its reader."""

import json
import re
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

from .documents import canonical, same_origin
from .paging import ListingPage, PageRequest


ARCHIVE_URL = "https://kazanutlary.ru/j-archive"
PARSER_VERSION = 1
DOWNLOAD_UNIT = "issue"
ISSUE_PATH = re.compile(r"/j-archive/journals/([\w-]+)/?")
YEAR_PATH = re.compile(r"/j-archive/sections/[\w-]+/[\w-]+/journals/?")


def checked_url(href, base, pattern):
    url = canonical(href, base)
    parsed = urlsplit(url)
    if not same_origin(url, ARCHIVE_URL) or not pattern.fullmatch(parsed.path):
        raise ValueError(f"Unexpected archive URL: {url}")
    return url


def parse_listing(html, request, root):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main.jarchive__main")
    if main is None:
        raise ValueError("Kazan Utları archive structure is missing.")
    path = urlsplit(request.url).path.rstrip("/")
    is_root = path == "/j-archive"
    if not is_root and not YEAR_PATH.fullmatch(path):
        raise ValueError("Unrecognized archive listing route.")
    year_links = soup.select("a.jarchive-section-item__name[href]")
    following = {}
    context = {"listing_url": request.url}
    for link in year_links:
        url = checked_url(link["href"], root, YEAR_PATH)
        if urlsplit(url).query:
            raise ValueError("Unexpected query on archive year link.")
        if is_root:
            following.setdefault(url, PageRequest(url))
        if urlsplit(url).path.rstrip("/") == path:
            context["year_raw"] = link.get_text(" ", strip=True)
            group = link.find_parent("ul")
            heading = group.parent.find("h2", recursive=False) if group else None
            if heading:
                context["journal_title_raw"] = heading.get_text(" ", strip=True)
    if is_root and not following:
        raise ValueError("Archive does not expose any year listings.")
    records = {}
    for link in main.select("a.jarchive-journal-item__name[href]"):
        url = checked_url(link["href"], root, ISSUE_PATH)
        if urlsplit(url).query:
            raise ValueError("Unexpected query on issue reference.")
        records[url] = {**context, "issue_label_raw": link.get_text(" ", strip=True)}
    if not records:
        raise ValueError("Archive listing contains no recognizable issue cards.")
    # This is listing pagination only; pagination on an issue is its article index.
    next_link = main.select_one('a[rel~="next"][href]')
    if next_link:
        target = canonical(next_link["href"], request.url)
        old_page = parse_qs(urlsplit(request.url).query).get("page", ["1"])
        query = parse_qs(urlsplit(target).query)
        if (not same_origin(target, root) or urlsplit(target).path.rstrip("/") != path
                or len(old_page) != 1 or not old_page[0].isdecimal()
                or query != {"page": [str(int(old_page[0]) + 1)]}):
            raise ValueError("Archive pagination does not advance within its listing.")
        following[target] = PageRequest(target)
    return ListingPage(list(records), list(following.values()), entries=len(records),
                       record_context=records, detect_repeats=not is_root,
                       fingerprint=json.dumps([path, list(records)], ensure_ascii=False))


def record(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".journal__single")
    identity = ISSUE_PATH.fullmatch(urlsplit(page_url).path)
    heading = content.select_one("h1.single-page__title") if content else None
    reader = content.select_one("#lightgallery") if content else None
    if not identity or heading is None or reader is None:
        raise ValueError("Kazan Utları issue or reader structure is missing.")
    scripts = [s.get_text() for s in content.select("script:not([src])") if "zeroPad(index" in s.get_text()]
    if len(scripts) != 1:
        raise ValueError("Expected one recognized issue reader configuration.")
    script = scripts[0]
    journal = re.search(r"\blet\s+journal\s*=\s*'([\w-]+)'\s*;", script)
    count = re.search(r"\blet\s+count\s*=\s*(\d+)\s*;", script)
    if (not journal or not count or journal.group(1) != identity.group(1)
            or not re.search(r'zeroPad\(index,\s*3\)', script)
            or not re.search(r'index\s*<=\s*count', script)
            or '"/images/uploads/j-archive/" + journal + "/"' not in script
            or '+ ".jpg"' not in script):
        raise ValueError("Unrecognized image reader configuration; refusing to guess page URLs.")
    total = int(count.group(1))
    if not 0 < total <= 10000:
        raise ValueError("Invalid or excessive issue image count.")
    slug = journal.group(1)
    assets = [{"url": canonical(f"/images/uploads/j-archive/{slug}/{index:03d}.jpg", page_url),
               "label": f"{slug} / {index:03d}", "extension": ".jpg", "page_index": index,
               "kind": "page_image", "unsupported_reason": None} for index in range(total)]
    cover = reader.select_one("img[src]")
    if cover is None or canonical(cover["src"], page_url) != assets[0]["url"]:
        raise ValueError("Reader cover does not match its declared image sequence.")
    metadata = {"url": page_url, "issue_id": slug, "title": heading.get_text(" ", strip=True),
                "title_raw": heading.get_text(" ", strip=True), "expected_pages": total,
                "reader_configuration_raw": script.strip(), "reader_count_convention": "total_images",
                "reader_indexing_note": "The reader uses <= count; acquire count images, indices 0 through count-1.",
                "admission_reason": "Issue linked by the public Kazan Utları archive.",
                "attachments": [{k: a[k] for k in ("url", "label", "page_index")} for a in assets]}
    description = content.select_one(".single-page__overview")
    if description and description.get_text(" ", strip=True):
        metadata["description"] = description.get_text(" ", strip=True)
    return metadata, assets


def record_key(metadata):
    return "issue:" + metadata["issue_id"]
