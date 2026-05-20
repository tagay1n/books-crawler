"""Scrapes Litres catalog pages to build a JSON index of titles, authors, URLs, and content types, merging with any existing index."""

import json
import os.path
import re
from urllib.parse import parse_qs, urljoin, urlparse

import bs4 as bs
import requests

from consts import TOTAL_PAGES, entry_point, domain
from utils import create_driver, dump_json_atomic, get_sid, get_in_workdir, get_hash


BOOK_PATH_MARKERS = ("/book/", "/audiobook/")
BLOCKED_MARKERS = ("DDoS-Guard", "ddos-guard", "Checking your browser")
PDF_CONTENT_MARKERS = ("pdf", "пдф")
TEXT_CONTENT_MARKERS = (
    "text book",
    "textbook",
    "e-book",
    "ebook",
    "текстовая книга",
    "электронная книга",
)


def index():
    index_file_name = "books-index.json"
    index_dir = get_in_workdir("../__artifacts/litres")
    os.makedirs(index_dir, exist_ok=True)
    index_file = os.path.join(index_dir, index_file_name)
    if os.path.exists(index_file):
        with open(index_file, "r") as f:
            books = json.load(f)
    else:
        books = {}

    headers = {
        "Cookie": f"SID={get_sid()};",
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    }
    discovered = 0
    added = 0
    updated = 0
    reader_resolver = _ReaderContentTypeResolver()
    try:
        try:
            for i in range(1, TOTAL_PAGES + 1):
                paginated_url = f"{entry_point}&page={i}"
                print(f"Processing page: {paginated_url}")
                with requests.get(paginated_url, headers=headers) as r:
                    r.raise_for_status()
                    _raise_if_blocked(r.text, paginated_url)
                    soup = bs.BeautifulSoup(r.text, "html.parser")
                    cards = _parse_books(soup)
                    page_added = 0
                    page_updated = 0
                    for parsed in cards:
                        discovered += 1
                        h = get_hash(parsed["url"])
                        if h in books:
                            details = _merge_book_details(books[h], parsed, reader_resolver)
                            page_updated += 1
                            updated += 1
                        else:
                            details = _merge_book_details({}, parsed, reader_resolver)
                            page_added += 1
                            added += 1
                        books[h] = details
                    print(f"Page {i}: found {len(cards)} book card(s), added {page_added}, updated {page_updated}")
        except KeyboardInterrupt:
            dump_json_atomic(books, index_file)
            print(f"Interrupted; saved current index state to {index_file}")
            raise
    finally:
        reader_resolver.close()

    dump_json_atomic(books, index_file)

    print(f"Discovered {discovered} book card(s), added {added}, updated {updated}")
    print(f"Index contains {len(books)} books")


def _raise_if_blocked(html, url):
    if any(marker in html for marker in BLOCKED_MARKERS):
        raise RuntimeError(f"Litres returned anti-bot challenge page for {url}")


def _parse_books(soup):
    cards = _parse_legacy_cards(soup)
    if cards:
        return cards
    return _parse_link_cards(soup)


def _parse_legacy_cards(soup):
    books = []
    for book in soup.select('div[class^="ArtDefault_container"]'):
        cover = book.select_one('a[class^="ArtDefault_cover"]')
        title = book.select_one('p[class^="ArtInfo_title"]')
        if not cover or not title:
            continue
        details = {
            "title": _normalize_text(title.get_text()),
            "subscription": True,
            "url": _normalize_book_url(cover["href"]),
        }
        details["content_type"] = _detect_content_type_from_node(book, details["url"])
        if author := book.select_one('a[class^="ArtInfo_author"]'):
            details['author'] = _normalize_text(author.get_text())
        _set_full_name(details)
        books.append(details)
    return books


def _parse_link_cards(soup):
    books = {}
    for link in soup.select("a[href]"):
        href = link.get("href")
        if not _is_book_href(href):
            continue
        url = _normalize_book_url(href)
        title = _extract_title(link)
        if not title:
            continue
        details = {
            "title": title,
            "url": url,
            "subscription": True,
            "content_type": _detect_content_type(link, url),
        }
        if author := _extract_author(link):
            details["author"] = author
        _set_full_name(details)
        books[url] = details
    return list(books.values())


def _is_book_href(href):
    if not href:
        return False
    path = urlparse(href).path
    return any(marker in path for marker in BOOK_PATH_MARKERS)


def _normalize_book_url(href):
    url = urljoin(domain, href)
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _extract_title(link):
    title_node = link.select_one('[data-testid*="title" i], [class*="title" i], [class*="name" i]')
    title = title_node.get_text(" ", strip=True) if title_node else link.get_text(" ", strip=True)
    return _normalize_text(title)


def _extract_author(link):
    card = _find_card_root(link)
    if not card:
        return None
    author = card.select_one('a[href*="/author/"], [data-testid*="author" i], [class*="author" i]')
    if not author:
        return None
    return _normalize_text(author.get_text(" ", strip=True))


def _detect_content_type(link, url):
    card = _find_card_root(link)
    return _detect_content_type_from_node(card or link, url)


def _detect_content_type_from_node(node, url):
    search_text = _node_search_text(node)
    has_pdf_marker = any(marker in search_text for marker in PDF_CONTENT_MARKERS)
    has_text_marker = any(marker in search_text for marker in TEXT_CONTENT_MARKERS)
    if has_pdf_marker and has_text_marker:
        raise ValueError(f"Ambiguous Litres content type for {url}: found both PDF and text markers")
    if has_pdf_marker:
        return "pdf"
    if has_text_marker:
        return "text"
    return None


