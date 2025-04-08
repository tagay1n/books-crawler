import json
import os.path
import re

from monocorpus_models import Session, Document
from rich.progress import track
from sqlalchemy import text
from yadisk_client import YaDisk, ConflictResolution
from rich import print

REMOTE_DIR = "/НейроТатарлар/kitaplar/_все книги/милли.китапханә"


def upload_docs(path_to_pdf, path_to_texts_zip, path_to_metadata, config, is_limited):
    remote_dir = os.path.join(REMOTE_DIR, "limited" if is_limited else "full", os.path.splitext(os.path.basename(path_to_pdf))[0][:100])
    client = YaDisk(config['yandex.oauth_token'])

    for f in [path_to_pdf, path_to_texts_zip, path_to_metadata]:
        if not f:
            continue
        remote_path, _ = client.upload_or_replace(
            f, 
            remote_dir=remote_dir,
            conflict_resolution=ConflictResolution.SKIP
        )
        client.publish(remote_path)

