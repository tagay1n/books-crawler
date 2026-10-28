"""Original PDFs of DUM RT's two contemporary Tatar publication series."""

from pathlib import PurePosixPath
import re
from urllib.parse import parse_qs, unquote, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from requests.utils import requote_uri

from .documents import canonical, same_origin
from .network import install_native_get_guard
from .paging import ListingPage, PageRequest


ORIGIN = "https://dumrt.ru"
ARCHIVE_URL = ORIGIN + "/media/din-va-magishet/"
PARSER_VERSION = 2
SERIES = {
    "/media/din-va-magishet/": {"id": "din_va_magishet", "title": "Дин вә мәгыйшәт", "heading": "Дин вә мәгыйшәт", "component": "751", "step": 6},
    "/media/shura-almanah/": {"id": "shura_modern", "title": "Шура", "heading": '"Шура" альманахы', "component": "757", "step": 10},
}
LANGUAGE_EVIDENCE_URL = ORIGIN + "/netcat_files/multifile/2627/otchet_DUM_2018.pdf"


def native_url(href, base=ARCHIVE_URL):
    url = requote_uri(canonical(href, base))
    p = urlsplit(url)
    path = unquote(p.path)
    if (not same_origin(url, ORIGIN) or "\\" in path
            or {".", ".."}.intersection(path.split("/"))
            or any(ord(c) < 32 or ord(c) == 127 for c in path)):
        raise ValueError("Publisher resources must remain on safe native HTTPS paths.")
    if p.path in SERIES:
        query = parse_qs(p.query, keep_blank_values=True)
        if not query:
            return urlunsplit((p.scheme, p.netloc, p.path, "", ""))
        series = SERIES[p.path]
        if (set(query) != {"curPos", "cur_cc"} or any(len(v) != 1 for v in query.values())
                or query["cur_cc"] != [series["component"]]
                or not re.fullmatch(r"0|[1-9]\d*", query["curPos"][0])
                or int(query["curPos"][0]) % series["step"]):
            raise ValueError("Unexpected publisher series pagination.")
        params = urlencode({"curPos": int(query["curPos"][0]), "cur_cc": series["component"]}) if int(query["curPos"][0]) else ""
        return urlunsplit((p.scheme, p.netloc, p.path, params, ""))
    if p.query:
        raise ValueError("Publisher issue and original PDF URLs must not have queries.")
    if any(re.fullmatch(re.escape(root) + r"[a-z0-9_-]+_[1-9]\d*\.html", p.path) for root in SERIES):
        return url
    if re.fullmatch(r"/netcat_files/(?:[1-9]\d*/[1-9]\d*|multifile/[1-9]\d*)/.+\.pdf", path, re.I):
        return url
    if re.fullmatch(r"/(?:files/)?pdf/.+\.pdf", path, re.I):
        return url
    raise ValueError("Expected a configured series archive, issue or native PDF attachment.")


def pdf_link(raw, base):
    """Repair only the observed dangling quote in legacy /files/pdf links."""
    parsed = urlsplit(canonical(raw, base))
    path = unquote(parsed.path)
    repair = None
    if re.fullmatch(r"/files/pdf/.+\.pdf[\"']", path, re.I) and not parsed.query and not parsed.fragment:
        cleaned = re.sub(r"(?:[\"']|%22|%27)$", "", parsed.path, flags=re.I)
        raw_target = urlunsplit((parsed.scheme, parsed.netloc, cleaned, "", ""))
        repair = {"operation": "remove_dangling_quote", "advertised_href_raw": raw}
    else:
        raw_target = raw
    if PurePosixPath(unquote(urlsplit(raw_target).path)).suffix.lower() != ".pdf":
        return None, None
    return native_url(raw_target, base), repair


def series_for(url):
    path = urlsplit(native_url(url)).path
    for root, series in SERIES.items():
        if path.startswith(root):
            return root, series
    raise ValueError("Expected a configured publication series URL.")


def prepare_http(http, session_file):
    install_native_get_guard(http, native_url, "DUM RT publications")


