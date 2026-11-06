"""Bounded, read-only views of selected PostgreSQL state."""
from sqlalchemy import select, func, or_
from .database import transaction
from .postgres_state import tables, encode_string, decode_string, transform
from .diagnostics import partition_discovery_errors
from .output import compact_result
from .views import preview


def state(source, keys):
    table = tables(source)[2]
    with transaction() as conn:
        rows = conn.execute(select(table.c.key, table.c.payload).where(table.c.key.in_([encode_string(k) for k in keys])))
        return {decode_string(k): transform(v, decode_string) for k, v in rows}


def record(source, key, asset_limit, fields=()):
    records, assets, _ = tables(source)
    with transaction() as conn:
        payload = conn.scalar(select(records.c.payload).where(records.c.key == encode_string(key)))
        if payload is None:
            raise ValueError('Record not found')
        data = transform(payload, decode_string)
        owner = or_(assets.c.payload['record_key'].astext == encode_string(key),
                    (assets.c.payload['record_key'].astext.is_(None)) & (assets.c.payload['record_url'].astext == encode_string(key)))
        count = conn.scalar(select(func.count()).select_from(assets).where(owner))
        asset_preview = []
        if asset_limit:
            for asset_key, value in conn.execute(select(assets.c.key, assets.c.payload).where(owner).order_by(assets.c.key).limit(asset_limit)):
                value = transform(value, decode_string)
                asset_preview.append({'key': decode_string(asset_key), **{k: value[k] for k in ('url', 'status', 'kind', 'extension', 'last_error') if k in value}})
    observations = data.get('observations', [])
    metadata = observations[-1].get('metadata', {}) if observations else data
    missing_fields = [field for field in fields if field not in metadata]
    if fields:
        metadata = {field: metadata[field] for field in fields if field in metadata}
    return preview(dict(source=source, key=key, assets=count, missing_fields=missing_fields,
                        asset_preview=asset_preview, assets_omitted=max(0, count - len(asset_preview)),
                        completion={k: data[k] for k in ('pdf', 'package_pdf', 'imported_acquisition_complete') if k in data}, metadata=metadata),
                   omitted_keys={'observations', 'results', 'current_results'})


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
        result[name] = {'count': len(entries), 'preview': selected, 'omitted': len(entries) - len(selected)}
        remaining -= len(selected)
    return preview({'source': source, **result})


def last_run(source):
    run = state(source, ['last_run']).get('last_run')
    return {'source': source, 'last_run': compact_result(run, run.get('command', 'unknown'), source) if run else None}


def records(source, limit, after=None):
    """List stable record keys with SQL-projected titles and completion hints."""
    from sqlalchemy import func, case
    table = tables(source)[0]
    payload = table.c.payload
    metadata = func.coalesce(payload['observations'][-1]['metadata'], payload)
    title = func.coalesce(metadata['title'].astext, metadata['full_name'].astext, metadata['name'].astext)
    status = func.coalesce(payload['pdf']['status'].astext, payload['package_pdf']['status'].astext,
                           metadata['downloaded'].astext,
                           case((metadata['finalized'].astext.is_not(None), 'finalized'),
                                (metadata['acquired'].astext.is_not(None), 'acquired'), else_='observed'))
    query = select(table.c.key, title, status).order_by(table.c.key).limit(limit + 1)
    if after is not None:
        query = query.where(table.c.key > encode_string(after))
    with transaction() as conn:
        rows = conn.execute(query).all()
    selected = rows[:limit]
    result = {'source': source, 'records': [
        {'key': decode_string(key), 'title': decode_string(title) if title else None,
         'status': decode_string(status) if status else None} for key, title, status in selected],
        'has_more': len(rows) > limit,
        'next_after': decode_string(selected[-1][0]) if len(rows) > limit else None}
    # The explicit CLI limit controls this list, not the general preview list limit.
    result['records'] = [{**preview({k: v for k, v in row.items() if k != 'key'}), 'key': row['key']} for row in result['records']]
    return result
