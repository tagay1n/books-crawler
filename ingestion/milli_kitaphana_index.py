"""Scrapes Milli Kitaphana search pages, builds a metadata index, and merges it with existing records."""
from .runtime_config import option as operational_option

from .native_records import records, update_records
from .milli_kitaphana_utils import require_runtime

class Requests:
    def get(self, url, **kwargs):
        return require_runtime().request("GET", url, **kwargs)

requests = Requests()
import bs4 as bs
from urllib.parse import urlparse
import re
from rich import print
from requests.exceptions import RequestException
from .network import BudgetStop
from .milli_kitaphana_logging import error_fields


def index():
    print("Creating index of books")
    runtime = require_runtime()
    scans = runtime.manifest.data.setdefault('milli_catalog', {})
    if len(scans) == len(operational_option('milli_kitaphana_index', 'language_queries')) + len(operational_option('milli_kitaphana_index', 'collection_queries')) and all(scan.get('complete') for scan in scans.values()):
        scans.clear()
    try:
        for lang_code in operational_option('milli_kitaphana_index', 'language_queries'):
            _create_newest_index(lang_code)
        for collection in operational_option('milli_kitaphana_index', 'collection_queries'):
            _create_collection_index(collection)
    finally:
        for scan in scans.values():
            if 'seen' in scan:
                scan['seen_count'] = len(scan.pop('seen'))
        # One atomic save for the observations and their scan frontiers, including
        # partial discovery. Per-page work only updates the in-memory manifest.
        runtime.manifest.checkpoint()
        runtime.event('discovery_checkpointed', pages=runtime.summary['pages'],
                      records=len(runtime.manifest.data['records']))


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
    runtime.event('scan_resumed', scan=description, next_page=next_page)
    # Migrate older inventories to a scalar count rather than rewriting every ID.
    previous_seen = set(scan.pop('seen', []))
    previous_count = scan.get('seen_count', len(previous_seen))
    seen = set()
    total_docs = None
    total_pages = None
    retry_page = None
    while next_page:
        if runtime.summary['pages'] >= runtime.settings.max_pages:
            raise BudgetStop('discovery page cap')
        runtime.event('page_started', scan=description, page=next_page)
        try:
            with requests.get(
                url=operational_option('milli_kitaphana_index', 'entry_point'),
                params=base_params + [('page', next_page)],
            ) as response:
                soup = bs.BeautifulSoup(response.text, 'html.parser')
            count = soup.select_one('.search-nav__item.search-nav__item_sm-ta-c > .search-nav__text')
            total_docs = int(count.text.split(':')[1].strip())
            cards = soup.select('.list__col-text')
            if total_docs == 0 and not cards and next_page == 1:
                scan.update(next_page=1, complete=True, seen_count=0)
                runtime.summary['pages'] += 1
                runtime.event('page_indexed', scan=description, page=1,
                              records_on_page=0, seen_records=0, complete=True)
                break
            if not cards:
                raise ValueError('Discovery returned no book cards')
            page_metas = {}
            card_failed = False
            for position, card in enumerate(cards, 1):
                try:
                    key, metadata = _parse_book_card(card)
                    page_metas[key] = metadata
                except (ValueError, AttributeError, KeyError, TypeError, IndexError) as error:
                    card_failed = True
                    _failure(runtime, description, next_page, error, card=position)
            # Preserve good cards even if another card or pagination is broken.
            latest = records(runtime.manifest, page_metas)
            merged = {key: {**latest.get(key, {}), **value} for key, value in page_metas.items()}
            update_records(runtime.manifest, merged,
                           url_prefix=operational_option('milli_kitaphana_index', 'url_https_kitap_tatar_ru'))
            runtime.summary['pages'] += 1
            pagination = soup.select_one('.pagination')
            if pagination is None and total_docs == len(cards):
                current_page = total_pages = 1
            else:
                current_page = int(pagination.select_one('.active').text.strip())
                total_pages = max(int(li.text.strip()) for li in pagination.select('li')
                                  if li.text.strip().isdigit())
            if current_page != next_page or current_page > total_pages:
                raise ValueError('Unexpected discovery pagination')
            if card_failed:
                # Continue inspecting independent cards/pages, but preserve the
                # first incomplete page as the next run's retry frontier.
                retry_page = retry_page or current_page
            seen.update(page_metas)
            finished = current_page == total_pages
            if retry_page is None:
                scan['seen_count'] = previous_count + len(seen - previous_seen)
                scan.update(next_page=1 if finished else current_page + 1, complete=finished)
            else:
                scan.update(next_page=retry_page, complete=False)
            runtime.event('page_indexed', scan=description, page=current_page,
                          total_pages=total_pages, records_on_page=len(page_metas),
                          seen_records=previous_count + len(seen - previous_seen), complete=scan['complete'])
            if finished:
                if retry_page is None and scan['seen_count'] != total_docs:
                    # Counts cannot prove coverage of a moving catalog. Rescan
                    # this query next run while still processing its found books.
                    scan.update(next_page=1, complete=False, seen_count=0)
                    _failure(runtime, description, current_page,
                             ValueError('Discovery count differs from advertised count'))
                break
            next_page = current_page + 1
        except (RequestException, ValueError, AttributeError, KeyError, TypeError, IndexError) as error:
            _failure(runtime, description, next_page, error)
            break


def _failure(runtime, description, page, error, **fields):
    failure = {'stage': 'discovery', 'scan': description, 'page': page,
               **fields, **error_fields(error)}
    runtime.summary['errors'].append(failure)
    runtime.event('discovery_failed', **{key: value for key, value in failure.items() if key != 'stage'})


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