def _merge_book_details(existing, parsed, content_type_resolver=None):
    parsed = dict(parsed)
    parsed_type = parsed.get("content_type")
    should_verify_type = parsed_type in {None, "pdf"} or existing.get("content_type") == "pdf"
    resolved_type = content_type_resolver(parsed["url"]) if content_type_resolver and should_verify_type else None
    parsed_type = resolved_type or parsed.get("content_type")
    if parsed_type is None:
        parsed_type = _known_content_type(existing, parsed["url"])
    elif _has_pdf_artifacts(existing) and parsed_type != "pdf":
        raise ValueError(
            f"Litres content type conflict for {parsed['url']}: "
            f"existing index has PDF artifacts but catalog says {parsed_type}"
        )
    parsed["content_type"] = parsed_type
    existing.update(parsed)
    return existing


def _known_content_type(existing, url):
    if _has_pdf_artifacts(existing):
        return "pdf"
    raise ValueError(f"Could not determine Litres content type for {url}")


class _ReaderContentTypeResolver:
    def __init__(self):
        self._driver = None
        self._session = requests.Session()
        self._session.headers.update(_litres_headers())

    def __call__(self, url):
        print(f"Resolving Litres content type from reader: {url}")
        if content_type := _content_type_from_book_page(url, self._session):
            return content_type
        return _content_type_from_reader_url(_open_reader_url(url, self._get_driver()), url)

    def close(self):
        if self._driver:
            self._driver.quit()
            self._driver = None
        self._session.close()

    def _get_driver(self):
        if not self._driver:
            self._driver = create_driver()
        return self._driver


def _open_reader_url(url, driver):
    from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    driver.get(url)
    wait = WebDriverWait(driver, 20)
    for attempt in range(3):
        try:
            read_button = _find_read_button(wait)
            old_handles = set(driver.window_handles)
            driver.execute_script(
                """
                const target = arguments[0].closest('button,a,[role="button"]') || arguments[0];
                target.scrollIntoView({block: 'center'});
                target.click();
                """,
                read_button,
            )
            _wait_for_reader_navigation(driver, url, old_handles)
            break
        except StaleElementReferenceException:
            if attempt == 2:
                raise
        except TimeoutException:
            if attempt == 2:
                raise ValueError(f"Could not open Litres reader for {url}")
    return driver.current_url


def _find_read_button(wait):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC

    text_button_xpath = (
        "//*[contains(@class, 'Button_textContainer') and "
        "(contains(normalize-space(.), 'Читать') or contains(normalize-space(.), 'Read'))]"
    )
    return wait.until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                f"({text_button_xpath} | //a[contains(@href, '/reader/')] | //a[contains(@href, '/static/or3/view/or.html')])[1]",
            )
        )
    )


def _wait_for_reader_navigation(driver, initial_url, old_handles):
    from selenium.webdriver.support.ui import WebDriverWait

    def _reader_opened(current):
        new_handles = set(current.window_handles) - old_handles
        if new_handles:
            current.switch_to.window(next(iter(new_handles)))
            return True
        return current.current_url != initial_url

    WebDriverWait(driver, 10).until(_reader_opened)


def _content_type_from_reader_url(reader_url, book_url):
    queries = parse_qs(urlparse(reader_url).query)
    if queries.get("art_type") == ["4"]:
        return "pdf"
    if queries.get("file"):
        return "pdf"
    if queries.get("baseurl"):
        return "text"
    raise ValueError(f"Could not determine Litres content type for {book_url}; reader URL was {reader_url}")


def _content_type_from_book_page(url, session=None):
    request = session.get if session else requests.get
    kwargs = {"timeout": 30}
    if not session:
        kwargs["headers"] = _litres_headers()
    with request(url, **kwargs) as r:
        r.raise_for_status()
        _raise_if_blocked(r.text, url)
        return _content_type_from_book_page_html(r.text, url)


def _litres_headers():
    return {
        "Cookie": f"SID={get_sid()};",
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    }


def _content_type_from_book_page_html(html, url):
    book_id = _book_id_from_url(url)
    if not book_id:
        return None
    patterns = (
        rf'\\"id\\":{book_id}.*?\\"art_type\\":(\d+)',
        rf'"id":{book_id}.*?"art_type":(\d+)',
    )
    for pattern in patterns:
        if match := re.search(pattern, html):
            return _content_type_from_art_type(match.group(1), url)
    return None


def _book_id_from_url(url):
    match = re.search(r"-(\d+)/?$", urlparse(url).path)
    return match.group(1) if match else None


def _content_type_from_art_type(art_type, url):
    if str(art_type) == "4":
        return "pdf"
    if str(art_type) == "0":
        return "text"
    raise ValueError(f"Unsupported Litres art_type={art_type} for {url}")


def _has_pdf_artifacts(details):
    return bool(
        details.get("file_id")
        or details.get("ext")
        or details.get("pdf_file")
    )


def _node_search_text(node):
    values = [node.get_text(" ", strip=True)]
    for element in [node, *node.find_all(True)]:
        for value in element.attrs.values():
            if isinstance(value, list):
                values.extend(str(item) for item in value)
            else:
                values.append(str(value))
    return _normalize_text(" ".join(values)).lower()


def _find_card_root(link):
    current = link
    for _ in range(8):
        if not current:
            return None
        if current.name in {"article", "li"}:
            return current
        classes = " ".join(current.get("class", []))
        test_id = current.get("data-testid", "")
        if "card" in classes.lower() or "book" in classes.lower() or "card" in test_id.lower():
            return current
        current = current.parent
    return link.parent


def _normalize_text(value):
    return " ".join(value.split()).strip()


def _set_full_name(details):
    _title = details['title'].replace("/", "|").strip()
    _author = (details.get('author') or "").strip()
    details['full_name'] = (f"{_title} - {_author}" if _author else _title)[:133]
