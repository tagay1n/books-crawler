from utils import  _get_in_workdir, _load_index, _dump_index
import os
from rich import print
import requests
import pymupdf
import pandas as pd
import hashlib
import shutil
from urllib.parse import urlparse, unquote
from rich.progress import track
import re
import datetime
from warcio.archiveiterator import ArchiveIterator


def download():
    # download_directly()
    download_cc()
    
    
def download_cc():
    index = _load_index()
    _dump_index(index=index, backup=True)
    try: 
        _augment(index)
        docs_to_download = [d for d in index.values() if not d.get('path_to_file', None)]
        print(f"About to download {len(docs_to_download)} of {len(index)} documents")
        path_to_file = _get_in_workdir("../__artifacts/common.crawl/tmp.pdf")

        for doc in docs_to_download:
                warc_file = doc['file_path'] if not doc['file_path'].endswith('.parquet') else doc.get('augmented_file_path', None)
                if not warc_file:
                    continue
                print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
                if _fetch_record_from_offset(warc_file, doc['offset'], path_to_file) and check_pdf(path_to_file):
                    doc['md5'] = _calculate_md5(path_to_file)
                    doc['path_to_file'] = _move_file(path_to_file, doc['md5'], doc['url'], doc['script'])
                    print(f"Saved doc '{doc['md5']}' to '{doc['path_to_file']}'")
                    _dump_index(index=index)
                else:
                    print(f"Could not download doc from common crawl", doc)
                    continue
    except KeyboardInterrupt:
        print("Interrupting...")
    finally:
        _dump_index(index=index)


def _augment(index):
    docs_to_augment = [d for d in index.values() if (not d.get('path_to_file', None)) and (not d.get('augmented_file_path', None)) and d['file_path'].endswith('.parquet')]
    index_file_to_docs = {}
    for doc in docs_to_augment:
        warc_filename = doc['file_path'].strip()
        # url = warc_filename.replace("s3://commoncrawl/", "https://data.commoncrawl.org/")
        # warc_id = _get_warc_id(warc_filename)
        if warc_filename in index_file_to_docs:
            index_file_to_docs[warc_filename].append(doc)
        else: 
            index_file_to_docs[warc_filename] = [doc]
    
    items = index_file_to_docs.items()
    print(f"About to process {len(items)} indexes")
    for warc_filename, docs in track(items, "Downloading index files"):
        try:
            df = _get_warc(warc_filename)
            for doc in docs:
                aug_warc_filename =  _look_for_filename_in_index(doc, df)
                if aug_warc_filename:
                    doc['augmented_file_path'] = aug_warc_filename
            _dump_index(index=index)  
            del df
        except Exception as e:
            print(f"Error: {e}")
            continue

        

def download_directly():
    index = _load_index()
    _dump_index(index=index, backup=True)
    try: 
        docs_to_download = [d for d in index.values() if not d.get('path_to_file', None)]
        path_to_file = _get_in_workdir(f"../__artifacts/common.crawl/tmp.pdf")
        slice_size = 25
        start = 0
        while True:
            slice = docs_to_download[start:start+slice_size]
            start += slice_size
            if not slice:
                break
            
            for doc in track(slice, "Downlading document..."):
                print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
                if _download_direct_pdf(doc['url'], path_to_file) and check_pdf(path_to_file):
                    doc['md5'] = _calculate_md5(path_to_file)
                    doc['path_to_file'] = _move_file(path_to_file, doc['md5'], doc['url'], doc['script'])
                    print(f"Saved doc '{doc['md5']}' to '{doc['path_to_file']}'")
                    _dump_index(index=index)
                else:
                    print(f"Could not download doc directly", doc)
                    continue
    except KeyboardInterrupt:
        print("Interrupting...")
    finally:
        _dump_index(index=index)

        
