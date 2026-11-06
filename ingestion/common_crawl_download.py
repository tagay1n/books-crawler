"""Acquire FinePDFs originals directly, then fall back to Common Crawl WARC offsets."""

import hashlib
import os
from pathlib import Path
import shutil
from urllib.parse import urlparse

import pandas as pd
import pymupdf
from warcio.archiveiterator import ArchiveIterator

from .common_crawl_utils import _runtime, _get_in_workdir, _load_index, _dump_index, configured_path, write_stream
from .network import BudgetStop


def download():
    runtime = _runtime()
    index = _load_index()
    selected = []
    temporary = _get_in_workdir('tmp.pdf')
    try:
        for key, doc in index.items():
            if doc.get('uploaded') or doc.get('path_to_file'):
                runtime.summary['skipped'] += 1
                continue
            if len(selected) >= runtime.settings.max_items:
                break
            runtime.budget.start_item()
            selected.append((key, doc))
            if _download_direct_pdf(doc['url'], temporary) and check_pdf(temporary):
                _commit_download(doc, temporary, index)
        pending = [(key, doc) for key, doc in selected if not doc.get('path_to_file')]
        _augment(index, [doc for _, doc in pending])
        for key, doc in pending:
            runtime.budget.check()
            warc_file = doc['file_path'] if not doc['file_path'].endswith('.parquet') else doc.get('augmented_file_path')
            if warc_file and _fetch_record_from_offset(warc_file, doc['offset'], temporary) and check_pdf(temporary):
                _commit_download(doc, temporary, index)
            else:
                runtime.summary['errors'].append({'stage': 'download', 'record': key, 'error': 'Direct and WARC PDF acquisition failed'})
    finally:
        Path(temporary).unlink(missing_ok=True)
        _dump_index(index)


def _commit_download(doc, temporary, index):
    doc['md5'] = _calculate_md5(temporary)
    doc['path_to_file'] = _move_file(temporary, doc['md5'], doc['url'], doc['script'])
    _runtime().summary['downloaded'] += 1
    _dump_index(index)


def _augment(index, docs):
    grouped = {}
    for doc in docs:
        if not doc.get('augmented_file_path') and doc['file_path'].endswith('.parquet'):
            grouped.setdefault(doc['file_path'].strip(), []).append(doc)
    for filename, items in grouped.items():
        _runtime().budget.check()
        try:
            frame = _get_warc(filename)
            for doc in items:
                match = _look_for_filename_in_index(doc, frame)
                if match:
                    doc['augmented_file_path'] = match
            _dump_index(index)
        except BudgetStop:
            raise
        except Exception:
            # Individual records still get a structured failure if no WARC was found.
            continue


def _move_file(path_to_file, md5, url, script):
    from .core import check_space

    if script not in {'cyrl', 'latn'}:
        raise ValueError('Unsupported Common Crawl script')
    source_name = None
    if url.endswith('.pdf'):
        source_name = os.path.splitext(os.path.basename(urlparse(url).path))[0][:100]
    new_name = f"{md5}{'-' + source_name if source_name else ''}.pdf"
    target_dir = configured_path('result_dir', '~/.common-crawl/result') / script
    target_dir.mkdir(parents=True, exist_ok=True)
    check_space(target_dir, _runtime().settings.disk_reserve_bytes, Path(path_to_file).stat().st_size)
    target_path = target_dir / new_name
    shutil.move(path_to_file, target_path)
    return str(target_path)


def _calculate_md5(file_path):
    digest = hashlib.md5()
    with open(file_path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _look_for_filename_in_index(doc, frame):
    matches = frame[frame['url'] == doc['url'].strip()]
    return None if matches.empty else matches['warc_filename'].values[0]


def _fetch_record_from_offset(warc_filename, offset, output_file):
    runtime = _runtime()
    url = 'https://data.commoncrawl.org/' + warc_filename.removeprefix('s3://commoncrawl/')

    def fetch():
        with runtime.http.get(url, headers={'Range': f'bytes={offset}-'}) as response:
            if response.status_code != 206:
                raise ValueError('Common Crawl did not honor the WARC byte range')
            for record in ArchiveIterator(response.raw, arc2warc=True):
                if record.http_headers:
                    write_stream(record.content_stream(), output_file)
                    return True
                break
        return False
    try:
        return runtime.http.retry(fetch)
    except BudgetStop:
        raise
    except Exception:
        return False


def _get_warc(warc_filename):
    runtime = _runtime()
    directory = configured_path('cache_dir', '~/.common-crawl/warcs')
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / warc_filename.replace('/', '_')
    if not path.exists():
        url = warc_filename.replace('s3://commoncrawl/', 'https://data.commoncrawl.org/')
        temporary = Path(str(path) + '.part')
        def fetch():
            with runtime.http.get(url) as response:
                write_stream(response.raw, temporary)
            temporary.replace(path)
        try:
            runtime.http.retry(fetch)
        finally:
            temporary.unlink(missing_ok=True)
    return pd.read_parquet(path)


def check_pdf(path_to_file):
    try:
        with pymupdf.open(path_to_file) as document:
            if document.page_count == 0 or not document.is_pdf:
                return False
            for _ in document:
                _runtime().budget.check()
    except BudgetStop:
        raise
    except Exception:
        return False
    return True


def _download_direct_pdf(url, path_to_file):
    runtime = _runtime()
    def fetch():
        with runtime.http.get(url) as response:
            if response.status_code != 200:
                return False
            write_stream(response.raw, path_to_file)
        return True
    try:
        return runtime.http.retry(fetch)
    except BudgetStop:
        raise
    except Exception:
        return False
