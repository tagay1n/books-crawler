"""Resumable Milli publication with an MD5 gate before any upload."""
import contextlib
import posixpath
import shutil
import tempfile
from pathlib import Path

from yadisk_client import YaDisk, ConflictResolution

from .files import file_digests
from .network import BudgetStop
from .state import now
from . import milli_kitaphana_catalog as catalog


def require_publication_config(config):
    values = [config.get('database_url'), config.get('yandex', {}).get('disk', {}).get('oauth_token'),
              config.get('yandex', {}).get('disk', {}).get('target_dir')]
    if any(not isinstance(value, str) or not value.strip() or value == '<SET ME>' for value in values):
        raise ValueError('Configure Milli database_url, yandex.disk.oauth_token and target_dir')


def publication_complete(data, key, sha256):
    steps = data.get('publications', {}).get(key, {})
    return steps.get('sha256') == sha256 and steps.get('status') in {'complete', 'duplicate'}


def restore_inputs(data, directory):
    """Terminal records stay terminal even when local artifacts have been removed."""
    for key, record in data['records'].items():
        item = record['observations'][-1]['metadata']
        output = item.get('finalized', {})
        if publication_complete(data, key, output.get('sha256')):
            continue
        if item.get('decrypted') and data.get('publications', {}).get(key, {}).get('status') != 'pending':
            # Legacy imports used this flag for completed publication. Missing
            # runner-local inputs must not restart those completed acquisitions.
            continue
        if (output.get('path') and Path(output['path']).is_file()
                and file_digests(Path(output['path']))[0] == output.get('sha256')):
            continue
        if item.get('downloaded') != 'full':
            continue
        paths = [Path(p['enc_unzip_dir']) / 'enc.dat' for p in item.get('enc_part_paths', [])]
        if item.get('download_code'):
            paths.append(directory / item['download_code'] / 'part0_encrypted/enc.dat')
        item.pop('finalized', None)
        item['decrypted'] = False
        if not paths or any(not path.is_file() for path in paths):
            for name in ('downloaded', 'enc_part_paths', 'imported_acquisition_complete'):
                item.pop(name, None)


def upload_doc(path_to_pdf, config, is_limited, *, md5=None):
    """Use a stable MD5 filename; repeated uploads reconcile the same remote path."""
    digest = md5 or file_digests(Path(path_to_pdf))[1]
    remote_dir = posixpath.join(config['yandex']['disk']['target_dir'], 'limited' if is_limited else 'full')
    with tempfile.TemporaryDirectory(prefix='milli-upload-') as temp, YaDisk(config['yandex']['disk']['oauth_token']) as client:
        canonical = Path(temp) / (digest + '.pdf')
        shutil.copyfile(path_to_pdf, canonical)
        remote_path, remote_md5 = client.upload_or_replace(str(canonical), remote_dir, ConflictResolution.REPLACE_IF_DIFFERENT)
        if remote_md5 != digest:
            raise ValueError('Yandex upload MD5 does not match local PDF')
        client.publish(remote_path)
        info = client.get_meta(remote_path, fields=['md5', 'resource_id', 'public_key', 'public_url'])
        if info['md5'] != digest or not all(info[key] for key in ('resource_id', 'public_key', 'public_url')):
            raise ValueError('Yandex upload metadata is incomplete')
        return {'path': remote_path.removeprefix('disk:'), **{key: info[key] for key in ('resource_id', 'public_key', 'public_url')}}


def upload_s3(client, settings, path, md5, sha256, size):
    """Reconcile an interrupted upload with an exact-key HEAD request."""
    from botocore.exceptions import ClientError
    bucket, key = settings.s3['bucket'], md5 + '.pdf'
    matches = False
    try:
        info = client.head_object(Bucket=bucket, Key=key)
        matches = info['ContentLength'] == size and info.get('Metadata', {}).get('md5') == md5
    except ClientError as error:
        if str(error.response['Error']['Code']) not in {'404', 'NoSuchKey', 'NotFound'}:
            raise
    if not matches:
        client.upload_file(str(path), bucket, key, ExtraArgs={'ContentType': 'application/pdf', 'Metadata': {'md5': md5, 'sha256': sha256}})
    info = client.head_object(Bucket=bucket, Key=key)
    if info['ContentLength'] != size or info.get('Metadata', {}).get('md5') != md5:
        raise ValueError('S3 upload verification failed')
    return {'url': f"{client.meta.endpoint_url.rstrip('/')}/{bucket}/{key}", 'size': size,
            'etag': info.get('ETag'), 'bucket': bucket, 'key': key}


