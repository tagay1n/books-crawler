"""Catalog registration after verified Milli uploads; the catalog owns MD5 indexing."""
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from .database import transaction


def document_status(database_url, md5, steps):
    """Decide new/duplicate/our recovered publication in one database snapshot."""
    yandex, s3 = steps.get('yandex'), steps.get('s3')
    yandex = yandex if isinstance(yandex, dict) else {}
    s3 = s3 if isinstance(s3, dict) else {}
    with transaction(database_url) as connection:
        return connection.scalar(text("""
            SELECT CASE
                WHEN NOT EXISTS (SELECT 1 FROM monocorpus.downloaded_documents
                                 WHERE md5=decode(:md5,'hex')) THEN 'new'
                WHEN EXISTS (
                    SELECT 1 FROM monocorpus.catalog_locations y
                    JOIN monocorpus.catalog_locations s ON s.md5=y.md5
                    WHERE y.md5=:md5 AND y.provider='yandex' AND y.purpose='source'
                      AND y.resource_id=:resource_id AND s.provider='s3' AND s.purpose='primary'
                      AND s.locator=:url
                ) AND EXISTS (SELECT 1 FROM monocorpus.library_upstream_metadata WHERE md5=:md5)
                THEN 'complete' ELSE 'duplicate'
            END
        """), {'md5': md5, 'resource_id': yandex.get('resource_id'), 'url': s3.get('url')})


def register_document(database_url, md5, steps, metadata):
    """Preserve existing catalog decisions and commit metadata, locations and MD5 together."""
    yandex, s3 = steps['yandex'], steps['s3']
    with transaction(database_url) as connection:
        # Serialize the short check/insert against all catalog writers, including
        # the existing sync workflow, without holding a lock during uploads.
        connection.execute(text('LOCK TABLE monocorpus.catalog_documents IN SHARE ROW EXCLUSIVE MODE'))
        exists = connection.scalar(text("SELECT EXISTS (SELECT 1 FROM monocorpus.downloaded_documents WHERE md5=decode(:md5,'hex'))"), {'md5': md5})
        if exists:
            return False
        connection.execute(text("""
            INSERT INTO public.document
                (md5,mime_type,ya_path,ya_resource_id,ya_public_url,ya_public_key,
                 "full",sharing_restricted,document_url,primary_storage_size,
                 primary_storage_etag,primary_storage_verified_at)
            VALUES (:md5,'application/pdf',:path,:resource_id,:public_url,:public_key,
                    true,false,:url,:size,:etag,CURRENT_TIMESTAMP)
        """), {'md5': md5, **yandex, **s3})
        # Preserve any previously supplied raw context instead of overwriting it.
        statement = text("""
            INSERT INTO monocorpus.library_upstream_metadata(md5,payload_json)
            VALUES (:md5,:payload) ON CONFLICT(md5) DO NOTHING
        """).bindparams(bindparam('payload', type_=JSONB))
        connection.execute(statement, {'md5': md5, 'payload': metadata})
        return True
