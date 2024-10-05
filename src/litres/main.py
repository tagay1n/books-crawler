import json

import bs4 as bs
import requests

from pdf import visit_pdf_books_pages
from consts import TOTAL_PAGES, entry_point, domain
from utils import get_sid, get_in_workdir


def collect_book_pages():
    books = []
    for i in range(1, TOTAL_PAGES + 1):
        paginated_url = f"{entry_point}&page={i}"
        print(f"Processing page: {paginated_url}")
        headers = {
            "Cookie": f"SID={get_sid()};"
        }
        with requests.get(paginated_url, headers=headers) as r:
            r.raise_for_status()
            soup = bs.BeautifulSoup(r.text, "html.parser")
            for book in soup.select('div[class^="ArtDefault_container"]'):
                details = {'title': book.select_one('p[class^="ArtInfo_title"]').get_text()}
                if author := book.select_one('a[class^="ArtInfo_author"]'):
                    details['author'] = author.get_text()
                details['subscription'] = True if book.select_one(
                    'div[class^="ArtPriceFooter_ArtPriceFooterSubscriptions"]') else False
                details['url'] = f"{domain}{book.select_one('a[class^="ArtDefault_cover"]')['href']}"
                details['content_type'] = "pdf" if book.select_one('span[class^="Label_label"]') else 'text'
                books.append(details)

    # deduplicate possible duplicates of books details
    books = [dict(t) for t in {tuple(d.items()) for d in books}]
    with open(get_in_workdir("books-index.json"), "w") as f:
        json.dump(books, f, indent=4, ensure_ascii=False)

    print(f"Collected {len(books)} books")

def main():
    collect_book_pages()
    visit_pdf_books_pages()


if __name__ == "__main__":
    main()
