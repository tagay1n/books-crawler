"""Catalog registration after verified Milli uploads; the catalog owns MD5 indexing."""
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from .state import now


def document_status(operation, steps):
    """Decide new/duplicate/our recovered publication in one database snapshot."""
    yandex, s3 = steps.get('yandex'), steps.get('s3')
    yandex = yandex if isinstance(yandex, dict) else {}
    s3 = s3 if isinstance(s3, dict) else {}
    with operation.transaction() as connection:
        return connection.scalar(text("""
            SELECT CASE
                WHEN NOT EXISTS (SELECT 1 FROM monocorpus.downloaded_documents
                                 WHERE md5=decode(:md5,'hex')) THEN 'new'
                WHEN EXISTS (
                    SELECT 1 FROM monocorpus.catalog_locations y
                    JOIN monocorpus.catalog_locations s ON s.md5=y.md5
                    WHERE y.md5=:md5 AND y.provider='yandex' AND y.purpose='source'
                      AND y.source_path=:path AND s.provider='s3' AND s.purpose='primary'
                      AND s.locator=:url
                ) AND EXISTS (SELECT 1 FROM monocorpus.library_upstream_metadata WHERE md5=:md5)
                THEN 'complete' ELSE 'duplicate'
            END
        """), {'md5': operation.md5, 'path': yandex.get('path'), 'url': s3.get('url')})


def register_document(operation, steps, metadata):
    """Preserve existing catalog decisions and commit metadata, locations and MD5 together."""
    yandex, s3 = steps['yandex'], steps['s3']
    md5 = operation.md5
    with operation.transaction() as connection:
        exists = connection.scalar(text("SELECT EXISTS (SELECT 1 FROM monocorpus.downloaded_documents WHERE md5=decode(:md5,'hex'))"), {'md5': md5})
        if exists:
            return False
        payload = {'md5': md5, 'mime_type': 'application/pdf', 'ya_path': yandex['path'],
                   'full': True, 'sharing_restricted': False, 'document_url': s3['url'],
                   'primary_storage_size': s3['size'], 'primary_storage_etag': s3['etag'],
                   'primary_storage_verified_at': now()}
        # Insert-only policy: the explicit empty update allowlist preserves every
        # existing Yandex, derived, review and primary-storage field on conflict.
        statement = text("""
            SELECT monocorpus.catalog_upsert(
                'document', :payload, ARRAY['md5']::text[], ARRAY[]::text[])
        """).bindparams(bindparam('payload', type_=JSONB))
        connection.execute(statement, {'payload': payload})
        # Preserve any previously supplied raw context instead of overwriting it.
        statement = text("""
            INSERT INTO monocorpus.library_upstream_metadata(md5,payload_json)
            VALUES (:md5,:payload) ON CONFLICT(md5) DO NOTHING
        """).bindparams(bindparam('payload', type_=JSONB))
        connection.execute(statement, {'md5': md5, 'payload': metadata})
        return True
