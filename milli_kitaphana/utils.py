"""Shared helpers for Milli Kitaphana: index paths, file locking, list management, and HTTP request wrappers."""

import json
import os
import shutil
import time
from contextlib import contextmanager
from datetime import datetime

import requests
import yaml
import zipfile

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning)


def get_in_workdir(file):
    """Return normalized absolute path under the milli_kitaphana directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.normpath(os.path.join(script_dir, file)))


HOST = "https://kitap.tatar.ru"
index_file_name = "books-index.json"
index_dir_name = "_index"
backups_dir_name = "_backups"
base_dir = get_in_workdir(os.path.join("../__artifacts/milli.kitaphana"))
index_root_dir = get_in_workdir("../__artifacts/milli.kitaphana")


def read_config():
    # read config file from the same directory
    with open(get_in_workdir("config.yaml"), "r", encoding="utf-8-sig") as f:
        return yaml.safe_load(f)
    
    
def load_index_file(index_file=None):
    if not index_file:
        index_file = get_index_file_loc()
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8-sig") as f:
            books = json.load(f)
    else:
        books = {}
    return books
        
        
def get_index_dir():
    """Return dedicated storage directory for index files."""
    return os.path.normpath(os.path.join(index_root_dir, index_dir_name))


def get_backups_dir():
    """Return dedicated storage directory for index backups."""
    return os.path.normpath(os.path.join(index_root_dir, backups_dir_name))


def get_index_file_loc():
    os.makedirs(index_root_dir, exist_ok=True)
    index_dir = get_index_dir()
    os.makedirs(index_dir, exist_ok=True)
    return os.path.join(index_dir, index_file_name)


def backup_index_snapshot():
    """
    Create a zip backup of current index state before a mutating command runs.

    Returns full path to the created backup archive.
    """
    index_file = get_index_file_loc()
    backups_dir = get_backups_dir()
    os.makedirs(backups_dir, exist_ok=True)

    # Human-readable local timestamp: YYYY-MM-DD_HH-MM-SS
    backup_file_name = f"{os.path.splitext(index_file_name)[0]}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.zip"
    backup_path = os.path.abspath(os.path.normpath(os.path.join(backups_dir, backup_file_name)))

    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        if os.path.exists(index_file):
            zf.write(index_file, arcname=index_file_name)
        else:
            zf.writestr(index_file_name, "{}\n")

    return backup_path


def dump_index(idx, index_file=None):
    if not index_file:
        index_file = get_index_file_loc()
    tmp_file = f"{index_file}.{os.getpid()}_part"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=4)
    shutil.move(tmp_file, index_file)


def get_lists_dir():
    lists_dir = os.path.normpath(get_in_workdir("../__artifacts/milli.kitaphana/subindexes"))
    os.makedirs(lists_dir, exist_ok=True)
    return lists_dir


def get_list_file_loc(name, lists_dir=None):
    if not name:
        raise ValueError("List name is required")
    if not lists_dir:
        lists_dir = get_lists_dir()
    os.makedirs(lists_dir, exist_ok=True)
    filename = name if name.endswith(".json") else f"{name}.json"
    return os.path.normpath(os.path.join(lists_dir, filename))


def get_not_downloaded_docs(index, limited):
    not_downloaded_docs = []
    for card_path, meta in index.items():
        if meta.get("broken", False):
            continue

        if limited:
            if not meta.get("needs_full_download"):
                continue
            downloaded = meta.get("downloaded")
            if downloaded is None or downloaded == "limited":
                not_downloaded_docs.append((card_path, meta))
            continue

        if meta.get("downloaded") is None:
            not_downloaded_docs.append((card_path, meta))

    not_downloaded_docs = sorted(not_downloaded_docs, key=lambda x: x[1].get('publish_year', "").strip('[]'), reverse=True)
    return not_downloaded_docs


@contextmanager
def open_lock(index_file, wait_seconds=0.5):
    lock_file = f"{index_file}.lock"
    try:
        while True:
            try:
                with open(lock_file, "x", encoding="utf-8") as f:
                    f.write(str(os.getpid()))
                break
            except FileExistsError:
                time.sleep(wait_seconds)
        yield
    finally:
        try:
            os.remove(lock_file)
        except FileNotFoundError:
            pass


def download_part(context, part):
    work_dir = context["work_dir"]
    enc_zip_path, enc_zip_part_path, enc_unzip_dir, enc_file_path = get_part_paths(work_dir, part)

    url = HOST + context['meta']["format_url"].format(url=part)
    # download the encrypted zip file
    with request(method="GET", url=url, stream=True, proxies=context.get('proxies')) as response:
        os.makedirs(work_dir, exist_ok=True)
        if os.path.exists(enc_zip_part_path):
            os.remove(enc_zip_part_path)
        # save the encrypted zip file
        with open(enc_zip_part_path, "wb") as enc_zip:
            task = context["progress"].download(part)
            for chunk in response.iter_content(chunk_size=1024):
                enc_zip.write(chunk)
                chunk_len = len(chunk)
                context['progress']._aux.update(task, advance=chunk_len)
            context['progress']._aux.update(
                task, description=f"Downloaded {part}")
            context['progress']._aux.stop_task(task)

    os.replace(enc_zip_part_path, enc_zip_path)

    # unzip the encrypted zip file
    with zipfile.ZipFile(enc_zip_path, 'r') as enc_zip:
        bad_entry = enc_zip.testzip()
        if bad_entry:
            raise ValueError(f"Corrupted encrypted zip for '{part}', bad entry: {bad_entry}")
        if "enc.dat" not in enc_zip.namelist():
            raise ValueError(f"Encrypted zip for '{part}' does not contain enc.dat")
        enc_zip.extractall(enc_unzip_dir)
    if not is_valid_encrypted_part(enc_file_path):
        raise ValueError(f"Encrypted payload for '{part}' is invalid")

    return enc_unzip_dir


def get_part_paths(work_dir, part):
    part_name, _ = part.rsplit(".", 1)
    enc_zip_path = os.path.join(work_dir, part_name + "_encrypted.zip")
    enc_zip_part_path = enc_zip_path + ".part"
    enc_unzip_dir = os.path.join(work_dir, part_name + "_encrypted")
    enc_file_path = os.path.join(enc_unzip_dir, "enc.dat")
    return enc_zip_path, enc_zip_part_path, enc_unzip_dir, enc_file_path


def is_valid_encrypted_part(enc_file_path):
    if not os.path.exists(enc_file_path):
        return False
    file_size = os.path.getsize(enc_file_path)
    if file_size <= 0:
        return False
    # AES-CBC ciphertext is block aligned.
    return file_size % 16 == 0


def request(method, url, params=None, data=None, stream=False, headers={}, proxies=None):
    headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    })
    resp = requests.request(
        method=method,
        url=url,
        params=params,
        verify=False,
        data=data,
        stream=stream,
        timeout=30,
        headers=headers,
        proxies=proxies
    )
    resp.raise_for_status()
    return resp
