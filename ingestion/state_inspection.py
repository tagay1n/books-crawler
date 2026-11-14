"""Bounded, read-only views of selected PostgreSQL state."""
from collections import deque
from sqlalchemy import select, func, or_, cast, text, case
from sqlalchemy.dialects.postgresql import JSONB, JSONPATH
from .database import transaction
from .postgres_state import tables, encode_string, decode_string, transform
from .diagnostics import discovery_error_classifier
from .sql_views import discovery_scan, object_fields, without_histories
from .output import compact_result
from .views import preview


def record(source, key, asset_limit, fields=()):
    records, assets, _ = tables(source)
    payload = records.c.payload
    metadata = without_histories(func.coalesce(payload['observations'][-1]['metadata'], payload))
    if fields:
        metadata = object_fields(metadata, [encode_string(field) for field in fields])
    completion = object_fields(payload, ('imported_acquisition_complete',))
    for name in ('pdf', 'package_pdf'):
        completion = completion.op('||')(case((payload.has_key(name),
            func.jsonb_build_object(name, without_histories(payload[name]))), else_=func.jsonb_build_object()))
    projection = func.jsonb_build_object('metadata', metadata, 'completion', completion)
    with transaction() as conn:
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        data = conn.scalar(select(projection).where(records.c.key == encode_string(key)))
        if data is None:
            raise ValueError('Record not found')
        data = transform(data, decode_string)
        owner = or_(assets.c.payload['record_key'].astext == encode_string(key),
                    (assets.c.payload['record_key'].astext.is_(None)) & (assets.c.payload['record_url'].astext == encode_string(key)))
        count = conn.scalar(select(func.count()).select_from(assets).where(owner))
        asset_preview = []
        if asset_limit:
            asset_view = object_fields(assets.c.payload, ('url', 'status', 'kind', 'extension', 'last_error'))
            for asset_key, value in conn.execute(select(assets.c.key, asset_view).where(owner).order_by(assets.c.key).limit(asset_limit)):
                value = transform(value, decode_string)
                asset_preview.append({'key': decode_string(asset_key), **value})
    metadata = data['metadata']
    missing_fields = [field for field in fields if field not in metadata]
    if fields:
        metadata = {field: metadata[field] for field in fields if field in metadata}
    return preview(dict(source=source, key=key, assets=count, missing_fields=missing_fields,
                        asset_preview=asset_preview, assets_omitted=max(0, count - len(asset_preview)),
                        completion=data['completion'], metadata=metadata),
                   omitted_keys={'observations', 'results', 'current_results'})


def errors(source, limit):
    table = tables(source)[2]
    def value(key):
        return select(table.c.payload).where(table.c.key == key).scalar_subquery()
    with transaction() as conn:
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        scan = conn.scalar(select(discovery_scan(value('discovery_scan'))))
        is_active = discovery_error_classifier(transform(scan, decode_string) if scan else None)
        entries = func.jsonb_each(value('discovery_errors')).table_valued('key', 'value')
        active, prior = deque(maxlen=limit), deque(maxlen=limit)
        active_count = prior_count = 0
        # Classify streamed identities/timestamps; fetch full payloads only for selected keys.
        evidence = object_fields(cast(entries.c.value, JSONB), ('scan_id', 'at'))
        rows = conn.execution_options(stream_results=True).execute(select(entries.c.key, evidence))
        for key, error in rows:
            if is_active(decode_string(key), transform(error, decode_string)):
                active_count += 1
                active.append(key)
            else:
                prior_count += 1
                prior.append(key)
        def selected_errors(keys):
            if not keys:
                return []
            selected = dict(conn.execute(select(entries.c.key, entries.c.value).where(entries.c.key.in_(keys))).all())
            return [transform(selected[key], decode_string) for key in keys]
        def array_tail(array, count):
            if not count:
                return []
            items = func.jsonb_array_elements(array).table_valued('value', with_ordinality='position').render_derived()
            selected = conn.execute(select(items.c.value).order_by(items.c.position.desc()).limit(count)).scalars().all()
            return [transform(item, decode_string) for item in reversed(selected)]
        history = value('discovery_error_history')
        last_errors = value('last_run')['errors']
        history_count = conn.scalar(select(func.coalesce(func.jsonb_array_length(history), 0)))
        last_count = conn.scalar(select(func.coalesce(func.jsonb_array_length(last_errors), 0)))
        current = selected_errors(list(active))
        remaining = limit - len(current)
        prior_keys = list(prior)[-remaining:] if remaining else []
        historical = array_tail(history, max(0, remaining - prior_count)) + selected_errors(prior_keys)
        remaining -= len(historical)
        last = array_tail(last_errors, remaining)
        result = {name: {'count': count, 'preview': selected, 'omitted': count - len(selected)}
                  for name, count, selected in (
                      ('active_discovery', active_count, current),
                      ('historical_discovery', history_count + prior_count, historical),
                      ('last_run', last_count, last))}
    return preview({'source': source, **result})


def last_run(source):
    table = tables(source)[2]
    payload = table.c.payload
    errors = func.coalesce(func.jsonb_path_query_array(payload['errors'], cast('$[0 to 2]', JSONPATH)),
                           func.jsonb_build_array())
    projection = payload.op('-')('errors').op('||')(func.jsonb_build_object('errors', errors))
    with transaction() as conn:
        row = conn.execute(select(projection, func.coalesce(func.jsonb_array_length(payload['errors']), 0))
                           .where(table.c.key == 'last_run', func.jsonb_typeof(payload) == 'object',
                                  payload != func.jsonb_build_object())).first()
    if row is None:
        return {'source': source, 'last_run': None}
    run = transform(row[0], decode_string)
    result = compact_result(run, run.get('command', 'unknown'), source)
    if not run.get('error'):
        result['error_count'] = row[1]
    return {'source': source, 'last_run': result}


def records(source, limit, after=None):
    """List stable record keys with SQL-projected titles and completion hints."""
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
