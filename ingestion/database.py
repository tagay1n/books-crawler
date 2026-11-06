"""Shared bounded PostgreSQL engines, transactions and source ownership."""
import atexit
import hashlib
import os
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

_engines = {}
_mutex = threading.Lock()
_owner = ContextVar('postgres_source_owner', default=None)


def engine(database_url=None):
    value = database_url or os.environ.get('DATABASE_URL')
    if not value:
        raise RuntimeError('DATABASE_URL is required; local persistence is no longer supported')
    try:
        url = make_url(value)
        if url.drivername in {'postgres', 'postgresql'}:
            url = url.set(drivername='postgresql+psycopg')
        if url.drivername != 'postgresql+psycopg':
            raise ValueError()
    except Exception:
        raise RuntimeError('Expected a PostgreSQL connection URL') from None
    with _mutex:
        if url not in _engines:
            if int(os.environ.get('PG_POOL_SIZE', '2')) < 2:
                raise RuntimeError('PG_POOL_SIZE must be at least two for source locks and transactions')
            _engines[url] = create_engine(
                url, pool_size=int(os.environ.get('PG_POOL_SIZE', '2')),
                max_overflow=0, pool_timeout=float(os.environ.get('PG_POOL_TIMEOUT', '30')),
                pool_pre_ping=True, hide_parameters=True,
                connect_args={'connect_timeout': int(os.environ.get('PG_CONNECT_TIMEOUT', '10'))})
        return _engines[url]


@contextmanager
def transaction(database_url=None):
    try:
        assert_ownership()
        with engine(database_url).begin() as connection:
            yield connection
    except SQLAlchemyError:
        raise RuntimeError('Postgres operation failed; transaction rolled back (connection details suppressed)') from None


def assert_ownership(force=True, owner=None):
    owner = owner or _owner.get()
    if owner:
        connection, backend, checked, mutex = owner
        with mutex:
            try:
                if not force and time.monotonic() - checked[0] < 1:
                    return
                if connection.scalar(text('SELECT pg_backend_pid()')) != backend:
                    raise RuntimeError('Source lock session changed; stop and restart this command')
                checked[0] = time.monotonic()
            except SQLAlchemyError:
                raise RuntimeError('Source lock connection lost; stop and restart this command') from None


@contextmanager
def source_lock(source):
    key = int.from_bytes(hashlib.sha256(('books-crawler:' + source).encode()).digest()[:8], 'big', signed=True)
    try:
        with engine().connect().execution_options(isolation_level='AUTOCOMMIT') as connection:
            if not connection.scalar(text('SELECT pg_try_advisory_lock(:key)'), {'key': key}):
                raise RuntimeError('Another command is already writing this source')
            token = _owner.set((connection, connection.scalar(text('SELECT pg_backend_pid()')), [time.monotonic()], threading.RLock()))
            try:
                yield
            finally:
                _owner.reset(token)
                try:
                    connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': key})
                except SQLAlchemyError:
                    connection.invalidate()
    except SQLAlchemyError:
        raise RuntimeError('Postgres source lock failed (connection details suppressed)') from None


@atexit.register
def dispose():
    for item in _engines.values():
        item.dispose()
