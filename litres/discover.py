"""Discover likely Tatar Litres books from broad search pages and write a reviewable candidate index."""

import json
import os
import re
import time
from urllib.parse import urlencode

import bs4 as bs
import requests

from consts import domain
from index import (
    _content_type_from_book_page_html,
    _parse_books,
    _raise_if_blocked,
    _set_full_name,
)
from utils import create_driver, dump_json_atomic, get_hash, get_in_workdir, get_sid, read_config

CANDIDATES_INDEX = "../__artifacts/litres/candidates-index.json"
BOOKS_INDEX = "../__artifacts/litres/books-index.json"
MAX_PAGES_PER_QUERY_CAP = 20
DEFAULT_SEARCH_FILTERS = {
    "art_types": "text_book",
    "only_litres_subscription_arts": "true",
    "languages": ("ru", "en", "ba"),
}
TATAR_LETTERS = set("әөүҗңһӘӨҮҖҢҺ")
EXPLICIT_TATAR_PHRASES = (
    "на татарском",
    "на татарском языке",
    "татарском языке",
    "татар телендә",
    "татарча",
)
TATAR_WORDS = (
    "татар",
    "татарский",
    "татарская",
    "татарское",
    "татарском",
    "татарча",
    "телендә",
    "әдәбият",
    "шигырь",
    "хикәя",
    "җыр",
)


def discover_candidates():
    """
    Discover likely Tatar books outside the strict Litres language filter.

    Results are written to candidates-index.json for review; this command does not mutate books-index.json.
    """
    config = _discover_config()
    books = _load_json(get_in_workdir(BOOKS_INDEX))
    candidates_path = get_in_workdir(CANDIDATES_INDEX)
    candidates = _load_json(candidates_path)
    known_authors = _known_authors(books)
    existing_urls = {book.get("url") for book in books.values() if book.get("url")}
    driver = None

    def _get_driver():
        nonlocal driver
        if driver is None:
            driver = create_driver(headless=config["browser_headless"])
        return driver

    try:
        discovered = 0
        added = 0
        updated = 0
        skipped_low_score = 0
        headers = _headers()
        for query in config["search_queries"]:
            for page in range(1, config["max_pages_per_query"] + 1):
                url = _search_url(query, page)
                print(f"Processing search page: {url}")
                html = _fetch_search_page_html(
                    url,
                    headers,
                    _get_driver,
                    retries=config["search_request_retries"],
                )
                parsed_books = _parse_search_books(html)
                if not parsed_books:
                    print(f"No book cards found for query={query!r}, page={page}; stopping query")
                    break

                page_kept = 0
                for parsed in parsed_books:
                    discovered += 1
                    details = _enrich_candidate(parsed, headers)
                    score, signals = _score_candidate(details, query, known_authors)
                    if score < config["min_score"]:
                        skipped_low_score += 1
                        continue
                    key = get_hash(details["url"])
                    existing = candidates.get(key, {})
                    status = existing.get("status", "candidate")
                    details.update(
                        {
                            "score": score,
                            "signals": signals,
                            "status": status,
                            "already_indexed": details["url"] in existing_urls,
                        }
                    )
                    details["sources"] = _merge_sources(
                        existing.get("sources"),
                        {"type": "search", "query": query, "page": page, "url": url},
                    )
                    if key in candidates:
                        updated += 1
                    else:
                        added += 1
                    candidates[key] = details
                    page_kept += 1
                print(f"Page {page}: found {len(parsed_books)} book card(s), kept {page_kept}")
    finally:
        if driver:
            driver.quit()

    os.makedirs(os.path.dirname(candidates_path), exist_ok=True)
    dump_json_atomic(candidates, candidates_path)
    print(f"Discovered {discovered} book card(s), added {added}, updated {updated}")
    print(f"Skipped {skipped_low_score} low-score candidate(s)")
    print(f"Candidate index contains {len(candidates)} books")


def _discover_config():
    config = read_config()
    discover = _required_config_section(config, "discover")
    search_queries = _required_config_value(discover, "discover.search_queries")
    if not isinstance(search_queries, list) or not search_queries:
        raise ValueError("discover.search_queries must be a non-empty list")
    max_pages_per_query = int(_required_config_value(discover, "discover.max_pages_per_query"))
    return {
        "search_queries": search_queries,
        "max_pages_per_query": min(max_pages_per_query, MAX_PAGES_PER_QUERY_CAP),
        "min_score": int(_required_config_value(discover, "discover.min_score")),
        "browser_headless": _config_bool(
            _required_config_value(discover, "discover.browser_headless")
        ),
        "search_request_retries": int(
            _required_config_value(discover, "discover.search_request_retries")
        ),
    }


def _load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _required_config_section(config, name):
    if not isinstance(config, dict):
        raise ValueError("litres/config.yaml is empty or invalid")
    section = config.get(name)
    if not isinstance(section, dict):
        raise ValueError(f"{name} is not set in litres/config.yaml")
    return section


def _required_config_value(config, name):
    key = name.rsplit(".", 1)[-1]
    value = config.get(key)
    if value is None or value == "":
        raise ValueError(f"{name} is not set in litres/config.yaml")
    return value


def _headers():
    return {
        "Cookie": f"SID={get_sid()};",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    }


def _search_url(query, page):
    params = [
        ("q", query),
        ("art_types", DEFAULT_SEARCH_FILTERS["art_types"]),
        ("only_litres_subscription_arts", DEFAULT_SEARCH_FILTERS["only_litres_subscription_arts"]),
    ]
    params.extend(("languages", language) for language in DEFAULT_SEARCH_FILTERS["languages"])
    if page > 1:
        params.append(("page", str(page)))
    return f"{domain}/search/?{urlencode(params)}"


