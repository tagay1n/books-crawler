"""Native OJS full-issue PDFs explicitly labelled Tatar by Fänni Tatarstan."""
from .runtime_config import option as operational_option

import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .documents import canonical, same_origin
from .network import InvalidDocument, install_native_get_guard
from .paging import ListingPage, PageRequest


PARSER_VERSION = 2
ISSUE = re.compile(r"view/([1-9]\d*)")
GALLEY = re.compile(r"(?:view|download)/([1-9]\d*)/([1-9]\d*)(?:/[1-9]\d*)?")


def native_url(href, base=None):
    if base is None:
        base = operational_option('ftatarstan', 'archive_url')
    url = canonical(href.strip(), base).rstrip("/")
    parsed = urlsplit(url)
    if (not same_origin(url, operational_option('ftatarstan', 'base')) or parsed.query or not url.startswith(operational_option('ftatarstan', 'base'))
            or not re.fullmatch(r"archive(?:/[1-9]\d*)?|view/[1-9]\d*|(?:view|download)/[1-9]\d*/[1-9]\d*(?:/[1-9]\d*)?", url[len(operational_option('ftatarstan', 'base')):])):
        raise ValueError("Only native journal archive, issue and PDF-galley routes are supported.")
    return url


def galley_identity(url):
    match = GALLEY.fullmatch(native_url(url)[len(operational_option('ftatarstan', 'base')):])
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
    if not re.fullmatch(r"archive(?:/[1-9]\d*)?", url[len(operational_option('ftatarstan', 'base')):]):
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
        if ISSUE.fullmatch(target[len(operational_option('ftatarstan', 'base')):]) is None:
            raise ValueError("Archive card does not identify a native issue.")
        cover = card.select_one("img[src]")
        description = card.select_one(".description")
        entries[target] = {"catalog_url": url, "title_raw": anchor.get_text(" ", strip=True),
                           "cover_url": canonical(cover["src"], url) if cover else None,
                           "description_raw": description.get_text(" ", strip=True) if description else None,
                           "href_raw": anchor["href"]}
    if not entries:
        raise ValueError("Archive page contains no recognizable issues.")
    page = int(url.rsplit("/", 1)[1]) if url != operational_option('ftatarstan', 'archive_url') else 1
    following = {}
    for anchor in area.select(".cmp_pagination a[href]"):
        target = native_url(anchor["href"], url)
        match = re.fullmatch(r"archive/([1-9]\d*)", target[len(operational_option('ftatarstan', 'base')):])
        if match is None and target != operational_option('ftatarstan', 'archive_url'):
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
    identity = ISSUE.fullmatch(url[len(operational_option('ftatarstan', 'base')):])
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
    metadata = {"url": url, "issue_id": identity[1], "title": title, "title_raw": title,
            "publication_date_raw": date.get_text(" ", strip=True) if date else None,
            "doi_raw": doi.get_text(" ", strip=True) if doi else None,
            "representation": "full_issue_pdf" if assets else "issue_metadata_only",
            "article_count_claim": len(area.select(".obj_article_summary")),
            "admission_reason": "Only full-issue galleys explicitly labelled Tatar are acquired; article PDFs and covers are excluded."}
    cover = area.select_one(".heading .cover img[src]")
    if cover is not None:
        metadata["cover_url"] = canonical(cover["src"], url)
    description = area.select_one(":scope > .description, :scope > .heading .description")
    if description is not None:
        metadata["description_raw"] = description.get_text(" ", strip=True)
        metadata["description_html"] = description.decode_contents()
    metadata["contents"] = []
    for article in area.select(".obj_article_summary"):
        anchor = article.select_one(".title a[href]")
        if anchor is None:
            continue
        section = article.find_parent("div", class_="section")
        heading = section.select_one(":scope > h2, :scope > h3") if section else None
        authors, pages = article.select_one(".authors"), article.select_one(".pages")
        metadata["contents"].append({
            "title_raw": anchor.get_text(" ", strip=True), "href_raw": anchor["href"],
            "url": canonical(anchor["href"], url), "native_id_raw": anchor.get("id"),
            "section_raw": heading.get_text(" ", strip=True) if heading else None,
            "authors_raw": authors.get_text(" ", strip=True) if authors else None,
            "pages_raw": pages.get_text(" ", strip=True) if pages else None,
            "galleys": [{"url": canonical(a["href"], url), "label_raw": a.get_text(" ", strip=True)}
                        for a in article.select(".galleys_links a[href]")],
        })
    metadata["attachments"] = [dict(asset) for asset in assets.values()]
    metadata["acquisition_note"] = (
        "Full-issue galley candidates; only explicit Tatar labels permit acquisition."
        if assets else "Metadata only: no full-issue PDF galley exposed."
    )
    return metadata, list(assets.values())


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
            if not target.startswith(operational_option('ftatarstan', 'base') + "download/") or galley_identity(target) != galley_identity(asset["galley_view_url"]):
                raise ValueError("Native viewer download link changed its issue or galley identity.")
            targets[target] = anchor["href"]
        if len(targets) != 1:
            raise ValueError("Native PDF viewer must advertise one unique original download.")
        asset["url"], asset["download_href_raw"] = next(iter(targets.items()))
    metadata["attachments"] = [dict(asset) for asset in assets]
    return metadata, assets


def download(http, manifest, summary, log, recheck, *, selected_records=None):
    from .core import download as originals
    originals(http, manifest, summary, log, recheck, extensions={".pdf"})
