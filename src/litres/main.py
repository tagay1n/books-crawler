import json
import os.path

import bs4 as bs
import requests

from consts import TOTAL_PAGES, entry_point, domain
from pdf import visit_pdf_books_pages
from text import visit_text_books_pages, _make_up_markdown
from utils import get_sid, get_in_workdir, get_hash
import typer


app = typer.Typer()

@app.command()
def collect():
    """
    Collect book details from the website and save them to the file
    """
    index = get_in_workdir("artifacts/books-index.json")
    if os.path.exists(index):
        with open(index, "r") as f:
            books = json.load(f)
    else:
        books = {}

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
                url = f"{domain}{book.select_one('a[class^="ArtDefault_cover"]')['href']}"
                if (h:=get_hash(url)) in books:
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
                details['full_name']  = (f"{_title} - {_author}" if _author else _title)[:133]
                books[h] = details


    with open(get_in_workdir("artifacts/books-index.json"), "w") as f:
        json.dump(books, f, indent=4, ensure_ascii=False)

    print(f"Collected {len(books)} books")

@app.command()
def pdf():
    """
    Download pdf books from the website
    """
    visit_pdf_books_pages()


@app.command()
def text():
    """
    Download text books from the website
    """
    visit_text_books_pages()

@app.command()
def upload():
    """
    Upload markdown and images to hugging face
    """
    print("Uploading to huggingface")
    from huggingface_hub import HfApi
    api = HfApi()
    api.upload_folder(
        folder_path=get_in_workdir("artifacts/markdown"),
        repo_id="neurotatarlar/tt-litres-books",
        repo_type="dataset",
    )
    print("Done")


if __name__ == "__main__":
    app()
