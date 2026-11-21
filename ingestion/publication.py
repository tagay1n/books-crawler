"""Source-neutral finished artifact inventory and resumable S3 publication."""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import mimetypes


from .state import now


@dataclass(frozen=True)
class PublishableArtifact:
    record: str
    identity: str
    path: Path
    sha256: str | None
    provenance: dict


def _selected_items(items, keys):
    return items.items() if keys is None else ((key, items[key]) for key in keys if key in items)


def artifacts(data, directory, *, direct_files_only=False, record_keys=None, asset_keys=None):
    """Project native state without modifying provider payloads."""
    for key, record in _selected_items(data['records'], record_keys):
        observation = record.get('observations', [])
        meta = observation[-1]['metadata'] if observation else record
        if data['source'] == 'milli_kitaphana':
            state = data.get('publications', {}).get(key, {})
            if state.get('status') in {'duplicate', 'not_full'} and state.get('sha256') == meta.get('finalized', {}).get('sha256'):
                continue
        # Direct-only collection policies also exclude previously assembled
        # outputs; original document assets are projected separately below.
        if direct_files_only or meta.get('acquisition_policy') == 'direct_files_only':
            continue
        provenance = {'observation_id': observation[-1]['id']} if observation else {}
        outputs = []
        for name in ('pdf', 'package_pdf'):
            state = record.get(name, {})
            if state.get('status') == 'complete':
                outputs.extend(state.get('current_results', state.get('results', [])[-1:]))
        if meta.get('finalized'):
            outputs.append(meta['finalized'])
        if not meta.get('finalized'):
            outputs.extend(meta.get('imported_outputs', {}).values())
        if data['source'] == 'common_crawl' and meta.get('path_to_file'):
            outputs.append({'path': meta['path_to_file'], 'sha256': meta.get('sha256')})
        seen = set()
        for output in outputs:
            if not output.get('path') or output['path'] in seen:
                continue
            seen.add(output['path'])
            path = Path(output['path'])
            path = path if path.is_absolute() else directory / path
            yield PublishableArtifact(key, output.get('id', output['path']), path,
                                      output.get('sha256'), {**provenance, 'result': output})
    for key, asset in _selected_items(data['assets'], asset_keys):
        if (not asset.get('current', True) or asset.get('status') != 'downloaded'
                or asset.get('kind') == 'page_image' or not asset.get('results')):
            continue
        from .files import source_version_matches
        if not source_version_matches(asset):
            continue
        result = asset['results'][-1]
        # Package archives are inputs, never finished documents.
        if Path(result['path']).suffix.lower() in {'.zip', '.dat'}:
            continue
        yield PublishableArtifact(asset.get('record_key', asset['record_url']), key,
                                  directory / result['path'], result.get('sha256'),
                                  {'observation_id': asset['observation_id'], 'result': result})


def receipt_key(artifact):
    return hashlib.sha256((artifact.record + '\n' + artifact.identity).encode()).hexdigest()


def _require_bucket(config):
    bucket = config.get('bucket') if isinstance(config, dict) else None
    if not isinstance(bucket, str) or not bucket.strip() or bucket.lstrip().startswith('<'):
        raise ValueError('Configure storage.s3.bucket before run or publish --target s3')
    return bucket


def configuration(settings):
    config = settings.s3
    _require_bucket(config)
    if settings.file_only or config.get('access_key_id') or config.get('secret_access_key'):
        for key in ('access_key_id', 'secret_access_key'):
            if not isinstance(config.get(key), str) or not config[key].strip() or config[key] == '<SET ME>':
                raise ValueError(f'Set storage.s3.{key} in the source configuration file')
    if settings.file_only and (not isinstance(config.get('region'), str) or not config['region'].strip()):
        raise ValueError('Set storage.s3.region in the source configuration file')
    return config


def destination(settings):
    config = settings.s3
    return {'bucket': _require_bucket(config), 'endpoint_url': config.get('endpoint_url', ''),
            'prefix': config.get('prefix', '')}


def completed(data, artifact, receipt_destination):
    receipt = data.get('s3_publications', {}).get(receipt_key(artifact), {})
    return (receipt.get('destination') == receipt_destination
            and receipt.get('sha256') == artifact.sha256 and artifact.sha256 is not None)


def artifact_counts(settings, data, directory):
    try:
        receipt_destination = destination(settings)
    except ValueError:
        receipt_destination = None
    counts = {'published_artifacts': len(data.get('s3_publications', {})), 'current_artifacts': 0}
    if receipt_destination is not None:
        counts['pending_artifacts'] = 0
    for artifact in artifacts(data, directory, direct_files_only=settings.source_options.get('direct_files_only') is True):
        counts['current_artifacts'] += 1
        if receipt_destination is not None and not completed(data, artifact, receipt_destination):
            counts['pending_artifacts'] += 1
    return counts


def create_client(settings):
    """Use the same configured credentials, endpoint and transfer timeouts everywhere."""
    from boto3 import Session
    from botocore.config import Config
    config = configuration(settings)
    credentials = ({'aws_access_key_id': config['access_key_id'],
                    'aws_secret_access_key': config['secret_access_key'],
                    'aws_session_token': config.get('session_token') or None}
                   if settings.file_only or config.get('access_key_id') else {})
    return Session(**credentials).client('s3', endpoint_url=config.get('endpoint_url') or None,
                              region_name=config.get('region') or None, config=Config(
                                  connect_timeout=settings.connect_timeout_seconds,
                                  read_timeout=settings.read_timeout_seconds,
                                  retries={'max_attempts': settings.retry_attempts, 'mode': 'standard'}))


