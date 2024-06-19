import json
import os
import sys
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# entering point for the crawling and mask for the pages to visit,
DOMAIN = "https://tatkniga.ru"

# This is the mask for the books pages - mask for the pages that we are interested in.
BOOKS_PAGE_MASK = "https://tatkniga.ru/books/"

# This is the mask for the pages that we are not interested in due to they do not contain links to book's pages
SKIP_FILTERS = [
    "https://tatkniga.ru/news",
    "https://tatkniga.ru/Identity",
    "https://tatkniga.ru/public-offers",
    "https://tatkniga.ru/authentication"
    "https://tatkniga.ru/support",
    "https://tatkniga.ru/account",
    "https://tatkniga.ru/about",
    "https://tatkniga.ru/cart",
]

# Name of the file where we store the visited non-book pages. We need it to resume crawling after the crash
VISITED_NON_BOOK_PAGES = "workdir/visited_pages.txt"
# Name of the file where we store the visited book pages. We need it to resume crawling after the crash
VISITED_BOOK_PAGES = "workdir/visited_book_pages.txt"
# Name of the file where we store the pages that contain links to the book's pages and need to be crawled
BOOKS_PAGES_LIST = "workdir/books_pages.txt"
# Name of the file where we store the metas of the books
BOOKS_METAS = "workdir/books_metas.json"
# Name of the folder where we store the downloaded books
DOWNLOADS_FOLDER = "workdir/downloads"
# Name of the file where we store the list of the downloaded files
DOWNLOADED_FILES = "workdir/downloaded_files.txt"


def load_visited_pages():
    with open(get_real_path(VISITED_NON_BOOK_PAGES), "r") as f:
        return set(f.read().splitlines())


def load_visited_book_pages():
    with open(get_real_path(VISITED_BOOK_PAGES), "r") as f:
        return set(f.read().splitlines())


def load_books_pages():
    with open(get_real_path(BOOKS_PAGES_LIST), "r") as f:
        return set(f.read().splitlines())


def load_downloaded_files():
    with open(get_real_path(DOWNLOADED_FILES), "r") as f:
        return set(f.read().splitlines())


def load_books_metas():
    with open(get_real_path(BOOKS_METAS), "r") as f:
        return json.load(f)


def get_element(xpath, driver, timeout=30):
    try:
        element = WebDriverWait(
            driver,
            timeout,
            ignored_exceptions=[StaleElementReferenceException, TimeoutException]
        ).until(
            expected_conditions.presence_of_all_elements_located((By.XPATH, xpath))
        )
        return element
    except TimeoutException:
        print("Timeout exception on page for element: " + xpath)
        return None


def create_driver():
    options = webdriver.ChromeOptions()
    options.headless = True
    return webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options
    )


def get_hostname(url):
    parse_result = urlparse(url)
    return f"{parse_result.scheme}://{parse_result.netloc}"


def create_files_if_not_exists():
    if not os.path.exists(get_real_path("workdir")):
        os.makedirs("workdir")

    downloads_folder = get_real_path(DOWNLOADS_FOLDER)
    if not os.path.exists(downloads_folder):
        os.makedirs(downloads_folder)

    def aux(file_path, content=""):
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                f.write(content)
        return file_path

    visited_non_book_pages_sink = aux(get_real_path(VISITED_NON_BOOK_PAGES))
    visited_book_pages_sink = aux(get_real_path(VISITED_BOOK_PAGES))
    book_pages_sink = aux(get_real_path(BOOKS_PAGES_LIST))
    book_metas = aux(get_real_path(BOOKS_METAS), content="[]")
    downloaded_files = aux(get_real_path(DOWNLOADED_FILES))
    return visited_non_book_pages_sink, visited_book_pages_sink, book_pages_sink, book_metas, downloaded_files, downloads_folder


def get_real_path(rel_path):
    parent_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
    paths = [parent_dir, rel_path]
    real_path = os.path.join(*paths)
    return os.path.normpath(real_path)


def mark_visited_book_page(link):
    with open(get_real_path(VISITED_BOOK_PAGES), "a") as f:
        f.write(link + "\n")
        f.flush()


def write_if_new(element, collector, file):
    """
    This function writes the element to the file if it is not in the collector.

    :param element: item to write
    :param collector: accumulator of the elements
    :param file: target file to write
    :return: True if the element was new and False otherwise
    """
    if element not in collector:
        collector.add(element)
        with open(file, "a") as f:
            f.write(element + "\n")
            f.flush()
        return True
    return False
