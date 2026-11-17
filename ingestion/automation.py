"""Credential preflight and credential-free Actions reporting for the shared CLI."""
import os
from datetime import datetime
from pathlib import Path


MILLI_CRYPTO_SECRETS = {
    'MILLI_KITAPHANA_AES_RAW_KEY': ('aes', 'raw_key'),
    'MILLI_KITAPHANA_AES_DEFAULT_IV': ('aes', 'default_iv'),
    'MILLI_KITAPHANA_AES_SALT': ('aes', 'salt'),
    'MILLI_KITAPHANA_PRIV_KEY': ('priv_key',),
    'MILLI_KITAPHANA_SIG_PREFIX': ('sig_prefix',),
}


def prepare_source_config(source, runner_temp, *, environment=None):
    """Render individual Actions secrets into one ephemeral standalone YAML."""
    import base64
    import binascii
    import yaml
    from .config import load_settings, read_configuration
    from .publication import configuration
    if source != 'milli_kitaphana':
        raise ValueError('Actions config rendering is currently supported for Milli only')
    environment = os.environ if environment is None else environment

    def required(name):
        value = environment.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'Missing required Actions value: {name}')
        return value

    template = Path(__file__).resolve().parents[1] / 'config/sources/milli_kitaphana.yaml'
    data = read_configuration(template)
    options = data['sources'][source]
    data['standalone'] = True
    data['database'] = {**data.get('database', {}), 'url': required('DATABASE_URL')}
    data.setdefault('storage', {})['s3'] = {
        'bucket': required('MILLI_KITAPHANA_S3_BUCKET'),
        'endpoint_url': required('MILLI_KITAPHANA_S3_ENDPOINT_URL'),
        'region': required('MILLI_KITAPHANA_S3_REGION'), 'prefix': '',
        'access_key_id': required('AWS_ACCESS_KEY_ID'),
        'secret_access_key': required('AWS_SECRET_ACCESS_KEY'), 'session_token': None}
    options['database_url'] = required('MILLI_KITAPHANA_DATABASE_URL')
    options['yandex']['disk'] = {
        'oauth_token': required('MILLI_KITAPHANA_YANDEX_DISK_OAUTH_TOKEN'),
        'target_dir': required('MILLI_KITAPHANA_YANDEX_DISK_TARGET_DIR')}
    for name, keys in MILLI_CRYPTO_SECRETS.items():
        try:
            value = base64.b64decode(required(name), validate=True)
        except (ValueError, binascii.Error):
            raise ValueError(f'Actions secret {name} must be valid base64') from None
        if not value:
            raise ValueError(f'Actions secret {name} must not be empty')
        target = options
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = value
    root = Path(runner_temp).resolve()
    data['artifacts_root'] = str(root / 'ingestion')
    options['artifact_dir'] = str(root / 'ingestion' / source)
    path = root / 'source-config.yaml'
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        settings = load_settings(path, source)
        require_access(settings, source)
        configuration(settings)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def require_access(settings, source):
    if source == 'litres':
        values = [settings.source_options.get('sid')]
    elif source == 'milli_kitaphana':
        config = settings.source_options
        values = [config.get('priv_key'), config.get('sig_prefix')]
        values.extend(config['aes'].get(key) for key in ('raw_key', 'default_iv', 'salt'))
        from .milli_kitaphana_upload_docs import require_publication_config
        require_publication_config(config)
    else:
        return
    if any(not isinstance(value, (str, bytes)) or not value.strip() or value == '<SET ME>' for value in values):
        raise ValueError(f'Missing access credentials for {source}')


def job_summary(result, source, command):
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if not path:
        return
    # Do not render upstream URLs, error messages, metadata or session values.
    from .registry import SOURCES
    if source not in SOURCES:
        source = 'unknown'
    def count(value):
        return value if type(value) in (int, float, bool) else 'unavailable'
    failed = bool(result.get('errors'))
    lines = [f'## Ingestion: {source}', '',
             f"Outcome: {'FAILED' if failed else 'partial (budget stop)' if result.get('stops') else 'completed with warnings' if result.get('warnings') else 'completed'}", '',
             '| Metric | Value |', '| --- | --- |']
    for key in ('pages', 'records', 'downloaded', 'finalized', 'pdf_assembled', 'skipped',
                'yandex_published', 'upstream_metadata_saved', 'duplicates', 'catalog_registered', 'catalog_reconciled',
                's3_published', 's3_skipped', 'attempted_download_bytes'):
        lines.append(f'| {key} | {count(result.get(key, 0))} |')
    lines.append(f"| failures | {len(result.get('errors', []))} |")
    if 'warnings' in result:
        lines.append(f"| warnings | {len(result['warnings'])} |")
    start, end = result.get('started_at'), result.get('finished_at')
    if start and end:
        seconds = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
        lines.append(f'| duration seconds | {seconds:.1f} |')
    for section in ('backlog', 'discovery', 's3'):
        for key, value in result.get(section, {}).items():
            if type(value) in (int, float, bool) and key.replace('_', '').isalnum():
                lines.append(f'| {section}.{key} | {value} |')
    for section in ('current_assets', 'pdf_books', 'pdf_issues', 'package_books', 'image_pages'):
        for key, value in result.get('backlog', {}).get(section, {}).items():
            if type(value) in (int, float, bool) and key.replace('_', '').isalnum():
                lines.append(f'| backlog.{section}.{key} | {value} |')
    allowed = {'soft deadline', 'discovery time cap', 'download item cap', 'download byte cap',
               'discovery page cap', 'S3 item cap', 'finalization item cap', 'page cap'}
    stops = [s if s in allowed else 'other configured limit' for s in result.get('stops', [])]
    lines.extend(['', 'Stop reasons: ' + (', '.join(dict.fromkeys(stops)) or 'none'), ''])
    with Path(path).open('a', encoding='utf-8') as handle:
        handle.write('\n'.join(lines))
