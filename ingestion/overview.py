"""Compact inventories without loading record or asset histories."""
from collections import Counter
from itertools import chain

from .diagnostics import partition_discovery_errors
from .views import preview


def summarize(source, coverage, record_count, states, formats, current, historical, *, details):
    result = dict(source=source, records=record_count, current_assets=dict(sorted(states.items())),
                  discovery_complete=coverage.get('complete'), pages=coverage.get('pages'),
                  remaining_listings=coverage.get('remaining_listing_requests'),
                  remaining_records=coverage.get('remaining_record_urls'),
                  discovery_errors=sum(current.values()), historical_discovery_errors=sum(historical.values()))
    if details:
        result.update(scan={key: coverage.get(key) for key in (
            'catalog_entries_enumerated', 'unique_records_inspected',
            'advertised_catalog_entries', 'count_verified', 'restart_required')},
            asset_formats=dict(sorted(formats.items())),
            discovery_error_messages=message_groups(current),
            historical_discovery_error_messages=message_groups(historical))
    return preview(result)


def message_groups(counts):
    # Messages are values so the shared preview bounds their text as well as the
    # number of groups. Stable ordering makes SQL and snapshot previews identical.
    return [{'message': message, 'count': count} for message, count in
            sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def snapshot_overview(data, *, details=False):
    assets = [a for a in data['assets'].values() if a.get('current', True)]
    current, prior = partition_discovery_errors(data)
    return summarize(data['source'], data.get('discovery', {}), len(data['records']),
                     Counter(a.get('status', 'unknown') for a in assets),
                     Counter(a.get('extension') or 'unknown' for a in assets),
                     Counter(e.get('error', 'unknown') for e in current.values()),
                     Counter(e.get('error', 'unknown') for e in chain(
                         data.get('discovery_error_history', []), prior.values())), details=details)


def database_overview(source, *, details=False):
    from sqlalchemy import select, func, text, or_, cast
    from sqlalchemy.dialects.postgresql import JSONB
    from .database import transaction
    from .postgres_state import tables, decode_string, transform
    from .diagnostics import discovery_error_classifier

    records, assets, state = tables(source)
    payload = assets.c.payload
    current_asset = or_(~payload.has_key('current'), payload['current'].as_boolean().is_(True))
    with transaction() as conn:
        conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        record_count = conn.scalar(select(func.count()).select_from(records))

        def counts(expression):
            return {decode_string(key) if key is not None else None: count for key, count in
                    conn.execute(select(expression, func.count()).where(current_asset)
                                 .group_by(expression))}

        states = counts(func.coalesce(payload['status'].astext, 'unknown'))
        formats = counts(func.coalesce(func.nullif(payload['extension'].astext, ''), 'unknown')) if details else {}
        # Only coverage and pending request identities are needed, never visited
        # records, observations, asset results, or a writable repository baseline.
        coverage = conn.scalar(select(state.c.payload).where(state.c.key == 'discovery')) or {}
        scan_payload = state.c.payload
        scan_view = func.jsonb_build_object(*[
            part for key in ('id', 'started_at', 'pending_records', 'frontier')
            for part in (key, scan_payload[key])])
        scan = conn.scalar(select(scan_view).where(state.c.key == 'discovery_scan'))
        scan = transform(scan, decode_string) if scan else None
        if scan:
            scan = {key: value for key, value in scan.items() if value is not None}
        is_active = discovery_error_classifier(scan)
        current, historical = Counter(), Counter()
        error_payload = select(state.c.payload).where(state.c.key == 'discovery_errors').scalar_subquery()
        errors = func.jsonb_each(error_payload).table_valued('key', 'value')
        # Server-side cursors keep even a large error register out of memory.
        rows = conn.execution_options(stream_results=True).execute(select(errors.c.key, errors.c.value))
        for key, error in rows:
            error = transform(error, decode_string)
            target = current if is_active(decode_string(key), error) else historical
            target[error.get('error', 'unknown')] += 1
        history_payload = select(state.c.payload).where(state.c.key == 'discovery_error_history').scalar_subquery()
        history = func.jsonb_array_elements(history_payload).table_valued('value')
        # Aggregate history in PostgreSQL; return message groups rather than entries.
        message = func.coalesce(cast(history.c.value, JSONB)['error'].astext, 'unknown')
        for value, count in conn.execute(select(message, func.count()).group_by(message)):
            historical[decode_string(value)] += count
    return summarize(source, transform(coverage, decode_string), record_count, states, formats,
                     current, historical, details=details)
