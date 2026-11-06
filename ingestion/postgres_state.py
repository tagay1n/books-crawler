"""JSONB repositories retaining the existing manifest and provider payloads."""
import copy
import base64
from sqlalchemy import MetaData, Table, Column, Text, select, text, delete, func, case
from sqlalchemy.dialects.postgresql import JSONB, insert
from .database import transaction, assert_ownership, _owner
from .registry import SOURCES

_ESCAPE = '__books_crawler_string_v1__:'


def encode_string(value):
    if value.startswith(_ESCAPE) or any(ord(c) == 0 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        return _ESCAPE + base64.b64encode(value.encode('utf-8', errors='surrogatepass')).decode('ascii')
    return value


def decode_string(value):
    if value.startswith(_ESCAPE):
        return base64.b64decode(value[len(_ESCAPE):]).decode('utf-8', errors='surrogatepass')
    return value


def transform(value, operation):
    if isinstance(value, str):
        return operation(value)
    if isinstance(value, dict):
        return {operation(k):transform(v, operation) for k,v in value.items()}
    if isinstance(value, list):
        return [transform(v, operation) for v in value]
    return value


_metadata = MetaData(schema='ingestion')
_tables = {}


def tables(source):
    if source not in SOURCES and source != 'kfu_vakyt_pilot':
        raise ValueError('Unknown persistence source')
    if source not in _tables:
        _tables[source] = tuple(Table(source + '_' + suffix, _metadata,
                                     Column('key', Text, primary_key=True), Column('payload', JSONB, nullable=False))
                                for suffix in ('records', 'assets', 'state'))
    return _tables[source]


bookkeeping = Table('bookkeeping', _metadata, Column('key', Text, primary_key=True), Column('payload', JSONB, nullable=False))


def initialize():
    for source in SOURCES:
        tables(source)
    with transaction() as connection:
        connection.execute(text('CREATE SCHEMA IF NOT EXISTS ingestion'))
        _metadata.create_all(connection)
        connection.execute(insert(bookkeeping).values(key='schema_version', payload=1).on_conflict_do_nothing())


class Repository:
    def __init__(self, source):
        self.source = source
        self.tables = tables(source)
        self.baseline = None
        self.owner = _owner.get()

    def load(self):
        with transaction() as connection:
            groups = [{decode_string(k):transform(v, decode_string) for k,v in connection.execute(select(t.c.key, t.c.payload))} for t in self.tables]
        records, assets, state = groups
        data = {'schema_version': 1, 'source': self.source, **state, 'records': records, 'assets': assets}
        self.baseline = copy.deepcopy(data)
        return data

    def load_status(self):
        """One read-only snapshot of current evidence, with SQL history counts.

        This deliberately does not establish a writable baseline. Historical
        observations/results stay in PostgreSQL; publication needs latest results.
        """
        self.baseline = None
        records, assets, state = self.tables
        r, a = records.c.payload, assets.c.payload
        def latest_array(value):
            return case((func.jsonb_typeof(value) == 'array',
                         case((func.jsonb_array_length(value) > 0,
                               func.jsonb_build_array(value[-1])), else_=func.jsonb_build_array())),
                        else_=func.jsonb_build_array())
        record_view = func.jsonb_build_object(
            'observations', latest_array(r['observations']),
            'attachment_count', r['attachment_count'],
            'imported_acquisition_complete', r['imported_acquisition_complete'])
        for name in ('pdf', 'package_pdf'):
            value = r[name]
            output = func.jsonb_build_object('results', latest_array(value['results']))
            for field in ('status', 'current_results'):
                output = output.op('||')(case((value.has_key(field),
                                              func.jsonb_build_object(field, value[field])),
                                             else_=func.jsonb_build_object()))
            record_view = record_view.op('||')(case((r.has_key(name), func.jsonb_build_object(name, output)),
                                                   else_=func.jsonb_build_object()))
        if self.source == 'common_crawl':
            record_view = func.jsonb_build_object(
                'path_to_file', r['path_to_file'], 'uploaded', r['uploaded'], 'sha256', r['sha256'])
        asset_fields = ('status', 'current', 'kind', 'unsupported_code', 'record_key',
                        'record_url', 'observation_id', 'source_version', 'verified_source_version')
        # Omit absent keys: absence has different semantics from JSON null.
        asset_view = func.jsonb_build_object('results', latest_array(a['results']))
        for name in asset_fields:
            asset_view = asset_view.op('||')(case((a.has_key(name), func.jsonb_build_object(name, a[name])),
                                                 else_=func.jsonb_build_object()))
        keys = ('discovery', 'discovery_scan', 'discovery_errors', 'discovery_error_history',
                's3_publications', 'candidates', 'litres_catalog', 'milli_catalog', 'publications', 'last_run')
        with transaction() as conn:
            # All three views and the aggregate observe the same database snapshot.
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            record_data = {decode_string(k): transform(v, decode_string) for k, v in
                           conn.execute(select(records.c.key, record_view))}
            asset_data = {decode_string(k): transform(v, decode_string) for k, v in
                          conn.execute(select(assets.c.key, asset_view))}
            state_data = {decode_string(k): transform(v, decode_string) for k, v in
                          conn.execute(select(state.c.key, state.c.payload).where(state.c.key.in_(keys)))}
            history_count = conn.scalar(select(func.coalesce(func.sum(
                func.jsonb_array_length(func.coalesce(a['results'], func.jsonb_build_array()))), 0)).select_from(assets))
        return {'schema_version': 1, 'source': self.source, **state_data,
                'records': record_data, 'assets': asset_data, '_historical_results': history_count}

    def save(self, data, connection=None):
        assert_ownership(owner=self.owner)
        if self.baseline is None:
            raise RuntimeError('Load repository before saving')
        def write(conn):
            for table, group in zip(self.tables, ('records', 'assets', None)):
                current = data[group] if group else {k:v for k,v in data.items() if k not in {'records','assets','source','schema_version'}}
                previous = self.baseline[group] if group else {k:v for k,v in self.baseline.items() if k not in {'records','assets','source','schema_version'}}
                rows = [{'key':encode_string(k), 'payload':transform(v, encode_string)} for k,v in current.items() if k not in previous or v != previous[k]]
                for start in range(0, len(rows), 250):
                    statement = insert(table).values(rows[start:start+250])
                    conn.execute(statement.on_conflict_do_update(index_elements=['key'], set_={'payload':statement.excluded.payload}))
                removed = previous.keys() - current.keys()
                if removed:
                    conn.execute(delete(table).where(table.c.key.in_([encode_string(k) for k in removed])))
        if connection is None:
            with transaction() as conn:
                write(conn)
        else:
            write(connection)
        self.baseline = copy.deepcopy(data)
