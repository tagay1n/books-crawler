import io
import json
import os.path
from urllib.parse import urlparse, parse_qs

import requests
from PIL import Image
from rich.progress import track
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from seleniumwire import webdriver
import pymupdf
from consts import domain


from utils import get_sid, get_in_workdir


def visit_pdf_books_pages():
    """
    Entry point for visiting pdf books pages.

    Visit pdf books pages, download their pages separately and create pdf from them
    """
    path_to_idx = get_in_workdir("books-index.json")
    with open(path_to_idx, "r") as f:
        books = json.load(f)

    books = [book for book in books if book['content_type'] == 'pdf']

    print(f"Visiting {len(books)} pdf books pages")

    for book in books[:1]:
        url = book['url']
        print(f"Visiting book page: {url}")
        file_id = book.get('file_id') or _get_file_id(url)
        page_extensions = book.get('ext') or _get_page_extensions(file_id)
        _download_book_pages(file_id, page_extensions)
        _create_pdf(file_id)
        book['file_id'] = file_id
        book['ext'] = page_extensions

        with open(path_to_idx, "w") as f:
            json.dump(books, f, indent=4, ensure_ascii=False)

def _get_file_id(book_page_url):
    """
    Get file_id from book page url

    :param book_page_url:
    :return: internal file id
    """
    print(f"Getting file_id for book page: {book_page_url}")
    with _create_driver() as driver:
        driver.get(book_page_url)
        read_button = driver.find_element(value='div[class^="Button_textContainer__"]', by=By.CSS_SELECTOR)
        read_button.click()
        reader_url = driver.current_url
        parsed_url = urlparse(reader_url)
        queries = parse_qs(parsed_url.query)
        if not (file := queries.get('file')):
            raise ValueError(f"Could not find file_id in url: {reader_url}")
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
        with _create_driver() as driver:
            return driver.execute_script("""let PFURL = { pdf: { } };""" + r.text+"; return PFURL.pdf[" + file_id + "];")


def _download_book_pages(file_id, page_extensions):
    """
    Download all pages for the book
    """
    artifacts_dir = os.path.join("artifacts", "litres", file_id)

    if not os.path.exists(artifacts_dir):
        os.makedirs(artifacts_dir, exist_ok=True)

    p = page_extensions['pages'][0]['p']

    for page_no in track(range(len(p)), description=f"Downloading pages for file: {file_id}"):
        ext = p[page_no]['ext']
        file_name = os.path.join(artifacts_dir, f"{page_no}.{ext}")
        if not os.path.exists(file_name):
            url = f"{domain}/pages/get_pdf_page/?file={file_id}&page={page_no}&rt=w1900&ft={ext}"
            headers = {
                "Cookie": f"SID={get_sid()};"
            }
            with requests.get(url, headers=headers, stream=True) as r:
                r.raise_for_status()
                with Image.open(io.BytesIO(r.content)) as img:
                    img.save(file_name, quality=95, optimize=True, progressive=True, resolution=300, subsampling=0)


def _create_pdf(file_id):
    """
    Create pdf from downloaded pages images
    """
    artifacts_dir = os.path.join("artifacts", "litres", file_id)
    pdf_file = os.path.join("artifacts", "litres", f"{file_id}.pdf")
    with pymupdf.open() as doc:
        # sort pages by number
        images = sorted([f for f in os.listdir(artifacts_dir) if not f.endswith('.tmp')], key=lambda x: int(x.split(".")[0]))
        for page in track(images, description=f"Creating pdf for file: {file_id}"):
            with pymupdf.open(os.path.join(artifacts_dir, page)) as img:
                rect = img[0].rect  # pic dimension
                img_pdf = pymupdf.open("pdf",  img.convert_to_pdf() )  # open stream as PDF
                page = doc.new_page(width=rect.width, height=rect.height)
                page.show_pdf_page(rect, img_pdf, 0)  # image fills the page

        doc.save(pdf_file)


def _create_driver():
    """
    Create a new Selenium driver instance with request interceptor
    """
    def _interceptor(request):
        # add the missing headers
        request.headers['Cookie'] = f"SID={get_sid()};"

    options = webdriver.ChromeOptions()
    options.headless = True
    options.add_argument("--headless")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options
    )
    driver.request_interceptor = _interceptor
    return driver
