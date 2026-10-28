"""Exact-series KFU Vakyt search, with explicit item-language admission."""

import json
import re
from urllib.parse import parse_qs, urlencode, urlsplit

from bs4 import BeautifulSoup

from . import kfu
from .documents import canonical, same_origin
from .paging import CatalogChanged, ListingPage, PageRequest


ARCHIVE_URL = kfu.ORIGIN + "/jspui/handle/net/86/simple-search"
PARSER_VERSION = 1
UNIQUE_RECORDS = True
PARAMETERS = {"query": "", "filter_field_1": "is_part_of_series",
              "filter_type_1": "equals", "filter_value_1": "Вакыт",
              "sort_by": "score", "order": "desc", "rpp": "10", "etal": "0"}
record_key = kfu.record_key
resolve_record = kfu.resolve_record


def search_url(start=0):
    return ARCHIVE_URL + "?" + urlencode({**PARAMETERS, "start": str(start)})


def position(url):
    parsed = urlsplit(url)
    if (not same_origin(url, ARCHIVE_URL) or parsed.path != urlsplit(ARCHIVE_URL).path
            or parsed.fragment):
        raise ValueError("Vakyt search must stay within its native filtered listing.")
    query = parse_qs(parsed.query, keep_blank_values=True)
    start = query.pop("start", ["0"])
    if (query != {key: [value] for key, value in PARAMETERS.items()}
            or len(start) != 1 or not start[0].isascii() or not start[0].isdecimal()
            or int(start[0]) % 10):
        raise ValueError("Vakyt listing lost its exact series filter or native pagination settings.")
    return int(start[0])


def initial_request(root):
    return PageRequest(search_url())


def verification_request(root, count):
    return PageRequest(search_url(), context={"verify": True, "count": count})


def parse_listing(html, request, root):
    start = position(request.url)
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main#content")
    table = main.select_one('table[summary="This table browses all dspace content"]') if main else None
    counter = re.search(r"Результаты\s+(\d+)-(\d+)\s+из\s+(\d+)",
                        main.get_text(" ", strip=True) if main else "")
    if table is None or counter is None:
        raise ValueError("Vakyt result table or advertised count is missing.")
    first, last, count = map(int, counter.groups())
    if "count" in request.context and count != request.context["count"]:
        raise CatalogChanged("Vakyt search count changed; restart enumeration.")
    records = []
    for row in table.select("tr"):
        if not row.select_one("td"):
            continue
        anchor = row.select_one('td[headers~="t3"] a[href]')
        if anchor is None:
            raise ValueError("Vakyt search row has no record link.")
        url = canonical(anchor["href"], request.url)
        identity = kfu.handle(url)
        if urlsplit(url).query or identity == "net/86" or identity.split("/")[1] in kfu.COLLECTIONS:
            raise ValueError("Vakyt result is not an item record.")
        records.append(kfu.ORIGIN + "/jspui/handle/" + identity)
    if first != start + 1 or len(records) != min(10, count - start) or last != start + len(records) or not records:
        raise ValueError("Vakyt pagination range disagrees with its rows.")
    if len(set(records)) != len(records):
        raise CatalogChanged("Vakyt search repeated an item.")
    if request.context.get("verify"):
        return ListingPage([], [], advertised=count, validation=True)
    next_url = None
    if last < count:
        for anchor in main.select('ul.pagination a[href]'):
            url = canonical(anchor["href"], request.url)
            if position(url) == last:
                next_url = search_url(last)
        if next_url is None:
            raise ValueError("Vakyt search is missing its native next-page link.")
    following = [PageRequest(next_url, context={"count": count})] if next_url else []
    context = {"collection_handle": "net/86", "series_filter": "Вакыт", "listing_url": request.url}
    return ListingPage(records, following, entries=len(records), advertised=count,
                       fingerprint=json.dumps(records), detect_repeats=True,
                       record_context={url: context for url in records})


def record(html, page_url):
    metadata, assets = kfu.record(html, page_url)
    rows = metadata["bibliography_raw"]
    series = [row["value_raw"] for row in rows if "dc_relation_ispartofseries" in row["field_classes"]]
    if not any(value.strip() == "Вакыт" for value in series):
        raise ValueError("Vakyt search result does not confirm the selected series in item metadata.")
    metadata["publication"] = {
        "title": "Вакыт", "kind": "newspaper", "issue_title_raw": metadata["title_raw"],
        "series_raw": series,
        "publication_dates_raw": [row["value_raw"] for row in rows if "dc_date_issued" in row["field_classes"]],
    }
    return kfu.select_tatar(metadata, assets, publication="Vakyt")


def prepare_http(http, session_file):
    kfu.prepare_http(http, session_file, listing_route=position)


def download(http, manifest, summary, log, recheck):
    return kfu.download(http, manifest, summary, log, recheck, unit="file_or_issue")
