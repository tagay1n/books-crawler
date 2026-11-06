"""Publish acquired Common Crawl PDFs to Yandex Disk with MD5 deduplication."""

import os

from .common_crawl_utils import _runtime, _load_index, _dump_index


def upload():
    from monocorpus_models import Document, Session
    from sqlalchemy import select
    from yadisk_client import YaDisk

    runtime = _runtime()
    config = runtime.settings.source_options['yandex']['disk']
    target = config.get('target_dir', '/НейроТатарлар/kitaplar/common_crawl').rstrip('/')
    index = _load_index()
    with Session() as session:
        known = set(session.scalars(select(Document.md5)))
    seen = set(known)
    with YaDisk(config['oauth_token']) as client:
        for key, doc in index.items():
            runtime.budget.check()
            if doc.get('uploaded') or not doc.get('md5') or doc['md5'] in seen:
                runtime.summary['skipped'] += 1
                continue
            local = doc.get('path_to_file')
            if not local or not os.path.isfile(local):
                continue
            runtime.budget.start_item()
            client.upload(local, f'{target}/{os.path.basename(local)}', overwrite=True)
            doc['uploaded'] = True
            seen.add(doc['md5'])
            runtime.summary['published'] += 1
            _dump_index(index)
            # Preserve the legacy upload workflow, deleting only after a checkpoint.
            os.remove(local)
