import re
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup


from .documents import DOCUMENT_EXTENSIONS, canonical, same_origin


def listing(html, page_url, archive_url):
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".news-list__list")
    if container is None or soup.select_one(".page__title") is None:
        raise ValueError(f"Archive structure is missing: {page_url}")
    records, pages = [], []
    for anchor in container.select("a.news-list__link[href]"):
        url = canonical(anchor["href"], page_url)
        if (same_origin(url, archive_url) and urlsplit(url).path.startswith("/documents/")
                and not re.fullmatch(r"/documents/page/\d+/?", urlsplit(url).path)):
            records.append(url)
    for anchor in soup.select("a.pagination__link[href]"):
        url = canonical(anchor["href"], page_url)
        if same_origin(url, archive_url) and re.fullmatch(r"/documents(?:/page/\d+)?/?", urlsplit(url).path):
            pages.append(url)
    return list(dict.fromkeys(records)), list(dict.fromkeys(pages))


def record(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one(".single-page__title")
    content = soup.select_one(".single-page__content")
    if title is None or content is None:
        raise ValueError(f"Record structure is missing: {page_url}")
    date = title.parent.select_one("time")
    raw_title = title.get_text(" ", strip=True)
    metadata = {"url": page_url, "title_raw": raw_title,
                "title": " ".join(re.sub(r"[\x00-\x1f]", " ", raw_title).split()),
                "date_raw": date.get_text(" ", strip=True) if date else None,
                "description": content.get_text(" ", strip=True),
                "admission_reason": "Document linked by the configured educational archive."}
    attachment_list = content.find_next_sibling("ul", class_="ul_hidden-default-styles")
    anchors = list(attachment_list.select("a[href]")) if attachment_list else []
    for anchor in content.select("a[href]"):
        if PurePosixPath(unquote(urlsplit(anchor["href"]).path)).suffix.lower() in DOCUMENT_EXTENSIONS:
            anchors.append(anchor)
    assets = {}
    for anchor in anchors:
        url = canonical(anchor["href"], page_url)
        extension = PurePosixPath(unquote(urlsplit(url).path)).suffix.lower()
        unsupported = None
        if not same_origin(url, page_url):
            unsupported = "Attachment is outside the configured source origin."
        elif extension and extension not in DOCUMENT_EXTENSIONS:
            unsupported = f"Unsupported attachment format: {extension}; package expansion is not implemented."
        assets[url] = {"url": url, "label": anchor.get_text(" ", strip=True),
                       "extension": extension, "unsupported_reason": unsupported}
    metadata["attachments"] = [{"url": asset["url"], "label": asset["label"]} for asset in assets.values()]
    return metadata, list(assets.values())
