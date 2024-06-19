import hashlib
import os
import random

import requests

from src.yandex_disk import upload_to_yandex
from utils import load_books_metas, DOWNLOADS_FOLDER, get_real_path, load_downloaded_files, write_if_new

PATH_TO_BOOKS_FOLDER_IN_YDISK = "НейроТатарлар/kitaplar/tatkniga.ru"


def download(dfs, config):
    """
    This function downloads the books from the links in the books_metas.txt file.
    :param dfs: file the store the downloaded file's links
    """
    book_metas = load_books_metas()
    downloaded_files = load_downloaded_files()
    book_metas = [
        book for book in book_metas
        if book["type"] == "book" and book.get('download_link')
    ]
    for meta in book_metas[:1]:
        title = meta["title"]
        link = meta["download_link"]
        if link in downloaded_files:
            print(f"Already downloaded `{meta['title']}`")
            continue

        md5, file = _download_by_link(link, title, get_real_path(DOWNLOADS_FOLDER))
        meta["md5"] = md5
        print(f"Downloaded `{meta['title']}`")

        public_url = upload_to_yandex(file, config, PATH_TO_BOOKS_FOLDER_IN_YDISK)
        meta["ya_disk_link"] = public_url
        print(meta)

        write_if_new(link, downloaded_files, dfs)

    print("Downloaded all books")


def _download_by_link(link, title, downloads_folder):
    tmp_name = f"{downloads_folder}/tmp_{random.randint(0, 10000000)}"
    print(f"Downloading {link}")
    response = requests.get(link)
    with open(tmp_name, 'wb') as f:
        f.write(response.content)
    match response.headers['Content-Type']:
        case "application/pdf":
            extension = "pdf"
        case _:
            raise Exception(f"Unknown content type: {response.headers['Content-Type']}")

    with open(tmp_name, "rb") as f:
        h = hashlib.md5(f.read()).hexdigest()
    new_name = f"{downloads_folder}/{title}.{extension}"
    os.rename(tmp_name, new_name)
    return h, new_name
