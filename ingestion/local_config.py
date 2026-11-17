"""Create complete private source configurations without copying environment secrets."""
import os
from pathlib import Path

import yaml

from .config import read_configuration
from .registry import DESCRIPTORS


def source_config_path(source):
    return Path(__file__).resolve().parents[1] / 'config' / 'local' / f'{source}.yaml'


def create_source_config(source):
    if source not in DESCRIPTORS:
        raise ValueError(f'Unknown source: {source}')
    path = source_config_path(source)
    if path.exists():
        return path
    template = path.parents[1] / 'sources' / path.name
    data = read_configuration(template)

    def literals(value):
        if isinstance(value, dict):
            if set(value) == {'env'}:
                return None
            return {key: literals(child) for key, child in value.items()}
        if isinstance(value, list):
            return [literals(child) for child in value]
        return value

    data = literals(data)
    data['standalone'] = True
    data['database'] = dict(url=None, pool_size=2, pool_timeout_seconds=30, connect_timeout_seconds=10)
    data['storage']['s3'].update(access_key_id=None, secret_access_key=None, session_token=None,
                               region='us-east-1', endpoint_url=None)
    if DESCRIPTORS[source].requires_session:
        data['sources'][source]['session'] = dict(format='miras-session-v1', origin='https://miras.info',
                                                 user_agent=None, cookies=[])
    if source == 'milli_kitaphana':
        options = data['sources'][source]
        for key in ('priv_key', 'sig_prefix'):
            options[key] = {'base64': None}
        for key in ('raw_key', 'default_iv', 'salt'):
            options['aes'][key] = {'base64': None}
    # Both directories have the same depth, so relative artifact paths retain
    # their meaning after flattening the public template and shared defaults.
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        handle.write('# Complete private source configuration. Fill null credential fields here.\n')
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)
    return path
