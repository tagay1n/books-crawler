"""Manzara-compatible per-MD5 storage coordination on one reserved session."""
from contextlib import contextmanager
from dataclasses import dataclass
import re
import sys

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from .database import assert_ownership, engine


class DocumentOperationBusy(RuntimeError):
    """Another catalog/storage operation owns this MD5; retry later."""


@dataclass
class DocumentOperation:
    connection: Connection
    md5: str
    backend: int

    def _check_session(self):
        if self.connection.closed or self.connection.invalidated:
            raise RuntimeError('Document operation lost its database session')
        if self.connection.in_transaction():
            raise RuntimeError('Document operation requires a closed SQL transaction')

    def check(self):
        """Probe before remote writes; never reconnect a lost owning session."""
        self._check_session()
        try:
            backend = self.connection.scalar(text('SELECT pg_backend_pid()'))
            self.connection.rollback()
            if backend != self.backend:
                raise RuntimeError('Document operation database session changed')
        except SQLAlchemyError:
            self.connection.invalidate()
            raise RuntimeError('Document operation lost its database session') from None
        except BaseException:
            self.connection.invalidate()
            raise

    @contextmanager
    def transaction(self):
        """Keep catalog reads/writes on the session that owns the storage lock."""
        self._check_session()
        assert_ownership()
        try:
            with self.connection.begin():
                yield self.connection
        except SQLAlchemyError:
            raise RuntimeError('Catalog operation failed; transaction rolled back (connection details suppressed)') from None


@contextmanager
def document_operation(database_url, md5):
    if not isinstance(md5, str) or re.fullmatch(r'[0-9a-f]{32}', md5) is None:
        raise ValueError('Document MD5 must be lowercase hexadecimal')
    # Manzara uses hashtext(current_schema()) with search_path=monocorpus,public.
    # Our engine defaults to public, so name the shared namespace explicitly.
    parameters = {'identity': f'catalog-document-storage:{md5}'}
    try:
        with engine(database_url).connect() as connection:
            try:
                backend, locked = connection.execute(text("""
                    SELECT pg_backend_pid(), pg_try_advisory_lock(
                        hashtext('monocorpus'), hashtext(:identity))
                """), parameters).one()
                connection.rollback()
            except BaseException:
                # The server may have acquired the lock before the reply failed.
                connection.invalidate()
                raise
            if not locked:
                raise DocumentOperationBusy('Document is busy; retry on the next run')
            operation = DocumentOperation(connection, md5, backend)
            try:
                yield operation
            finally:
                body_failed = sys.exc_info()[0] is not None
                try:
                    operation._check_session()
                    unlocked = connection.scalar(text("""
                        SELECT pg_advisory_unlock(hashtext('monocorpus'), hashtext(:identity))
                    """), parameters)
                    connection.rollback()
                    if not unlocked:
                        raise RuntimeError('Document operation lock ownership was lost')
                except BaseException:
                    connection.invalidate()
                    if not body_failed:
                        raise RuntimeError('Document operation lock release failed') from None
    except SQLAlchemyError:
        raise RuntimeError('Catalog document lock failed (connection details suppressed)') from None
