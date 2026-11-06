"""Shared helpers for Milli Kitaphana: database indexes, worker selections, and HTTP request wrappers."""
from .runtime_config import option as operational_option

import copy
import os
from contextlib import contextmanager
from contextvars import ContextVar

import requests
import zipfile

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning)


def get_in_workdir(file):
    """Return normalized absolute path under the milli_kitaphana directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.normpath(os.path.join(script_dir, file)))


RUNTIME = None


def require_runtime():
    if RUNTIME is None:
        raise RuntimeError("Milli helpers require the unified runtime")
    return RUNTIME


_http_session = ContextVar("milli_kitaphana_http_session", default=None)


@contextmanager
def request_session():
    """Reuse connections during one document's audit without sharing threads."""
    with requests.Session() as session:
        token = _http_session.set(session)
        try:
            yield session
        finally:
            _http_session.reset(token)


def read_config():
    return require_runtime().config


def get_index_file_loc():
    """Logical global index identifier, retained for provider helper callers."""
    return 'books'


def get_list_file_loc(name):
    if not name or '/' in str(name) or '\\' in str(name):
        raise ValueError('Worker selection must be a name, not a file path')
    name = str(name).removesuffix('.json')
    return name if name.startswith('selection:') else 'selection:' + name


def load_index_file(index_file=None):
    from .milli_kitaphana import records
    runtime = require_runtime()
    with runtime.state_lock:
        index = copy.deepcopy(records(runtime.manifest))
        if index_file is None or index_file == 'books':
            return index
        key = get_list_file_loc(index_file)
        if key not in runtime.manifest.data:
            raise ValueError('Unknown Postgres worker selection; run split first')
        return {k:index[k] for k in runtime.manifest.data[key] if k in index}


def dump_index(idx, index_file=None):
    runtime = require_runtime()
    with runtime.state_lock:
        manifest = runtime.manifest
        if index_file is not None and index_file != 'books':
            manifest.data[get_list_file_loc(index_file)] = list(idx)
        else:
            for key, item in idx.items():
                manifest.observe({**item, 'url': item.get('url') or operational_option('milli_kitaphana_utils', 'host') + key}, [], record_key=key, persist=False)
            for key in manifest.data['records'].keys() - idx.keys():
                del manifest.data['records'][key]
        manifest.checkpoint()


def get_not_downloaded_docs(index, limited):
    not_downloaded_docs = []
    for card_path, meta in index.items():
        if meta.get("record_type") == "collection":
            continue
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
def open_lock(index_file=None, wait_seconds=None):
    """The source's Postgres lease covers writers; serialize provider workers."""
    runtime = require_runtime()
    with runtime.state_lock:
        from .database import assert_ownership
        assert_ownership(owner=runtime.budget.database_owner)
        yield


def download_part(context, part):
    work_dir = context["work_dir"]
    enc_zip_path, enc_zip_part_path, enc_unzip_dir, enc_file_path = get_part_paths(work_dir, part)

    url = operational_option('milli_kitaphana_utils', 'host') + context['meta']["format_url"].format(url=part)
    # Offline finalization uses the verified local encrypted payload.
    if require_runtime().offline:
        if not is_valid_encrypted_part(enc_file_path):
            raise ValueError("Missing local encrypted metadata; run download first")
        return enc_unzip_dir
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
    return require_runtime().request(method, url, params=params, data=data, stream=stream, headers=headers, proxies=proxies)
