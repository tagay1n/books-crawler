"""Scrapes per-book metadata fields from Litres pages and stores them back into the index."""

import re

import bs4 as bs
from .litres_utils import requests
from rich.progress import track

from .litres_utils import RUNTIME, load_index, save_index, get_sid


def scrap_metadata():
    """
    Scrape book metadata and checkpoint it in Postgres
    """
    _all_books = load_index('books')
    headers = {
        "Cookie": f"SID={get_sid()};",
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    }
    for b in track(_all_books.values(), description="Scraping metadata"):
        if RUNTIME.get():
            RUNTIME.get().budget.start_item()
        with requests.get(b['url'], headers=headers) as resp:
            print(f"Visiting book page: {b['url']}")
            metadata = {}
            resp.raise_for_status()
            soup = bs.BeautifulSoup(resp.text, "html.parser")
            characteristics_block = soup.select_one('div[class^="CharacteristicsBlock_characteristics__"]')
            if characteristics_block is None:
                raise ValueError('Litres metadata structure is missing')
            metadata["properties_raw"] = {}
            for characteristic in characteristics_block.findAll('div', {
                'class': re.compile(r'CharacteristicsBlock_characteristic__(?!title).+')}):
                title = characteristic.select_one('div[class^="CharacteristicsBlock_characteristic__title__"]')
                title = title.get_text(strip=True).rstrip(':')
                raw_value = characteristic.get_text(" ", strip=True)
                metadata["properties_raw"][title] = raw_value
                match title:
                    case "Возрастное ограничение":
                        key = "age_limit"
                    case "Правообладатель":
                        key = "publisher"
                    case "ISBN":
                        key = "isbn"
                    case "Дата написания":
                        key = "publish_date"
                    case "Составитель":
                        key = "created_by"
                    case _:
                        continue
                if value := (characteristic.find('span', recursive=False) or characteristic.find('a', recursive=False)):
                    metadata[key] = value.get_text(strip=True)

            if summary := soup.select_one(
                    'div[class^="BookCard_book__mainInfo__block__"] div[class^="BookCard_truncate__"] p'
            ): metadata['summary'] = summary.get_text(strip=True)

        b['metadata'] = metadata
        save_index('books', _all_books)

    save_index('books', _all_books)
