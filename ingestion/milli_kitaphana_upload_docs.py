"""Uploads PDFs to Yandex Disk and stores upstream metadata in PostgreSQL."""

import posixpath
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB
from .database import transaction

from yadisk_client import YaDisk, ConflictResolution


def require_publication_config(config):
    values = [config.get('database_url'),
              config.get('yandex', {}).get('disk', {}).get('oauth_token'),
              config.get('yandex', {}).get('disk', {}).get('target_dir')]
    if any(not isinstance(value, str) or not value.strip() or value == '<SET ME>' for value in values):
        raise ValueError('Configure Milli database_url, yandex.disk.oauth_token and target_dir')


def publication_complete(data, key, sha256):
    steps = data.get('publications', {}).get(key, {})
    return steps.get('sha256') == sha256 and bool(steps.get('yandex') and steps.get('metadata'))


def publish_books(settings, data, directory, save, summary, budget, *, require_s3=False):
    """Checkpoint Yandex and metadata separately; run requires the S3 receipt first."""
    from pathlib import Path
    from . import publication
    from .core import file_digests
    from .milli_kitaphana_decrypt import _calculate_md5, _upstream_metadata
    from .network import BudgetStop
    from .state import now

    config = settings.source_options
    require_publication_config(config)
    for artifact in publication.artifacts(data, directory):
        key = artifact.record
        if publication_complete(data, key, artifact.sha256):
            continue
        if require_s3 and not publication.completed(data, artifact, settings):
            continue
        try:
            budget.start_item()
            path = Path(artifact.path)
            if not path.is_file() or file_digests(path)[0] != artifact.sha256:
                raise ValueError('Missing or changed finalized PDF; restore it before publication')
            item = data['records'][key]['observations'][-1]['metadata']
            steps = data.setdefault('publications', {}).setdefault(key, {})
            if steps.get('sha256') != artifact.sha256:
                steps.clear()
                steps['sha256'] = artifact.sha256
            if not steps.get('yandex'):
                upload_doc(str(path), config, item.get('downloaded') == 'limited')
                steps['yandex'] = now()
                save()
                summary['yandex_published'] = summary.get('yandex_published', 0) + 1
            budget.check()
            if not steps.get('metadata'):
                persist_upstream_metadata(_calculate_md5(path), _upstream_metadata(item), config['database_url'])
                steps['metadata'] = now()
                save()
                summary['upstream_metadata_saved'] = summary.get('upstream_metadata_saved', 0) + 1
            if not item.get('decrypted'):
                item['decrypted'] = True
                save()
        except BudgetStop:
            raise
        except Exception as error:
            # Destination client exceptions can include credentials or signed URLs.
            summary.setdefault('errors', []).append({'stage': 'yandex-metadata', 'record': key,
                                                     'error': type(error).__name__})


UPSTREAM_METADATA_INSERT = """
    INSERT INTO monocorpus.library_upstream_metadata (md5, payload_json)
    VALUES (:md5, :payload_json)
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

    with transaction(database_url) as connection:
        statement = text(UPSTREAM_METADATA_INSERT).bindparams(bindparam("payload_json", type_=JSONB))
        connection.execute(statement, {"md5":md5, "payload_json":payload_json})
