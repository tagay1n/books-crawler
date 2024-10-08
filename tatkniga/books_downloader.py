import hashlib
import json
import os
import random
import zipfile

import requests
from pyairtable.orm import Model, fields as F
# from src.google_sheets import get_by_md5, Record, update, append, AUDIOBOOKS_SPREADSHEET_ID
from src.yandex_disk import upload_to_yandex, create_public_link

from utils import load_books_metas, DOWNLOADS_FOLDER, get_real_path, load_downloaded_files, write_if_new, read_config

PATH_TO_BOOKS_IN_YDISK = "НейроТатарлар/kitaplar/tatkniga.ru"
PATH_TO_AUDIOBOOKS_IN_YDISK = "НейроТатарлар/audiokitaplar/tatkniga.ru"


def download(dfs, config):
    """
    This function downloads the books from the links in the books_metas.txt file.
    :param dfs: file the store the downloaded file's links
    """
    book_metas = load_books_metas()
    downloaded_files = load_downloaded_files()
    process_books(book_metas, downloaded_files, dfs, config)
    # process_audiobooks(book_metas, downloaded_files, dfs, config)


class Document(Model):
    # MD5 hash of the file
    md5 = F.TextField("md5")
    # MIME type of the file
    mime_type = F.TextField("mime_type")
    # Names of the document, more than one if there are duplicates
    names = F.TextField("names")
    # Yandex public url of the document
    ya_public_url = F.UrlField("ya_public_url")
    # Yandex public key of the document, used to retrieve temporary download link
    ya_public_key = F.TextField("ya_public_key")
    # Yandex resource id of the document. Together with public key it's used to identify the document
    ya_resource_id = F.TextField("ya_resource_id")

    class Meta:
        base_id = "appyygYGhPHwIQPO2"
        table_name = "tblmCi8f63d4YxEWF"
        api_key = "patxCM0Hw1Y3GbzHm.88a32e7eb5d67ea4ad91f7c5a73aad6a910938ba97ad5ab36463f29a00460466"

    def __str__(self):
        return self.to_record()['fields'].__str__()

    def __eq__(self, other):
        self_fields = self.to_record()['fields']
        other_fields = other.to_record()['fields']
        self_names_raw = self_fields.pop('names', "[]")
        other_names_raw = other_fields.pop('names', "[]")
        if self_fields != other_fields:
            return False

        self_names = set(json.loads(self_names_raw))
        other_names = set(json.loads(other_names_raw))
        return bool(self_names.intersection(other_names))

    def update(self, other):
        tmp_names = json.loads(self.names) if self.names else []

        fields = other.__dict__
        for key, value in fields.items():
            setattr(self, key, value)

        self.names = json.dumps(
            list(set(tmp_names + json.loads(fields['_fields']['names']))),
            ensure_ascii=False
        )

    def update_names(self, other):
        self.names = json.dumps(
            list(
                set(
                    (json.loads(self.names) if self.names else [])
                    +
                    (json.loads(other.names) if other.names else [])
                )
            ),
            ensure_ascii=False
        )


def get_all_md5s():
    all_md5s = set()
    for doc in Document.all(fields=["md5"]):
        all_md5s.add(doc.md5)
    return all_md5s


def process_books(book_metas, downloaded_files, dfs, config):
    all_md5s = get_all_md5s()
    book_metas = [
        book for book in book_metas
        if book["type"] == "book" and book.get('download_link')
    ]
    for meta in book_metas[:]:
        title = meta["title"]
        link = meta["download_link"]
        if link in downloaded_files:
            print(f"Already downloaded `{title}`")
            continue

        md5, file = _download_by_link(link, title, get_real_path(DOWNLOADS_FOLDER))
        if not md5:
            continue
        meta["md5"] = md5
        print(f"Downloaded `{title}`")
        if md5 not in all_md5s:
            remote_path = upload_to_yandex(file, config, PATH_TO_BOOKS_IN_YDISK)
            public_url = create_public_link(remote_path, config)
            print(public_url, meta, remote_path)
            exit(0)
            # doc = Document(
            #     md5=md5,
            #     mime_type="application/pdf",
            #     names=json.dumps([title])
            # )
            # doc.save()
        # row, rng = get_by_md5(md5)
        # record = (
        #     Record()
        #     .set_md5(md5)
        #     .append_source(meta["source_link"])
        #     .append_original_name(title)
        #     .set_meta(meta)
        # )
        # if row:
        #     print(f"Book `{title}` already exists in the Google Sheets")
        #     # update existing data
        #     record = record.merge(Record.from_row(row))
        #     update(rng, record)
        # else:
        #     print(f"Uploading `{title}` to Yandex.Disk")
        #     remote_path = upload_to_yandex(file, config, PATH_TO_BOOKS_IN_YDISK)
        #     public_url = create_public_link(remote_path, config)
        #     meta["ya_disk_link"] = public_url
        #     append(record)
        #
        # write_if_new(link, downloaded_files, dfs)
        # os.remove(file)


