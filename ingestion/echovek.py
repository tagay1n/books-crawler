"""Tatar-labelled article PDFs discovered through Echo of Centuries issues."""
from .runtime_config import option as operational_option

import json
from pathlib import PurePosixPath
import re
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from requests.utils import requote_uri

from .network import InvalidDocument, install_native_get_guard
from .paging import ListingPage, PageRequest


PARSER_VERSION = 2

ISSUE_PATH = re.compile(r"/ru/publication/[a-z0-9-]+")
ARTICLE_PATH = re.compile(r"/(?:ru/article/[a-z0-9-]+|(?:ru|tt)/node/[1-9]\d*)")


def native_url(href, base=None):
    if base is None:
        base = operational_option('echovek', 'archive_url')
    parsed = urlsplit(urljoin(base, href))
    path = unquote(parsed.path)
    if (parsed.scheme not in {"http", "https"} or parsed.netloc not in operational_option('echovek', 'hosts')
            or "\\" in path or {".", ".."}.intersection(path.split("/"))
            or any(ord(c) < 32 for c in path)):
        raise ValueError("Echo of Centuries URL is outside the native source or has an unsafe path.")
    query = ""
    if path == "/ru/publications":
        params = parse_qs(parsed.query, keep_blank_values=True)
        if params:
            if (set(params) != {"page"} or len(params["page"]) != 1
                    or not re.fullmatch(r"0|[1-9]\d*", params["page"][0])):
                raise ValueError("Unexpected Echo of Centuries archive query.")
            if int(params["page"][0]):
                query = "page=" + params["page"][0]
    elif parsed.query or not (ISSUE_PATH.fullmatch(path) or ARTICLE_PATH.fullmatch(path)
                              or (path.startswith("/sites/default/files/statya/")
                                  and PurePosixPath(path).suffix.lower() == ".pdf")):
        raise ValueError("Expected a journal archive, issue, article, or original article PDF URL.")
    return requote_uri(urlunsplit(("https", "www.echovek.ru", path, query, "")))


def article_url(href, base):
    url = native_url(href, base)
    if not ARTICLE_PATH.fullmatch(urlsplit(url).path):
        raise ValueError("Expected a native article record URL.")
    return url


def prepare_http(http, session_file):
    def https_native_url(href, base=None):
        url = urljoin(base or operational_option('echovek', 'archive_url'), href)
        if urlsplit(url).scheme != "https":
            raise ValueError("Echo of Centuries permits HTTPS requests only.")
        return native_url(url)

    install_native_get_guard(http, https_native_url, "Echo of Centuries")

    def validate_download(response, asset):
        if any(native_url(hop.url) != asset["url"] for hop in [*response.history, response]):
            raise InvalidDocument("Article download belongs to a different source resource.")

    http.validate_download_response = validate_download


def parse_listing(html, request, root):
    url = native_url(request.url)
    parsed = urlsplit(url)
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("#main-content h1")
    if heading is None or not heading.get_text(strip=True):
        raise ValueError("Echo of Centuries listing heading is missing.")
    title = heading.get_text(" ", strip=True)
    if parsed.path == "/ru/publications":
        area = soup.select_one(".view-id-izdaniya_page")
        if title != "Издания" or area is None:
            raise ValueError("Echo of Centuries issue archive structure is missing.")
        issues = {}
        for anchor in area.select(".view-content .views-row .izd_title a[href]"):
            target = native_url(anchor["href"], url)
            if not ISSUE_PATH.fullmatch(urlsplit(target).path):
                raise ValueError("Unexpected journal issue identity.")
            issues[target] = PageRequest(target)
        if not issues:
            raise ValueError("Issue archive has no recognizable issue links.")
        current = int(parse_qs(parsed.query).get("page", ["0"])[0])
        next_pages = {}
        for anchor in area.select("ul.pager a[href]"):
            target = native_url(anchor["href"], url)
            if urlsplit(target).path != "/ru/publications":
                raise ValueError("Issue archive pager points outside its listing.")
            number = int(parse_qs(urlsplit(target).query).get("page", ["0"])[0])
            if number == current + 1:
                next_pages[target] = PageRequest(target)
        if area.select_one(".pager-next") and not next_pages:
            raise ValueError("Issue archive pager does not advance by one page.")
        return ListingPage([], [*issues.values(), *next_pages.values()],
                           fingerprint=json.dumps(list(issues)), detect_repeats=True)
    if not ISSUE_PATH.fullmatch(parsed.path):
        raise ValueError("Expected an issue archive or issue contents page.")
    area = soup.select_one(".izd_soderganie")
    if area is None:
        raise ValueError("Issue contents structure is missing.")
    if not title.startswith("Гасырлар авазы"):
        classes = soup.body.get("class", []) if soup.body else []
        if "node-type-vitrina-izdanie" not in classes:
            raise ValueError("Unrecognized non-journal publication layout.")
        # The archive also lists publisher books. Retain them without treating
        # their contents as journal articles or stopping later archive pages.
        return ListingPage([url], [])
    if area.select_one("ul.pager a[href]"):
        raise ValueError("Issue contents acquired pagination; traversal needs review.")
    entries, unresolved = {}, []
    for card in area.select(".statya_izd"):
        anchor = card.select_one(".st_title a[href]")
        if anchor is None:
            raise ValueError("Issue article card is missing its title link.")
        if urlsplit(urljoin(url, anchor["href"])).path == "/ru/node/":
            unresolved.append({"title_raw": anchor.get_text(" ", strip=True),
                               "href_raw": anchor["href"],
                               "reason": "Native article link is missing its node identifier."})
            continue
        target = article_url(anchor["href"], url)
        entries[target] = {"issue_url": url, "issue_title_raw": title,
                           "article_title_raw": anchor.get_text(" ", strip=True)}
        summary = card.select_one(".st_kr")
        if summary is not None:
            entries[target]["description_raw"] = summary.get_text(" ", strip=True)
            entries[target]["description_html"] = summary.decode_contents()
    if not entries:
        raise ValueError("Issue contents contain no recognizable article records.")
    for context in entries.values():
        context["unresolved_article_cards"] = unresolved
    return ListingPage(list(entries), [], record_context=entries)


