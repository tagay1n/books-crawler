"""Shared helpers for Milli Kitaphana: index paths, file locking, list management, and HTTP request wrappers."""

import json
import os
import shutil
import time
from contextlib import contextmanager

import requests
import yaml
import zipfile


def get_in_workdir(file):
    """Return file in the current directory where script file is located"""
    return os.path.join(os.path.dirname(__file__), file)


index_file_name = "books-index.json"
HOST = "https://kitap.tatar.ru"
base_dir = get_in_workdir(os.path.join("../__artifacts/milli.kitaphana"))


def read_config():
    # read config file from the same directory
    with open(get_in_workdir("config.yaml"), "r") as f:
        return yaml.safe_load(f)
    
    
def load_index_file(index_file=None):
    if not index_file:
        index_file = get_index_file_loc()
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            books = json.load(f)
    else:
        books = {}
    return books
        
        
def get_index_file_loc():
    index_dir = get_in_workdir("../__artifacts/milli.kitaphana")
    os.makedirs(index_dir, exist_ok=True)
    return os.path.join(index_dir, index_file_name)


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


def get_not_downloaded_docs(index, limited_only):
    not_downloaded_docs = []
    for card_path, meta in index.items():
        if meta.get("broken", False):
            continue

        if not limited_only:
            if meta.get("downloaded") is None:
                not_downloaded_docs.append((card_path, meta))
            continue

        if meta.get("downloaded") == "limited" and meta.get("access") != "open":
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
    part_name, _ = part.split(".")
    enc_zip_path = os.path.join(work_dir, part_name + "_encrypted.zip")
    enc_unzip_dir = os.path.join(work_dir, part_name + "_encrypted")

    url = HOST + context['meta']["format_url"].format(url=part)
    # download the encrypted zip file
    with request(method="GET", url=url, stream=True, proxies=context.get('proxies')) as response:
        os.makedirs(work_dir, exist_ok=True)
        # save the encrypted zip file
        with open(enc_zip_path, "wb") as enc_zip:
            task = context["progress"].download(part)
            total_size = 0
            for chunk in response.iter_content(chunk_size=1024):
                enc_zip.write(chunk)
                chunk_len = len(chunk)
                total_size += chunk_len
                context['progress']._aux.update(task, advance=chunk_len)
            context['progress']._aux.update(
                task, description=f"Downloaded {part}")
            context['progress']._aux.stop_task(task)

    # unzip the encrypted zip file
    with zipfile.ZipFile(enc_zip_path, 'r') as enc_zip:
        enc_zip.extractall(enc_unzip_dir)

    return enc_unzip_dir


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
