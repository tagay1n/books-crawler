"""Uploads PDFs to Yandex Disk and stores upstream metadata in PostgreSQL."""

import posixpath
import psycopg
from psycopg.types.json import Jsonb

from yadisk_client import YaDisk, ConflictResolution


UPSTREAM_METADATA_INSERT = """
    INSERT INTO monocorpus.library_upstream_metadata (md5, payload_json)
    VALUES (%s, %s)
"""


def upload_doc(path_to_pdf, config, is_limited):
    remote_dir = posixpath.join(config['yandex']['disk']['target_dir'], "limited" if is_limited else "full")
    client = YaDisk(config['yandex']['disk']['oauth_token'])

    _, _ = client.upload_or_replace(
        path_to_pdf, 
        remote_dir=remote_dir,
        conflict_resolution=ConflictResolution.REPLACE_IF_DIFFERENT
    )
    # res = client.publish(remote_path)
    # res = client.get_meta(res.path, fields=['md5'])
    # return res.md5


def persist_upstream_metadata(md5, payload_json, database_url):
    """Insert one upstream metadata record without reading or updating existing rows."""
    database_url = str(database_url or "").strip()
    if not database_url or database_url == "<SET ME>":
        raise ValueError("database_url is required")

    with psycopg.connect(database_url) as connection:
        connection.execute(UPSTREAM_METADATA_INSERT, (md5, Jsonb(payload_json)))