def upstream_metadata(soup, url, field_selector, description_selector):
    """Retain publisher field labels/links without inferring bibliography."""
    result = {"fields_raw": [], "page_metadata": [
        {"name": tag.get("property") or tag.get("name"), "content": tag["content"]}
        for tag in soup.select("meta[content]")
        if (tag.get("property") or tag.get("name") or "").startswith((
            "og:", "article:", "description", "author", "keywords"))
    ]}
    for node in soup.select(field_selector):
        content = node.select_one(".field-content")
        if content is None:
            continue
        label = node.select_one(".views-label")
        result["fields_raw"].append({
            "classes": node.get("class", []),
            "label": label.get_text(" ", strip=True) if label else None,
            "text": content.get_text(" ", strip=True), "html": content.decode_contents(),
        })
    description = soup.select_one(description_selector)
    if description is not None:
        result["description_raw"] = description.get_text(" ", strip=True)
        result["description_html"] = description.decode_contents()
    cover = soup.select_one(".pane-views-statya-vitrina-oblogka-block img[src], .pane-views-izdanie-vitrina-obl-block-block img[src]")
    if cover is not None:
        result["cover_url"] = urljoin(url, cover["src"])
    return result


def record(html, page_url):
    url = native_url(page_url, operational_option('echovek', 'archive_url'))
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("#main-content h1")
    fields = soup.select_one(".pane-views-statya-vitrina-har-block")
    classes = soup.body.get("class", []) if soup.body else []
    ids = [re.fullmatch(r"page-node-([1-9]\d*)", c) for c in classes]
    ids = [m[1] for m in ids if m]
    if ISSUE_PATH.fullmatch(urlsplit(url).path):
        if (heading is None or not heading.get_text(strip=True) or len(ids) != 1
                or "node-type-vitrina-izdanie" not in classes
                or heading.get_text(" ", strip=True).startswith("Гасырлар авазы")):
            raise ValueError("Non-journal publication identity or title is missing.")
        language = soup.select_one(".views-field-field-izdanie-language .field-content")
        return {**upstream_metadata(soup, url,
                                   '#main-content .views-field[class*="views-field-field-izdanie-"], .pane-views-izdanie-vitr-title-block .views-field',
                                   '.izd_minianons'),
                "url": url, "publication_id": ids[0],
                "title": heading.get_text(" ", strip=True),
                "language_raw": language.get_text(" ", strip=True) if language else None,
                "representation": "non_journal_metadata",
                "admission_reason": "Publisher book retained as metadata; acquisition is limited to journal article PDFs."}, []
    article_url(url, operational_option('echovek', 'archive_url'))
    if (heading is None or not heading.get_text(strip=True) or fields is None
            or len(ids) != 1 or "node-type-vitrina" not in classes):
        raise ValueError("Article identity, title or bibliographic fields are missing.")

    def field(name):
        node = fields.select_one(f".views-field-field-statya-{name} .field-content")
        return node.get_text(" ", strip=True) if node else ""

    title, language_raw = heading.get_text(" ", strip=True), field("language")
    languages = [v.strip().casefold() for v in re.split(r"[,;/]|\s+и\s+", language_raw, flags=re.I) if v.strip()]
    selected = "татарский" in languages
    known = {"русский", "английский", "немецкий", "французский", "крымскотатарский"}
    selection = "selected" if selected else "excluded" if languages and set(languages) <= known else "unknown"
    assets = {}
    for anchor in soup.select(".statya_sale .pdf_file a.izd_link_w_icon[href]"):
        raw = anchor["href"]
        target = requote_uri(urljoin(url, raw))
        reason = None
        try:
            target = native_url(target)
            if not urlsplit(target).path.startswith("/sites/default/files/statya/"):
                raise ValueError("Not an article PDF.")
        except ValueError:
            reason = "Attachment is outside the native article-PDF paths."
        if reason is None and not selected:
            reason = ("Article language is explicitly non-Tatar." if selection == "excluded" else
                      "Missing or unrecognized article-language field; Tatar content is not established.")
        assets.setdefault(target, {"url": target, "label": title, "extension": ".pdf",
                                   "href_raw": raw, "link_label_raw": anchor.get_text(" ", strip=True),
                                   "unsupported_reason": reason})
    metadata = {**upstream_metadata(soup, url, '.pane-views-statya-vitrina-har-block .views-field', '.statya_page_anons'),
                "url": url, "article_id": ids[0], "title": title, "title_raw": title,
                "authors_raw": field("author"), "rubric_raw": field("rubrik"),
                "article_type_raw": field("type"), "publication_date_raw": field("date-public"),
                "language_raw": language_raw, "language_selection": selection,
                "language_evidence": {"field": "field-statya-language", "value_raw": language_raw},
                "representation": "article_pdf" if assets else "html_or_gated_metadata",
                "admission_reason": "Explicit native article-language field must identify Tatar; issue previews and full-issue files are outside this slice.",
                "attachments": [{"url": a["url"], "label": a["label"]} for a in assets.values()]}
    return metadata, list(assets.values())


def record_key(metadata):
    if "publication_id" in metadata:
        return "publication:" + metadata["publication_id"]
    return "article:" + metadata["article_id"]
