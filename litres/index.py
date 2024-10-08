import json
import os.path

import bs4 as bs
import requests

from consts import TOTAL_PAGES, entry_point, domain
from utils import get_sid, get_in_workdir, get_hash


def index():
    index_file_name = "books-index.json"
    index_dir = get_in_workdir("../__artifacts/litres")
    os.makedirs(index_dir, exist_ok=True)
    index_file = os.path.join(index_dir, index_file_name)
    if os.path.exists(index_file):
        with open(index_file, "r") as f:
            books = json.load(f)
    else:
        books = {}

    headers = {
        "Cookie": f"SID={get_sid()};",
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    }
    for i in range(1, TOTAL_PAGES + 1):
        paginated_url = f"{entry_point}&page={i}"
        print(f"Processing page: {paginated_url}")
        with requests.get(paginated_url, headers=headers) as r:
            r.raise_for_status()
            soup = bs.BeautifulSoup(r.text, "html.parser")
            for book in soup.select('div[class^="ArtDefault_container"]'):
                url = f"{domain}{book.select_one('a[class^="ArtDefault_cover"]')['href']}"
                if (h := get_hash(url)) in books:
                    details = books[h]
                else:
                    details = {}
                details['title'] = book.select_one('p[class^="ArtInfo_title"]').get_text()
                if author := book.select_one('a[class^="ArtInfo_author"]'):
                    details['author'] = author.get_text()
                details['subscription'] = True if book.select_one(
                    'div[class^="ArtPriceFooter_ArtPriceFooterSubscriptions"]') else False
                details['url'] = url
                details['content_type'] = "pdf" if book.select_one('span[class^="Label_label"]') else 'text'

                _title = details['title'].replace("/", "|").strip()
                _author = (details.get('author') or "").strip()
                details['full_name'] = (f"{_title} - {_author}" if _author else _title)[:133]
                books[h] = details

    with open(index_file, "w") as f:
        json.dump(books, f, indent=4, ensure_ascii=False)

    print(f"Collected {len(books)} books")