def publish(settings, data, directory, save, summary, budget, *, available_only=False,
            record_keys=None, asset_keys=None):
    from botocore.exceptions import ClientError, BotoCoreError
    from boto3.exceptions import S3UploadFailedError
    from .files import file_digests
    receipt_destination = destination(settings)
    inventory = list(artifacts(data, directory, record_keys=record_keys, asset_keys=asset_keys,
                               direct_files_only=settings.source_options.get('direct_files_only') is True))
    if available_only and not any(a.path.is_file() and not completed(data, a, receipt_destination) for a in inventory):
        return
    client = create_client(settings)
    try:
        receipts = data.setdefault('s3_publications', {})
        for artifact in inventory:
            if available_only and not artifact.path.is_file():
                continue
            budget.check()
            if completed(data, artifact, receipt_destination) and (artifact.path.suffix.lower() != '.md' or not artifact.path.is_file()):
                receipts[receipt_key(artifact)]['provenance'] = artifact.provenance
                summary['s3_skipped'] = summary.get('s3_skipped', 0) + 1
                continue
            if summary.get('s3_attempted', 0) >= settings.max_items:
                summary.setdefault('stops', []).append('S3 item cap')
                break
            summary['s3_attempted'] = summary.get('s3_attempted', 0) + 1
            try:
                sha, _, size = file_digests(artifact.path)
                if artifact.sha256 and sha != artifact.sha256:
                    raise ValueError('Local artifact hash does not match recorded result')
                files = [(artifact.path, artifact.path.name, sha, size)]
                if artifact.path.suffix.lower() == '.md':
                    for path in sorted((artifact.path.parent / 'media').rglob('*')):
                        if path.is_file():
                            if not path.resolve().is_relative_to(artifact.path.parent.resolve()):
                                raise ValueError('Media path escapes the document directory')
                            digest, _, length = file_digests(path)
                            files.append((path, path.relative_to(artifact.path.parent).as_posix(), digest, length))
                    bundle = hashlib.sha256('\n'.join(f'{name}:{digest}' for _, name, digest, _ in files).encode()).hexdigest()
                else:
                    bundle = sha
                objects = []
                for path, name, digest, length in files:
                    budget.check()
                    key = '/'.join(p for p in (receipt_destination['prefix'].strip('/'), data['source'], bundle, name) if p)
                    exists = False
                    try:
                        head = client.head_object(Bucket=receipt_destination['bucket'], Key=key)
                        exists = head['ContentLength'] == length and head.get('Metadata', {}).get('sha256') == digest
                    except ClientError as error:
                        if str(error.response['Error']['Code']) not in {'404', 'NoSuchKey', 'NotFound'}:
                            raise
                    if not exists:
                        client.upload_file(str(path), receipt_destination['bucket'], key, ExtraArgs={
                            'Metadata': {'sha256': digest},
                            'ContentType': mimetypes.guess_type(name)[0] or 'application/octet-stream'})
                    objects.append({'key': key, 'sha256': digest, 'size': length})
                receipts[receipt_key(artifact)] = {'destination': receipt_destination, 'sha256': sha,
                    'record': artifact.record, 'artifact': artifact.identity, 'provenance': artifact.provenance,
                    'objects': objects, 'completed_at': now()}
                if data['source'] == 'common_crawl':
                    data['records'][artifact.record]['sha256'] = sha
                save()
                summary['s3_published'] = summary.get('s3_published', 0) + 1
            except (OSError, ValueError, ClientError, BotoCoreError, S3UploadFailedError) as error:
                summary.setdefault('errors', []).append({'stage': 's3', 'record': artifact.record, 'error': str(error)})
    finally:
        client.close()


def restore_missing(settings, data, directory):
    """Invalidate only missing, unpublished inputs; retain acquisition history."""
    inventory = list(artifacts(data, directory, direct_files_only=settings.source_options.get('direct_files_only') is True))
    receipt_destination = destination(settings)
    settled = {a.record for a in inventory if completed(data, a, receipt_destination)}
    missing = {a.record for a in inventory
               if not completed(data, a, receipt_destination) and not a.path.is_file()}
    source = data['source']
    # Incomplete assemblies have no publishable artifact yet. Their recorded
    # acquisition flags cannot establish that inputs survived an ephemeral runner.
    for key, record in data['records'].items():
        if key in settled and key not in missing:
            continue
        observations = record.get('observations') or [{}]
        meta = observations[-1].get('metadata', {})
        if source == 'litres' and meta.get('acquired'):
            inputs = meta.get('inputs', [])
            if not inputs or any(not Path(p['path']).is_file() for p in inputs):
                missing.add(key)
    for key in missing:
        record = data['records'][key]
        if source == 'common_crawl':
            record.pop('path_to_file', None)
            record['s3_restore_required'] = True
        elif source == 'litres':
            import copy
            record.setdefault('s3_recovery_evidence', []).append(copy.deepcopy(record['observations'][-1]['metadata']))
            meta = record['observations'][-1]['metadata']
            # Provider helpers already implement re-acquisition from pending state.
            for field in ('acquired', 'imported_acquisition_complete', 'downloaded', 'decrypted', 'finalized', 'enc_part_paths'):
                meta.pop(field, None)
        else:
            for field in ('pdf', 'package_pdf'):
                if field in record:
                    record[field]['status'] = 'incomplete'
    for asset in data['assets'].values():
        if not asset.get('current', True) or asset.get('status') == 'unsupported':
            continue
        owner = asset.get('record_key', asset['record_url'])
        if (owner in missing or owner not in settled) and asset.get('results'):
            if not (directory / asset['results'][-1]['path']).is_file():
                if asset['status'] != 'pending' or asset.get('imported_acquisition_complete'):
                    missing.add(owner)
                asset['status'] = 'pending'
                asset.pop('imported_acquisition_complete', None)
                data['records'].get(owner, {}).pop('imported_acquisition_complete', None)
    return bool(missing)
