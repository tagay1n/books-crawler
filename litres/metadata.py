import json
import re

import bs4 as bs
import requests
from rich.progress import track

from utils import get_in_workdir, get_sid


def scrap_metadata():
    """
    Scrap metadata for the books and save it to the file
    """
    path_to_idx = get_in_workdir("../__artifacts/litres/books-index.json")
    with open(path_to_idx, "r") as f:
        _all_books = json.load(f)
    headers = {
        "Cookie": f"SID={get_sid()};",
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    }
    for b in track(_all_books.values(), description="Scraping metadata"):
        with requests.get(b['url'], headers=headers) as resp:
            print(f"Visiting book page: {b['url']}")
            metadata = {}
            resp.raise_for_status()
            soup = bs.BeautifulSoup(resp.text, "html.parser")
            characteristics_block = soup.select_one('div[class^="CharacteristicsBlock_characteristics__"]')
            for characteristic in characteristics_block.findAll('div', {
                'class': re.compile(r'CharacteristicsBlock_characteristic__(?!title).+')}):
                title = characteristic.select_one('div[class^="CharacteristicsBlock_characteristic__title__"]')
                title = title.get_text(strip=True).rstrip(':')
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

    with open(path_to_idx, "w") as f:
        json.dump(_all_books, f, indent=4, ensure_ascii=False)
