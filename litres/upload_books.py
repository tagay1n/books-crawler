import json
import os.path

from monocorpus_models import Session, Document
from rich.progress import track
from yadisk_client import YaDisk

from utils import get_in_workdir, read_config

REMOTE_DIR = "/НейроТатарлар/kitaplar/_все книги/litres"


def upload_pdfs():
    _index_file = get_in_workdir("../__artifacts/litres/books-index.json")
    with open(_index_file, "r") as f:
        _all_docs = json.load(f)

    config = read_config()
    client = YaDisk(config['yandex.oauth_token'])
    session = Session()

    for doc in track([d for d in _all_docs.values() if d['content_type'] == 'pdf'],
                     description="Uploading documents"):
        file = doc['pdf_file']
        remote_path, md5 = client.upload_or_replace(file, remote_dir=REMOTE_DIR)
        client.publish(remote_path, fields=['public_key', 'public_url'])

        meta = client.get_meta(remote_path, fields=['public_key', 'public_url', 'resource_id'])
        ya_public_url = meta['public_url']
        ya_public_key = meta['public_key']
        ya_resource_id = meta['resource_id']

        _metadata = doc['metadata']
        document = Document(
            md5=md5,
            mime_type='application/pdf',
            names=os.path.basename(file),
            ocr='required',
            ya_public_url=ya_public_url,
            ya_public_key=ya_public_key,
            ya_resource_id=ya_resource_id,
            publisher=_metadata.get('publisher'),
            author=doc.get('author') or _metadata.get('created_by'),
            title=doc.get('title'),
            age_limit=_metadata.get('age_limit'),
            isbn=_metadata.get('isbn'),
            publish_date=_metadata.get('publish_date'),
            summary=_metadata.get('summary'),
            sources=doc.get('url'),
        )
        session.upsert(document)
        print(f"Document uploaded: {md5}")