def _move_file(path_to_file, md5, url, script):
    source_name = None
    if url.endswith('.pdf'):
        source_name, _ = os.path.splitext(os.path.basename(urlparse(url).path))
        source_name = source_name[:100]
    new_name = f"{md5}{f'-{source_name}' if source_name else ""}.pdf"
    target_dir = os.path.normpath(_get_in_workdir(os.path.expanduser(f"~/.common-crawl/result/{script}")))
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, new_name)
    shutil.move(path_to_file, target_path)
    return target_path

        
def _calculate_md5(file_path: str):
    """
    Calculates MD5 hash of the file

    :param file_path: path to the file
    :return: MD5 hash of the file
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(2048), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()
        
    
def _look_for_filename_in_index(doc, df):
    orig_url = doc['url']
    exact_match = df[df['url'] == orig_url.strip()]

    if len(exact_match) == 1:
        return exact_match['warc_filename'].values[0]
    elif len(exact_match) > 1:
        print(f"Got more than one matches by url {orig_url}")
    else:
        print(f"File not found in index by url {orig_url}")
    return None
    

def _fetch_record_from_offset(warc_filename, offset, output_file):
    """
    Fetches a single WARC record from Common Crawl by offset only.
    Stops after the first record.
    """
    print(f"Trying do download doc from warc {warc_filename}")
    
    try: 
        warc_url = warc_filename.removeprefix("s3://commoncrawl/")
        warc_url = f"https://data.commoncrawl.org/{warc_url}"

        headers = {"Range": f"bytes={offset}-"}
        resp = requests.get(warc_url, headers=headers, stream=True)
        resp.raise_for_status()

        # Iterate records from stream
        for record in ArchiveIterator(resp.raw, arc2warc=True):
            # Example: only save PDFs
            if record.http_headers and record.http_headers.get_header("Content-Type") == "application/pdf":
                with open(output_file, "wb") as f:
                    f.write(record.content_stream().read())
                print(f"💾 Saved {output_file}")
                return True
            break   # <- stop after first record
    except Exception as e:
        print(f"Error: {e}")
    return False
    
    
def _get_warc(warc_filename, chunk_size: int = 8192):
    warcs_dir = os.path.normpath(_get_in_workdir(os.path.expanduser(f"~/.common-crawl/warcs")))
    os.makedirs(warcs_dir, exist_ok=True)
    warc_path = os.path.join(warcs_dir, warc_filename.replace('/', '_'))
    
    if not os.path.exists(warc_path):
        https_url = warc_filename.replace("s3://commoncrawl/", "https://data.commoncrawl.org/")
        tmp_warc_path = f"{warc_path}.part"
        # Stream download to avoid loading entire file into memory
        with requests.get(https_url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("Content-Length", 0))
            with open(tmp_warc_path, "wb") as f:
                # Use track to visualize progress
                for chunk in track(
                    r.iter_content(chunk_size=chunk_size),
                    description=f"Downloading '{https_url[-100:]}'",
                    total=total_size // chunk_size if total_size else None,
                ):
                    if chunk:  # filter out keep-alive chunks
                        f.write(chunk)
        shutil.move(tmp_warc_path, warc_path)
    else:
        print(f"📂 Using cached {warc_path}")
    return pd.read_parquet(warc_path)
    
    
def _get_warc_id(url):
    match = re.search(r"(CC-MAIN-\d{4}-\d{2})", url)
    if match:
        return match.group(1)
    else:
        raise ValueError(f"Could not parse warc id from url {url}")

        
def check_pdf(path_to_file):
    try: 
        with pymupdf.open(path_to_file) as pdf_file:
            for _ in pdf_file:
                pass
            
            # not the best way but should work
            # if (not pdf_file.can_save_incrementally) or pdf_file.is_repaired:
            #     print(f"Document {path_to_file} seems to be broken")
            #     return False
    except Exception:
        return False
    return True
       
    
def _download_direct_pdf(url, path_to_file):
    print(f"Trying do download doc by url {url}")
    try: 
        response = requests.get(url, timeout=3, stream=True, verify=False)
        
        if response.status_code == 200:
            with open(path_to_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"File download by url '{url}'")
            return True
        else:
            print(f"⚠️ File not found or not a PDF. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
    
    return False