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


def artifacts(data, directory):
    """Project native state without modifying provider payloads."""
    for key, record in data['records'].items():
        observation = record.get('observations', [])
        meta = observation[-1]['metadata'] if observation else record
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
    for key, asset in data['assets'].items():
        if (not asset.get('current', True) or asset.get('status') != 'downloaded'
                or asset.get('kind') == 'page_image' or not asset.get('results')):
            continue
        from .core import source_version_matches
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


def configuration(settings):
    config = settings.s3
    if (not isinstance(config, dict) or not isinstance(config.get('bucket'), str)
            or not config['bucket'].strip() or config['bucket'].startswith('<')):
        raise ValueError('Configure storage.s3.bucket before run or publish --target s3')
    return config


def destination(settings):
    config = configuration(settings)
    return {k: config.get(k, '') for k in ('bucket', 'endpoint_url', 'prefix')}


def completed(data, artifact, settings):
    receipt = data.get('s3_publications', {}).get(receipt_key(artifact), {})
    return (receipt.get('destination') == destination(settings)
            and receipt.get('sha256') == artifact.sha256 and artifact.sha256 is not None)


def publish(settings, data, directory, save, summary, budget, *, available_only=False):
    from boto3 import Session
    from botocore.config import Config
    from botocore.exceptions import ClientError, BotoCoreError
    from boto3.exceptions import S3UploadFailedError
    from .core import file_digests
    config = configuration(settings)
    inventory = list(artifacts(data, directory))
    if available_only and not any(a.path.is_file() and not completed(data, a, settings) for a in inventory):
        return
    client = Session().client('s3', endpoint_url=config.get('endpoint_url'),
                              region_name=config.get('region'), config=Config(
                                  connect_timeout=settings.connect_timeout_seconds,
                                  read_timeout=settings.read_timeout_seconds,
                                  retries={'max_attempts': settings.retry_attempts, 'mode': 'standard'}))
    try:
        receipts = data.setdefault('s3_publications', {})
        for artifact in inventory:
            if available_only and not artifact.path.is_file():
                continue
            budget.check()
            if completed(data, artifact, settings) and artifact.path.suffix.lower() != '.md':
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
                    key = '/'.join(p for p in (config.get('prefix', '').strip('/'), data['source'], bundle, name) if p)
                    exists = False
                    try:
                        head = client.head_object(Bucket=config['bucket'], Key=key)
                        exists = head['ContentLength'] == length and head.get('Metadata', {}).get('sha256') == digest
                    except ClientError as error:
                        if str(error.response['Error']['Code']) not in {'404', 'NoSuchKey', 'NotFound'}:
                            raise
                    if not exists:
                        client.upload_file(str(path), config['bucket'], key, ExtraArgs={
                            'Metadata': {'sha256': digest},
                            'ContentType': mimetypes.guess_type(name)[0] or 'application/octet-stream'})
                    objects.append({'key': key, 'sha256': digest, 'size': length})
                receipts[receipt_key(artifact)] = {'destination': destination(settings), 'sha256': sha,
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
    missing = {a.record for a in artifacts(data, directory)
               if not completed(data, a, settings) and not a.path.is_file()}
    source = data['source']
    for key in missing:
        record = data['records'][key]
        if source == 'common_crawl':
            record.pop('path_to_file', None)
            record['s3_restore_required'] = True
        elif source in {'litres', 'milli_kitaphana'}:
            import copy
            record.setdefault('s3_recovery_evidence', []).append(copy.deepcopy(record['observations'][-1]['metadata']))
            meta = record['observations'][-1]['metadata']
            # Provider helpers already implement re-acquisition from pending state.
            for field in ('acquired', 'imported_acquisition_complete', 'downloaded', 'decrypted', 'finalized'):
                meta.pop(field, None)
        else:
            for field in ('pdf', 'package_pdf'):
                if field in record:
                    record[field]['status'] = 'incomplete'
    for asset in data['assets'].values():
        owner = asset.get('record_key', asset['record_url'])
        if owner in missing and asset.get('results'):
            if not (directory / asset['results'][-1]['path']).is_file():
                asset['status'] = 'pending'
                asset.pop('imported_acquisition_complete', None)
    return bool(missing)