def _fetch_search_page_html(url, headers, driver_provider=None, retries=None):
    if retries is None:
        raise ValueError("discover.search_request_retries is not set in litres/config.yaml")
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, headers=headers, timeout=30) as response:
                response.raise_for_status()
                _raise_if_blocked(response.text, url)
                return response.text
        except (requests.HTTPError, RuntimeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(attempt)
                continue

    if not driver_provider:
        raise last_error
    print(f"Litres rejected direct search request; loading in browser: {url}")
    driver = driver_provider()
    driver.get(url)
    return driver.page_source


def _parse_search_books(html):
    soup = bs.BeautifulSoup(html, "html.parser")
    books = _parse_books(soup)
    if books:
        return books
    return _parse_next_data_search_books(soup)


def _parse_next_data_search_books(soup):
    script = soup.select_one("script#__NEXT_DATA__")
    if not script or not script.string:
        return []
    try:
        next_data = json.loads(script.string)
        initial_state = next_data["props"]["pageProps"]["initialState"]
        state = json.loads(initial_state) if isinstance(initial_state, str) else initial_state
    except (KeyError, TypeError, json.JSONDecodeError):
        return []

    books = {}
    queries = state.get("rtkqApi", {}).get("queries", {})
    for key, value in queries.items():
        if not key.startswith("getSearchData"):
            continue
        for item in (value.get("data") or {}).get("data") or []:
            if details := _details_from_search_item(item):
                books[details["url"]] = details
    return list(books.values())


def _details_from_search_item(item):
    instance = item.get("instance") or {}
    if item.get("type") != "text_book":
        return None
    if not instance.get("url") or not instance.get("title"):
        return None
    details = {
        "title": _normalize_text(instance["title"]),
        "url": _normalize_book_url(instance["url"]),
        "subscription": bool(instance.get("is_available_with_litres_subscription")),
        "content_type": _content_type_from_art_type(instance.get("art_type")),
    }
    if author := _author_from_search_item(instance):
        details["author"] = author
    if subtitle := _normalize_text(instance.get("subtitle") or ""):
        details["summary"] = subtitle
    if language_code := instance.get("language_code"):
        details["litres_language"] = language_code
    _set_full_name(details)
    return details


def _normalize_book_url(href):
    return f"{domain}{href}" if href.startswith("/") else href


def _content_type_from_art_type(art_type):
    if str(art_type) == "4":
        return "pdf"
    if str(art_type) == "0":
        return "text"
    return None


def _author_from_search_item(instance):
    persons = instance.get("persons") or []
    author = next((person for person in persons if person.get("role") == "author"), None)
    person = author or (persons[0] if persons else None)
    if not person:
        return None
    return _normalize_text(person.get("full_name") or "")


def _known_authors(books):
    return {
        book.get("author")
        for book in books.values()
        if book.get("author") and book.get("content_type") in {"pdf", "text"}
    }


def _enrich_candidate(parsed, headers):
    details = dict(parsed)
    details.setdefault("subscription", True)
    try:
        with requests.get(details["url"], headers=headers, timeout=30) as response:
            response.raise_for_status()
            _raise_if_blocked(response.text, details["url"])
            html = response.text
    except requests.RequestException as exc:
        details["enrichment_error"] = str(exc)
        return details

    soup = bs.BeautifulSoup(html, "html.parser")
    if summary := _extract_summary(soup):
        details["summary"] = summary
    if not details.get("content_type"):
        try:
            details["content_type"] = _content_type_from_book_page_html(html, details["url"])
        except ValueError as exc:
            details["enrichment_error"] = str(exc)
    _set_full_name(details)
    return details


def _extract_summary(soup):
    selectors = (
        '[data-testid*="annotation" i]',
        '[class*="annotation" i]',
        '[class*="description" i]',
        '[itemprop="description"]',
    )
    for selector in selectors:
        if node := soup.select_one(selector):
            if text := _normalize_text(node.get_text(" ", strip=True)):
                return text
    if meta := soup.select_one('meta[name="description"], meta[property="og:description"]'):
        return _normalize_text(meta.get("content") or "")
    return None


def _score_candidate(details, query, known_authors):
    score = 0
    signals = []
    searchable = " ".join(
        str(details.get(key) or "")
        for key in ("title", "author", "summary", "full_name")
    )
    searchable_lower = searchable.lower()
    query_lower = query.lower()

    for phrase in EXPLICIT_TATAR_PHRASES:
        if phrase in searchable_lower:
            score += 70
            signals.append(f"explicit_phrase:{phrase}")
            break

    if any(letter in searchable for letter in TATAR_LETTERS):
        score += 60
        signals.append("tatar_letters")

    matched_words = sorted({word for word in TATAR_WORDS if word in searchable_lower})
    if matched_words:
        score += min(30, len(matched_words) * 10)
        signals.append(f"tatar_words:{','.join(matched_words)}")

    if details.get("author") in known_authors:
        score += 25
        signals.append("known_author")

    if any(phrase in query_lower for phrase in EXPLICIT_TATAR_PHRASES):
        score += 15
        signals.append(f"query:{query}")

    return score, signals


def _merge_sources(existing_sources, source):
    sources = list(existing_sources or [])
    if source not in sources:
        sources.append(source)
    return sources


def _normalize_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _config_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError("discover.browser_headless must be a boolean")