def parse_listing(html, request, root):
    url = native_url(request.url)
    path, series = series_for(url)
    if urlsplit(url).path != path:
        raise ValueError("Expected a publisher series listing.")
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("#main-content")
    heading = main.select_one("h1") if main else None
    area = main.select_one(".jornal") if main else None
    if heading is None or heading.get_text(" ", strip=True) != series["heading"] or area is None:
        raise ValueError("Publisher series heading or native issue list is missing.")
    entries = {}
    for card in area.select(".jornal-item"):
        anchor = card.select_one("h3 a[href]")
        if anchor is None or not anchor.get_text(strip=True):
            raise ValueError("Issue card is missing its native title link.")
        target = native_url(anchor["href"], url)
        if series_for(target)[0] != path or not urlsplit(target).path.endswith(".html"):
            raise ValueError("Issue card changed its selected publication series.")
        date = card.select_one(".date")
        entries[target] = {"catalog_url": url, "series": series["id"],
                           "title_raw": anchor.get_text(" ", strip=True), "href_raw": anchor["href"],
                           "posted_date_raw": date.get_text(" ", strip=True) if date else None}
    if not entries:
        raise ValueError("Publisher series page has no recognizable issue cards.")
    offset = int(parse_qs(urlsplit(url).query).get("curPos", ["0"])[0])
    following = {}
    later_page_advertised = False
    for anchor in main.select(".pagination a[href]"):
        target = native_url(anchor["href"], url)
        if urlsplit(target).path != path:
            raise ValueError("Publisher pager changed publication series.")
        next_offset = int(parse_qs(urlsplit(target).query).get("curPos", ["0"])[0])
        later_page_advertised |= next_offset > offset
        if next_offset == offset + series["step"]:
            following[target] = PageRequest(target)
    if later_page_advertised and not following:
        raise ValueError("Publisher pager skips its next native page.")
    if url == ARCHIVE_URL:
        for other in SERIES:
            if other != path:
                following[ORIGIN + other] = PageRequest(ORIGIN + other)
    return ListingPage(list(entries), list(following.values()), record_context=entries,
                       detect_repeats=True)


def record(html, page_url):
    url = native_url(page_url)
    root, series = series_for(url)
    match = re.fullmatch(re.escape(root) + r"[a-z0-9_-]+_([1-9]\d*)\.html", urlsplit(url).path)
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("#main-content")
    heading = main.select_one("h1") if main else None
    area = main.select_one(".jornal_detail") if main else None
    canonical_claim = soup.select_one('meta[property="og:url"][content]')
    if (match is None or heading is None or area is None
            or (canonical_claim is not None and native_url(canonical_claim["content"], url) != url)):
        raise ValueError("Native issue identity, title or attachment area is missing.")
    title = heading.get_text(" ", strip=True)
    if not title:
        raise ValueError("Publication title is empty.")
    # Older cards use quoted titles or the original launch announcement. The
    # native series path, canonical claim when provided and issue layout establish
    # identity; publisher evidence establishes series language independently.
    date = area.select_one(".date")
    description = area.select_one("article")
    assets = {}
    for container in area.select(".file"):
        links = [(a["href"], a.get_text(" ", strip=True)) for a in container.select("a[href]")]
        links += [(o["data"], "Embedded original PDF") for o in container.select('object[type="application/pdf"][data]')]
        for raw, label in links:
            target, repair = pdf_link(raw, url)
            if target is None:
                continue
            if not urlsplit(target).path.startswith(("/netcat_files/", "/files/pdf/", "/pdf/")):
                raise ValueError("Issue PDF is outside the selected original-file storage.")
            assets.setdefault(target, {"url": target, "label": title, "extension": ".pdf",
                                       "source_asset_key": "original:" + target, "href_raw": raw,
                                       "link_label_raw": label, "source_url_repair": repair,
                                       "language_admission": "publisher_tatar_series"})
    return {"url": url, "native_url_claim": canonical_claim["content"] if canonical_claim else None,
            "publication_id": match[1], "series": series["id"],
            "series_title": series["title"], "title": title,
            "posted_date_raw": date.get_text(" ", strip=True) if date else None,
            "description_raw": description.get_text(" ", strip=True) if description else None,
            "language_evidence": {"language": "tt", "scope": "publication_series",
                                  "source_url": LANGUAGE_EVIDENCE_URL,
                                  "claim": "Publisher activity report identifies these two series as Tatar-language publications."},
            "admission_reason": "Selected contemporary Tatar publication series; individual language composition and edition completeness remain unverified."}, list(assets.values())


def record_key(metadata):
    return metadata["series"] + ":" + metadata["publication_id"]


def download(http, manifest, summary, log, recheck):
    from .core import download as originals
    originals(http, manifest, summary, log, recheck, extensions={".pdf"})
