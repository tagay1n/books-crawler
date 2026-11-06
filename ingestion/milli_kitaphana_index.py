"""Scrapes Milli Kitaphana search pages, builds a metadata index, and merges it with existing records."""
from .runtime_config import option as operational_option

from .milli_kitaphana_utils import load_index_file, dump_index
from .milli_kitaphana_utils import require_runtime

class Requests:
    def get(self, url, **kwargs):
        return require_runtime().request("GET", url, **kwargs)

requests = Requests()
import bs4 as bs
from urllib.parse import urlparse
import re
from rich import print
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, MofNCompleteColumn, TimeElapsedColumn
from .milli_kitaphana_merge_index import _merge_indexes


def index():
    print("Creating index of books")
    runtime = require_runtime()
    scans = runtime.manifest.data.setdefault('milli_catalog', {})
    if len(scans) == len(operational_option('milli_kitaphana_index', 'language_queries')) + len(operational_option('milli_kitaphana_index', 'collection_queries')) and all(scan.get('complete') for scan in scans.values()):
        scans.clear()
    new_index = {}
    for lang_code in operational_option('milli_kitaphana_index', 'language_queries'):
        lang_index = _create_newest_index(lang_code)
        new_index.update(lang_index)
    for collection in operational_option('milli_kitaphana_index', 'collection_queries'):
        collection_index = _create_collection_index(collection)
        new_index.update(collection_index)
    print("Loading old index of books")
    old_index = load_index_file()
    _merged_index = _merge_indexes(new_index, old_index)
    print("Merged indexes")
    dump_index(_merged_index)


def _create_newest_index(language_code):
    params = [
        ("attr", "text_t"),
        ("q", "*"),
        ("sort", "record-create-date"),
        ("q", language_code),
        ("attr", "code-language_t"),
    ]
    return _create_index(params, f"language {language_code}")


def _create_collection_index(collection):
    return _create_index(collection["params"], f"collection {collection['name']}")


def _create_index(base_params, description):
    runtime = require_runtime()
    scans = runtime.manifest.data.setdefault("milli_catalog", {})
    scan = scans.setdefault(description, {"next_page": 1, "complete": False})
    if scan["complete"]:
        return {}
    next_page = scan["next_page"]
    total_docs = None
    new_metas = {}
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        BarColumn(),
    ) as progress:
        task = progress.add_task(f"Indexing pages ({description})", start=True, total=None)
        total_pages = None

        while next_page:
            if runtime.summary['pages'] >= runtime.settings.max_pages:
                from .network import BudgetStop
                raise BudgetStop('discovery page cap')
            params = base_params + [("page", next_page)]
            with requests.get(
                url=operational_option('milli_kitaphana_index', 'entry_point'),
                params=params,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'},
                verify=False
            ) as r:
                r.raise_for_status()
                soup = bs.BeautifulSoup(r.text, "html.parser")
                # define total count of docs if have not defined yet
                if not total_docs:
                    _div = soup.select_one(
                        '.search-nav__item.search-nav__item_sm-ta-c > .search-nav__text')
                    total_docs = int(_div.text.split(':')[1].strip())

                for book_card in soup.select('.list__col-text'):
                    card_link, meta = _parse_book_card(book_card)
                    new_metas[card_link] = meta

                pagination_info = soup.select_one(".pagination")
                current_page = int(
                    pagination_info.select_one('.active').text.strip())
                if not total_pages:
                    total_pages = sorted([int(j) for j in [i.text.strip(
                    ) for i in pagination_info.select("li")] if j.isdigit()], reverse=True)[0]

                if current_page == total_pages:
                    # here if current page is the last
                    next_page = None
                else:
                    next_page = current_page + 1

                latest = load_index_file()
                merged = _merge_indexes(new_metas, latest)
                for key, value in merged.items():
                    runtime.manifest.observe({**value, 'url': value.get('url') or operational_option('milli_kitaphana_index', 'url_https_kitap_tatar_ru') + key}, [], record_key=key, persist=False)
                scan.update(next_page=next_page or 1, complete=next_page is None)
                scan['seen'] = list(set(scan.get('seen', [])) | set(new_metas))
                runtime.summary['pages'] += 1
                runtime.manifest.checkpoint()
                progress.update(task, completed=current_page,
                                total=total_pages)

        assert len(
            scan.get('seen', new_metas)) == total_docs, f"Expected {total_docs} documents, but indexed {len(new_metas)} documents."

    return new_metas


def _parse_book_card(book_card):
    title_elem = book_card.select_one(
        'h3[class="list__title"] > a[class="list__title-link"]')
    title = re.sub(r"NEW!!!", "", title_elem.text.strip())
    title = re.sub(r"\\s+", r"\\s", title)
    meta = {
        "title": title.strip()
    }
    card_link = urlparse(title_elem['href']).path.rstrip("/")
    _k = None
    _v = None
    _list_items = {}
    for ch in book_card.select_one('dl[class="list__dl"]'):
        if ch.name == "dt":
            _k = " ".join(ch.text.split())
        elif ch.name == "dd":
            _v = " ".join(ch.text.split())
            if _k and _v:
                _list_items[_k] = _v
                _k = None
                _v = None
    if _publish_year := _first_present(_list_items, "Бастырып чыгару елы:", "Год публикации:"):
        meta['publish_year'] = _publish_year
    if _lang := _first_present(_list_items, "Тел:", "Язык:"):
        meta['lang'] = _lang
    if _collection := _first_present(_list_items, "Коллекция:"):
        meta['collection'] = _collection

    if _tags := [i.text.strip() for i in book_card.select('ul[class="tag list__tag"] > li[class="tag__item"] > a')]:
        meta["tags"] = _tags

    if _author := book_card.select_one('p[class="list__description"]'):
        _author = " ".join(_author.text.split()).strip()
        if _author and not _author.isspace():
            meta['author'] = _author

    meta["properties_raw"] = _list_items
    return card_link, meta


def _first_present(items, *keys):
    for key in keys:
        if value := items.get(key):
            return value
    return None
