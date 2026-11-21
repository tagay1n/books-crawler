"""Resumable Milli publication with an MD5 gate before any upload."""
import contextlib
import posixpath
import shutil
import tempfile
from pathlib import Path

from yadisk_client import YaDisk, ConflictResolution

from .files import file_digests
from .catalog_operations import DocumentOperationBusy, document_operation
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
        if item.get('access') == 'limited' or item.get('downloaded') == 'limited':
            continue
        if publication_complete(data, key, output.get('sha256')):
            continue
        if item.get('decrypted') and data.get('publications', {}).get(key, {}).get('status') != 'pending':
            # Legacy imports used this flag for completed publication. Missing
            # runner-local inputs must not restart those completed acquisitions.
            continue
        if (output.get('complete') is True and output.get('path') and Path(output['path']).is_file()
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
        info = client.get_meta(remote_path, fields=['md5'])
        if info['md5'] != digest:
            raise ValueError('Yandex upload MD5 verification failed')
        return {'path': remote_path.removeprefix('disk:')}


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


def publish_books(settings, data, directory, save, summary, budget, *, target='all', log=None, record_keys=None):
    from .publication import PublishableArtifact, create_client, destination, receipt_key
    from .milli_kitaphana_decrypt import _upstream_metadata
    config = settings.source_options
    emit = log or (lambda *args, **kwargs: None)
    require_publication_config(config)
    with contextlib.ExitStack() as resources:
        client = None
        receipt_destination = None
        selected = data['records'] if record_keys is None else record_keys
        for key in selected:
            record = data['records'][key]
            item = record['observations'][-1]['metadata']
            output = item.get('finalized')
            if item.get('access') == 'limited' or item.get('downloaded') == 'limited':
                if output:
                    steps = data.setdefault('publications', {}).setdefault(key, {})
                    if steps.get('status') != 'not_full':
                        steps.update(status='not_full', sha256=output.get('sha256'))
                        save()
                summary['not_full_skipped'] = summary.get('not_full_skipped', 0) + 1
                continue
            if not output or publication_complete(data, key, output.get('sha256')):
                continue
            emit('publication_started', record=key, target=target)
            try:
                budget.check()
                path = Path(output['path'])
                steps = data.setdefault('publications', {}).setdefault(key, {})
                if not path.is_file():
                    # Catalog commit can precede the progress checkpoint and
                    # loss of runner-local files. Reconcile under the same lock.
                    if steps.get('sha256') == output['sha256'] and steps.get('md5'):
                        with document_operation(config['database_url'], steps['md5']) as operation:
                            status = catalog.document_status(operation, steps)
                            if status != 'new':
                                budget.start_item()
                                steps.update(status=status, finished_at=now())
                                item['decrypted'] = True
                                save()
                                counter = 'catalog_reconciled' if status == 'complete' else 'duplicates'
                                summary[counter] = summary.get(counter, 0) + 1
                                emit('publication_checkpointed', record=key, md5=steps['md5'], status=steps['status'])
                                continue
                    summary['awaiting_inputs'] = summary.get('awaiting_inputs', 0) + 1
                    emit('publication_pending', record=key, reason='awaiting_inputs')
                    continue
                budget.start_item()
                sha, md5, size = file_digests(path)
                if sha != output['sha256']:
                    raise ValueError('Finalized PDF hash has changed')
                if steps.get('sha256') != sha:
                    steps.clear()
                steps.update(sha256=sha, md5=md5, status='pending')
                # Recheck identity while holding Manzara's session lock, and
                # retain it through remote writes, catalog commit and checkpoint.
                with document_operation(config['database_url'], md5) as operation:
                    status = catalog.document_status(operation, steps)
                    if status != 'new':
                        steps.update(status=status, finished_at=now())
                        item['decrypted'] = True
                        save()
                        counter = 'catalog_reconciled' if status == 'complete' else 'duplicates'
                        summary[counter] = summary.get(counter, 0) + 1
                        emit('publication_checkpointed', record=key, md5=md5, status=steps['status'])
                        continue
                    if output.get('complete') is not True or item.get('downloaded') != 'full':
                        # A nonempty preview does not establish full acquisition.
                        steps['reason'] = 'full_verification_required'
                        save()
                        summary['awaiting_full_verification'] = summary.get('awaiting_full_verification', 0) + 1
                        emit('publication_pending', record=key, reason='full_verification_required')
                        continue
                    steps.pop('reason', None)
                    # Persist hashes and pending status before any external upload.
                    save()
                    if client is None:
                        client = create_client(settings)
                        resources.callback(client.close)
                    budget.check()
                    if target in {'all', 's3'} and not isinstance(steps.get('s3'), dict):
                        operation.check()
                        emit('upload_started', record=key, md5=md5, destination='s3', size_bytes=size)
                        steps['s3'] = upload_s3(client, settings, path, md5, sha, size)
                        operation.check()
                        if receipt_destination is None:
                            receipt_destination = destination(settings)
                        artifact = PublishableArtifact(key, output.get('id', output['path']), path, sha,
                                                      {'observation_id': record['observations'][-1]['id'], 'result': output})
                        data.setdefault('s3_publications', {})[receipt_key(artifact)] = {
                            'destination': receipt_destination, 'sha256': sha, 'record': key,
                            'artifact': artifact.identity, 'provenance': artifact.provenance,
                            'objects': [{'key': steps['s3']['key'], 'sha256': sha, 'size': size}],
                            'completed_at': now()}
                        save()
                        summary['s3_published'] = summary.get('s3_published', 0) + 1
                        emit('upload_checkpointed', record=key, md5=md5, destination='s3')
                    budget.check()
                    if target in {'all', 'yandex'} and not isinstance(steps.get('yandex'), dict):
                        operation.check()
                        emit('upload_started', record=key, md5=md5, destination='yandex', size_bytes=size)
                        steps['yandex'] = upload_doc(str(path), config, False, md5=md5)
                        operation.check()
                        save()
                        summary['yandex_published'] = summary.get('yandex_published', 0) + 1
                        emit('upload_checkpointed', record=key, md5=md5, destination='yandex')
                    if not (isinstance(steps.get('s3'), dict) and isinstance(steps.get('yandex'), dict)):
                        continue
                    metadata = _upstream_metadata(item)
                    budget.check()
                    operation.check()
                    emit('catalog_registration_started', record=key, md5=md5)
                    created = catalog.register_document(operation, steps, metadata)
                    steps.update(status='complete' if created else 'duplicate', finished_at=now())
                    item['decrypted'] = True
                    save()
                    counter = 'catalog_registered' if created else 'duplicates'
                    summary[counter] = summary.get(counter, 0) + 1
                    if created:
                        summary['upstream_metadata_saved'] = summary.get('upstream_metadata_saved', 0) + 1
                    emit('publication_checkpointed', record=key, md5=md5, status=steps['status'])
            except BudgetStop:
                raise
            except DocumentOperationBusy:
                summary.setdefault('warnings', []).append(
                    {'stage': 'publication', 'record': key, 'error': 'DocumentOperationBusy', 'retryable': True})
                emit('publication_deferred', record=key, reason='document_busy', retryable=True)
            except Exception as error:
                from .milli_kitaphana_logging import error_fields
                emit('publication_failed', record=key, **error_fields(error))
                summary.setdefault('errors', []).append({'stage': 'publication', 'record': key, 'error': type(error).__name__})
