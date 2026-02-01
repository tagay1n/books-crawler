"""Uploads downloaded Common Crawl PDFs to Yandex Disk, deduplicates by md5 using the database, and marks index entries as uploaded."""

from utils import _load_index, _dump_index
from monocorpus_models import Document, Session
from sqlalchemy import select
from yadisk_client import YaDisk, ConflictResolution
import os
from rich.progress import track

token = "<<set me>>"
upload_dir = "/НейроТатарлар/kitaplar/common_crawl"


def upload():
    original_index = _load_index()
    _dump_index(index=original_index, backup=True)
    index = _dedup(original_index)
    not_uploaded_docs = {k: v for k,v in index.items() if not v.get('uploaded', False)}
    print(f"About to upload {len(not_uploaded_docs)} docs")
    with YaDisk(token) as ya_client:
        try:
            for idx, (_, doc) in track(list(enumerate(not_uploaded_docs.items())), "Uploading docs..."):
                if not (local_path := doc.get('path_to_file')):
                    continue
                
                if os.path.exists(local_path):
                    print(f"Uploading {doc['md5']}")
                    _upload_doc(ya_client, local_path)
                doc['uploaded'] = True
                if idx % 10 == 0:
                    _dump_index(index=original_index)
        except Exception as e:
            print(f"Error: {e}")
        finally:
            _dump_index(original_index)
            _dump_index(original_index, backup=True)

            

def _upload_doc(ya_client, path_to_pdf):
    file_name = os.path.basename(path_to_pdf).split('/')[-1]
    remote_path = f"{upload_dir}/{file_name}"
    _ = ya_client.upload(
        path_to_pdf, 
        remote_path,
        overwrite=True
    )
    os.remove(path_to_pdf)
    

def _dedup(index):
    print("Querying all md5s")
    with Session() as gsheet_session:
        statement = select(Document.md5)
        all_md5s = gsheet_session.query(statement)
        all_md5s = set(all_md5s)
    
    # keep only with md5
    dowloaded_docs_idx =  {k: v for k,v in index.items() if v.get('md5')}
    # keep only not in yandex disk
    filtered_docs_idx = {k: v for k,v in dowloaded_docs_idx.items() if v['md5'] not in all_md5s}
    _md5s_to_urns = {v['md5']: k for k, v in filtered_docs_idx.items()}
    # remove duplicates in the downloaded docs
    if len(_md5s_to_urns) != len(dowloaded_docs_idx):
        print(f"There are duplicates in downloaded files: {len(_md5s_to_urns)} -- {len(dowloaded_docs_idx)}")
        filtered_docs_idx = {urn: filtered_docs_idx[urn] for _, urn in _md5s_to_urns.items()}
    
    print(f"Total index {len(index)}, downloaded docs: {len(dowloaded_docs_idx)}, filtered_docs: {len(filtered_docs_idx)}")
    return filtered_docs_idx
    
