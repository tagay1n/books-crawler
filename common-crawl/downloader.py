from utils import  _get_in_workdir, _load_index, _dump_index
import os
from rich import print
import requests
import pymupdf
import pandas as pd
import hashlib
import shutil
from urllib.parse import urlparse
from rich.progress import track
import re
import datetime
from warcio.archiveiterator import ArchiveIterator


def download():
    index = _load_index()
    _dump_index(index=index, backup=True)
    try: 
        docs_to_download = [d for d in index.values() if not d.get('path_to_file', None)]
        path_to_file = _get_in_workdir("../__artifacts/common.crawl/tmp.pdf")
        slice_size = 500
        start = 0
        while True:
            slice = docs_to_download[start:start+slice_size]
            start += slice_size
            if not slice:
                break
            
            for doc in track(slice, "Downlading document..."):
                print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
                if _download_direct_pdf(doc['url'], path_to_file) and check_pdf(path_to_file):
                    pass
                elif _fetch_record_from_offset(doc['file_path'], doc['url'], doc['offset'], path_to_file) and check_pdf(path_to_file):
                    pass
                else:
                    print(f"Could not download doc from any of resources", doc)
                    continue
                doc['md5'] = _calculate_md5(path_to_file)
                doc['path_to_file'] = _move_file(path_to_file, doc['md5'], doc['url'], doc['script'])
                print(f"Saved doc '{doc['md5']}' to '{doc['path_to_file']}'")
                _dump_index(index=index)
             
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
        
    
def _look_for_filename_in_index(warc_url, orig_url):
    df = _get_warc(warc_url)

    exact_match = df[df['url'] == orig_url]

    if len(exact_match) == 1:
        return exact_match['warc_filename'].values[0]
    else:
        print(f"File not found in index by url {orig_url}")
        return None

    # Show a few URLs
    print(exact_match[["url"]].head())
    print(exact_match.columns.values.tolist())
    
    return False


def _fetch_record_from_offset(warc_filename, orig_url, offset, output_file):
    """
    Fetches a single WARC record from Common Crawl by offset only.
    Stops after the first record.
    """
    print(f"Trying do download doc from warc {warc_filename}")
    
    if warc_filename.endswith('.parquet'):
        warc_filename = _look_for_filename_in_index(warc_filename, orig_url)
        if not warc_filename:
            return False
    
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
    
    
def _get_warc(url):
    url = url.replace("s3://commoncrawl/", "https://data.commoncrawl.org/")
    warc_id = _get_warc_id(url)
    warcs_dir = os.path.normpath(_get_in_workdir(os.path.expanduser(f"~/.common-crawl/warcs")))
    os.makedirs(warcs_dir, exist_ok=True)
    warc_path = os.path.join(warcs_dir, f"{warc_id}.parquet")
    
    if not os.path.exists(warc_path):
        print(f"📥 Downloadin {url} ...")
        df = pd.read_parquet(url)
        df.to_parquet(warc_path)   # Save locally
    else:
        print(f"📂 Using cached {warc_path}")
        df = pd.read_parquet(warc_path)
    return df
    
    
def _get_warc_id(url):
    match = re.search(r"(CC-MAIN-\d{4}-\d{2})", url)
    if match:
        return match.group(1)
    else:
        raise ValueError(f"Could not parse warc id from url {url}")

        
def check_pdf(path_to_file):
    with pymupdf.open(path_to_file) as pdf_file:
        for _ in pdf_file:
            pass
        
        # not the best way but should work
        if (not pdf_file.can_save_incrementally) or pdf_file.is_repaired:
            print(f"Document {path_to_file} seems to be broken")
            return False
    return True
       
    
def _download_direct_pdf(url, path_to_file):
    print(f"Trying do download doc by url {url}")
    try: 
        response = requests.get(url, timeout=3, stream=True)
        
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