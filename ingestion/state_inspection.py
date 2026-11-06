"""Bounded, read-only views of selected PostgreSQL state."""
from sqlalchemy import select, func, or_
from .database import transaction
from .postgres_state import tables, encode_string, decode_string, transform
from .diagnostics import partition_discovery_errors
from .output import compact_result


def bounded(value, depth=0):
    if depth >= 4:
        return '[nested content omitted]'
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, dict):
        return {str(k)[:100]: bounded(v, depth + 1) for k, v in [(k, v) for k, v in value.items() if k not in {'observations', 'results', 'current_results'}][:20]}
    if isinstance(value, list):
        return [bounded(v, depth + 1) for v in value[:10]]
    return value


def state(source, keys):
    table = tables(source)[2]
    with transaction() as conn:
        rows = conn.execute(select(table.c.key, table.c.payload).where(table.c.key.in_([encode_string(k) for k in keys])))
        return {decode_string(k): transform(v, decode_string) for k, v in rows}


def record(source, key, asset_limit):
    records, assets, _ = tables(source)
    with transaction() as conn:
        payload = conn.scalar(select(records.c.payload).where(records.c.key == encode_string(key)))
        if payload is None:
            raise ValueError('Record not found')
        data = transform(payload, decode_string)
        owner = or_(assets.c.payload['record_key'].astext == encode_string(key),
                    (assets.c.payload['record_key'].astext.is_(None)) & (assets.c.payload['record_url'].astext == encode_string(key)))
        count = conn.scalar(select(func.count()).select_from(assets).where(owner))
        preview = []
        if asset_limit:
            for asset_key, value in conn.execute(select(assets.c.key, assets.c.payload).where(owner).order_by(assets.c.key).limit(asset_limit)):
                value = transform(value, decode_string)
                preview.append(bounded({'key': decode_string(asset_key), **{k: value[k] for k in ('url', 'status', 'kind', 'extension', 'last_error') if k in value}}))
    observations = data.get('observations', [])
    metadata = observations[-1].get('metadata', {}) if observations else data
    return dict(source=source, key=key, metadata=bounded(metadata), assets=count, asset_preview=preview,
                completion=bounded({k: data[k] for k in ('pdf', 'package_pdf', 'imported_acquisition_complete') if k in data}))


def errors(source, limit):
    data = state(source, ['discovery_errors', 'discovery_scan', 'discovery_error_history', 'last_run'])
    current, prior = partition_discovery_errors(data)
    groups = {'active_discovery': list(current.values()),
              'historical_discovery': [*data.get('discovery_error_history', []), *prior.values()],
              'last_run': data.get('last_run', {}).get('errors', [])}
    remaining = limit
    result = {}
    for name, entries in groups.items():
        selected = entries[-remaining:] if remaining else []
        result[name] = {'count': len(entries), 'preview': bounded_errors(selected)}
        remaining -= len(selected)
    return {'source': source, **result}


def bounded_errors(entries):
    return [bounded(entry) for entry in entries]


def last_run(source):
    run = state(source, ['last_run']).get('last_run')
    return {'source': source, 'last_run': {k: bounded(v) for k, v in compact_result(run, run.get('command', 'unknown'), source).items()} if run else None}