def process_audiobooks(book_metas, downloaded_files, dfs, config):
    audiobooks_metas = [
        book for book in book_metas
        if book["type"] == "audio" and book.get('download_link')
    ]
    for meta in audiobooks_metas[:]:
        title = meta["title"]
        link = meta["download_link"]
        if link in downloaded_files:
            print(f"Already downloaded `{title}`")
            continue

        md5, zip_archive = _download_by_link(link, title, get_real_path(DOWNLOADS_FOLDER))
        if not md5:
            continue
        print(f"Downloaded `{title}`")

        # unzipped_dir = unzip(zip_archive)

        # row, rng = get_by_md5(md5, spreadsheet_id=AUDIOBOOKS_SPREADSHEET_ID)
        # record = (
        #     Record()
        #     .set_md5(md5)
        #     .append_source(meta["source_link"])
        #     .append_original_name(title)
        #     .set_meta(meta)
        # )
        # if row:
        #     print(f"Audiobook `{title}` already exists in the Google Sheets")
        #     # update existing data
        #     record = record.merge(Record.from_row(row))
        #     update(rng, record, spreadsheet_id=AUDIOBOOKS_SPREADSHEET_ID)
        # else:
        # print(f"Uploading `{title}` to Yandex.Disk")
        # for root, dirs, files in os.walk(unzipped_dir):
        #     dir_path = os.path.relpath(root, unzipped_dir)
        #     for file in files:
        #         local_path = os.path.join(root, file)
        #         remote_path = os.path.normpath(os.path.join(PATH_TO_AUDIOBOOKS_IN_YDISK, title, dir_path))
        #         upload_to_yandex(local_path, config, remote_path)
        #
        # public_link = create_public_link(os.path.join(PATH_TO_AUDIOBOOKS_IN_YDISK, title), config)
        # meta["ya_disk_link"] = public_link
        # append(record, spreadsheet_id=AUDIOBOOKS_SPREADSHEET_ID)

        write_if_new(link, downloaded_files, dfs)
        # os.remove(zip_archive)


def _download_by_link(link, title, downloads_folder):
    tmp_name = f"{downloads_folder}/tmp_{random.randint(0, 10000000)}"
    print(f"Downloading {link}")
    response = requests.get(link, verify=False)

    with open(tmp_name, 'wb') as f:
        f.write(response.content)
    match response.headers['Content-Type']:
        case "application/pdf":
            extension = "pdf"
        case "text/html":
            print(f"Cannot download `{title}`:{link}. It is not a book, most likely link returned 404")
            os.remove(tmp_name)
            return None, None
        case "application/zip" | 'application/x-zip-compressed':
            extension = "zip"
        case "audio/mpeg":
            # derive extension from the link
            extension = link.split(".")[-1]
        case _:
            os.remove(tmp_name)
            raise Exception(f"Unknown content type: {response.headers['Content-Type']}")

    with open(tmp_name, "rb") as f:
        h = hashlib.md5(f.read()).hexdigest()
    new_name = f"{downloads_folder}/{title}.{extension}"
    os.rename(tmp_name, new_name)
    print(f"Downloaded `{title}` to {new_name}")
    return h, new_name


def unzip(zip_archive):
    file_name = os.path.splitext(os.path.basename(zip_archive))[0]
    unzipped_folder = get_real_path(os.path.join(DOWNLOADS_FOLDER, file_name))

    with zipfile.ZipFile(zip_archive, 'r') as zip_ref:
        zip_ref.extractall(unzipped_folder)
    return unzipped_folder


def check_config():
    import yadisk

    config = read_config()
    if not yadisk.YaDisk(token=config['yandex']['oauth_token']).check_token():
        raise Exception("Invalid Yandex Disk OAuth token")


check_config()
