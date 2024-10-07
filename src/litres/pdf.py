import io
import json
import os.path
from urllib.parse import urlparse, parse_qs

import pymupdf
import requests
from PIL import Image
from rich.progress import track
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from consts import domain
from utils import get_sid, get_in_workdir, create_driver


def visit_pdf_books_pages():
    """
    Entry point for visiting pdf books pages.

    Visit pdf books pages, download their pages separately and create pdf from them
    """
    path_to_idx = get_in_workdir("artifacts/books-index.json")
    with open(path_to_idx, "r") as f:
        all_books = json.load(f)

    pdf_books = [b for b in all_books.values() if b['content_type'] == 'pdf']

    print(f"Visiting {len(pdf_books)} pdf books pages")

    for book in pdf_books[:]:
        url = book['url']
        print(f"Visiting book page: {url}")
        try:
            file_id = book.get('file_id') or _get_file_id(url)
            page_extensions = book.get('ext') or _get_page_extensions(file_id)
            _download_book_pages(file_id, page_extensions)

            book['file_id'] = file_id
            book['ext'] = page_extensions
            with open(path_to_idx, "w") as f:
                json.dump(all_books, f, indent=4, ensure_ascii=False)

            _create_pdf(book)
        except Exception as e:
            print(f"Error occurred while processing book: {url}")
            print(e)


def _get_file_id(book_page_url):
    """
    Get file_id from book page url

    :param book_page_url:
    :return: internal file id
    """
    print(f"Getting file id for book page: {book_page_url}")
    with create_driver() as driver:
        driver.get(book_page_url)
        read_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[class^="Button_textContainer__"]'))
        )
        read_button.click()
        reader_url = driver.current_url
        parsed_url = urlparse(reader_url)
        queries = parse_qs(parsed_url.query)
        if not (file := queries.get('file')):
            raise ValueError(f"Could not find file id in url: {reader_url}")
        return file[0]


def _get_page_extensions(file_id):
    """
    Get dict with extensions for each page

    :param file_id: id of the file
    :return: dict with extensions for each page
    """
    print(f"Getting page extensions for file: {file_id}")
    headers = {
        "Cookie": f"SID={get_sid()};",
    }
    with requests.get(f"{domain}/pages/get_pdf_js/?file={file_id}", headers=headers) as r:
        r.raise_for_status()
        with create_driver() as driver:
            return driver.execute_script(
                """let PFURL = { pdf: { } };""" + r.text + "; return PFURL.pdf[" + file_id + "];")


def _download_book_pages(file_id, page_extensions):
    """
    Download all pages for the book
    """
    artifacts_dir = get_in_workdir(os.path.join("artifacts", "images", file_id))

    os.makedirs(artifacts_dir, exist_ok=True)

    p = page_extensions['pages'][0]['p']

    for page_no in track(range(0, len(p)), description=f"Downloading pages for file: {file_id}"):
        ext = p[page_no]['ext']
        w = p[page_no]['w']
        file_name = os.path.join(artifacts_dir, f"{page_no}.{ext}")
        if not os.path.exists(file_name):
            url = f"{domain}/pages/get_pdf_page/?file={file_id}&page={page_no}&rt=w{w}&ft={ext}"
            headers = {
                "Cookie": f"SID={get_sid()};"
            }
            with requests.get(url, headers=headers, stream=True) as r:
                r.raise_for_status()
                with Image.open(io.BytesIO(r.content)) as img:
                    img.save(file_name, quality=95, optimize=True, subsampling=0)


def _create_pdf(book):
    """
    Create pdf from downloaded pages images
    """
    file_id = book['file_id']
    artifacts_dir = get_in_workdir(os.path.join("artifacts", "images", file_id))
    pdf_dir = get_in_workdir("artifacts/docs")
    os.makedirs(pdf_dir, exist_ok=True)

    name_with_ext = f"{book['full_name']}.pdf"
    pdf_file = os.path.join(pdf_dir, name_with_ext)
    if os.path.exists(pdf_file):
        return

    with pymupdf.open() as doc:
        # sort pages by number
        images = sorted([f for f in os.listdir(artifacts_dir)], key=lambda x: int(x.split(".")[0]))
        for page in track(images, description=f"Creating pdf for file: {file_id}"):
            with pymupdf.open(os.path.join(artifacts_dir, page)) as img:
                rect = img[0].rect  # pic dimension
                img_pdf = pymupdf.open("pdf", img.convert_to_pdf())  # open stream as PDF
                page = doc.new_page(width=rect.width, height=rect.height)
                page.show_pdf_page(rect, img_pdf, 0)  # image fills the page

        doc.save(pdf_file)

