from utils import _load_index, _dump_index
from monocorpus_models import Document, Session
from sqlalchemy import select
from yadisk_client import YaDisk, ConflictResolution
import os
from rich.progress import track

token = "<<SET ME>>>"
upload_dir = "/НейроТатарлар/kitaplar/common_crawl"


def upload():
    original_index = _load_index()
    try:
        index = _dedup(original_index)
        not_uploaded_docs = {k: v for k,v in index.items() if not v.get('uploaded', False)}
        print(f"About to upload {len(not_uploaded_docs)} docs")
        with YaDisk(token) as ya_client:
            for _, doc in track(not_uploaded_docs.items(), "Uploading docs..."):
                _upload_doc(ya_client, doc['path_to_file'])
                doc['uploaded'] = True
                print(f"Doc {doc['md5']} uploaded")
                _dump_index(original_index)
                exit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        _dump_index(original_index)
            

def _upload_doc(ya_client, path_to_pdf):
    remote_path, _ = ya_client.upload_or_replace(
        path_to_pdf, 
        remote_dir=upload_dir,
        conflict_resolution=ConflictResolution.SKIP
    )
    res = ya_client.publish(remote_path)
    res = ya_client.get_meta(res.path, fields=['md5'])
    return res.md5
    
    
def _dedup(index):
    print("Querying all md5s")
    with Session() as gsheet_session:
        statement = select(Document.md5)
        all_md5s = gsheet_session.query(statement)
        all_md5s = set(all_md5s)
    
    dowloaded_docs_idx =  {k: v for k,v in index.items() if v.get('md5')}
    filtered_docs_idx = {k: v for k,v in dowloaded_docs_idx.items() if v['md5'] not in all_md5s}
    
    print(f"Total index {len(index)}, downloaded docs: {len(dowloaded_docs_idx)}, filtered_docs: {len(filtered_docs_idx)}")
    return filtered_docs_idx
    
