from utils import load_index_file, dump_index
import os
import json
import requests
import bs4 as bs
from urllib.parse import urlparse
import re
from rich import print
from rich.progress import Progress, TextColumn, ProgressColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, MofNCompleteColumn, TimeElapsedColumn, FileSizeColumn, TotalFileSizeColumn, TransferSpeedColumn

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning)


entry_point = "https://kitap.tatar.ru/tt/ssearch/ecollection/?attr=text_t&q=*&sort=record-create-date&q=tat&attr=code-language_t"


def index():
    print("Creating index of books")
    new_index = _create_newest_index()
    print("Loading old index of books")
    old_index = load_index_file()
    _merged_index = _merge_indexes(new_index, old_index)
    print("Merged indexes")
    dump_index(_merged_index)


def _merge_indexes(new_index, old_index):
    _merged_index = {}
    _new_entries = 0
    for k, v in new_index.items():
        if k not in old_index:
            _new_entries += 1
            _merged_index[k] = v
        else:
            _merged_index[k] = old_index[k]
            _merged_index[k].update(v)

    if _new_entries:
        print(f"[green]Added {_new_entries} new entries to the index.[/green]")

    return _merged_index


def _create_newest_index():
    next_page = 1
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
        task = progress.add_task("Indexing pages", start=True, total=None)
        total_pages = None

        while next_page:
            with requests.get(
                url=entry_point,
                params={"page": next_page},
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
                    title_elem = book_card.select_one(
                        'h3[class="list__title"] > a[class="list__title-link"]')
                    title = re.sub(r"NEW!!!", "", title_elem.text.strip())
                    title = re.sub(r"\\s+", r"\\s", title)
                    meta = {
                        "title": title
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
                    if _publish_year := _list_items.get("Бастырып чыгару елы:"):
                        meta['publish_year'] = _publish_year
                    if _lang := _list_items.get("Тел:"):
                        meta['lang'] = _lang
                    if _collection := _list_items.get("Коллекция:"):
                        meta['collection'] = _collection

                    if _tags := [i.text.strip() for i in book_card.select('ul[class="tag list__tag"] > li[class="tag__item"] > a')]:
                        meta["tags"] = _tags

                    if _author := book_card.select_one('p[class="list__description"]'):
                        _author = " ".join(_author.text.split()).strip()
                        if _author and not _author.isspace():
                            meta['author'] = _author

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

                progress.update(task, completed=current_page,
                                total=total_pages)

        assert len(
            new_metas) == total_docs, f"Expected {total_docs} documents, but indexed {len(new_metas)} documents."

    return new_metas