def publish_books(settings, data, directory, save, summary, budget, *, target='all'):
    from .publication import create_client
    from .milli_kitaphana_decrypt import _upstream_metadata
    config = settings.source_options
    require_publication_config(config)
    with contextlib.ExitStack() as resources:
        client = None
        for key, record in data['records'].items():
            item = record['observations'][-1]['metadata']
            output = item.get('finalized')
            if not output or publication_complete(data, key, output.get('sha256')):
                continue
            try:
                budget.check()
                path = Path(output['path'])
                steps = data.setdefault('publications', {}).setdefault(key, {})
                # The catalog may have committed before progress was saved and
                # runner-local artifacts disappeared. Reconcile recorded hashes.
                if steps.get('sha256') == output['sha256'] and steps.get('md5'):
                    if catalog.known_document(config['database_url'], steps['md5']):
                        budget.start_item()
                        own = catalog.registered_here(config['database_url'], steps['md5'], steps)
                        steps.update(status='complete' if own else 'duplicate', finished_at=now())
                        item['decrypted'] = True
                        save()
                        counter = 'catalog_reconciled' if own else 'duplicates'
                        summary[counter] = summary.get(counter, 0) + 1
                        continue
                if not path.is_file():
                    summary['awaiting_inputs'] = summary.get('awaiting_inputs', 0) + 1
                    continue
                budget.start_item()
                sha, md5, size = file_digests(path)
                if sha != output['sha256']:
                    raise ValueError('Finalized PDF hash has changed')
                if steps.get('sha256') != sha:
                    steps.clear()
                steps.update(sha256=sha, md5=md5, status='pending')
                save()
                # Always consult the catalog before creating any remote object.
                if catalog.known_document(config['database_url'], md5):
                    own = catalog.registered_here(config['database_url'], md5, steps)
                    steps.update(status='complete' if own else 'duplicate', finished_at=now())
                    item['decrypted'] = True
                    save()
                    counter = 'catalog_reconciled' if own else 'duplicates'
                    summary[counter] = summary.get(counter, 0) + 1
                    continue
                if client is None:
                    client = create_client(settings)
                    resources.callback(client.close)
                budget.check()
                if target in {'all', 's3'} and not isinstance(steps.get('s3'), dict):
                    steps['s3'] = upload_s3(client, settings, path, md5, sha, size)
                    from .publication import PublishableArtifact, receipt_key, destination
                    artifact = PublishableArtifact(key, output.get('id', output['path']), path, sha,
                                                  {'observation_id': record['observations'][-1]['id'], 'result': output})
                    data.setdefault('s3_publications', {})[receipt_key(artifact)] = {
                        'destination': destination(settings), 'sha256': sha, 'record': key,
                        'artifact': artifact.identity, 'provenance': artifact.provenance,
                        'objects': [{'key': steps['s3']['key'], 'sha256': sha, 'size': size}],
                        'completed_at': now()}
                    save()
                    summary['s3_published'] = summary.get('s3_published', 0) + 1
                budget.check()
                if target in {'all', 'yandex'} and not isinstance(steps.get('yandex'), dict):
                    steps['yandex'] = upload_doc(str(path), config, False, md5=md5)
                    save()
                    summary['yandex_published'] = summary.get('yandex_published', 0) + 1
                if not (isinstance(steps.get('s3'), dict) and isinstance(steps.get('yandex'), dict)):
                    continue
                metadata = _upstream_metadata(item)
                budget.check()
                created = catalog.register_document(config['database_url'], md5, steps, metadata)
                steps.update(status='complete' if created else 'duplicate', finished_at=now())
                item['decrypted'] = True
                save()
                counter = 'catalog_registered' if created else 'duplicates'
                summary[counter] = summary.get(counter, 0) + 1
                if created:
                    summary['upstream_metadata_saved'] = summary.get('upstream_metadata_saved', 0) + 1
            except BudgetStop:
                raise
            except Exception as error:
                summary.setdefault('errors', []).append({'stage': 'publication', 'record': key, 'error': type(error).__name__})
