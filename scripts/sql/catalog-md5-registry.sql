-- Apply in the catalog database, in the same transaction as the initial backfill.
-- The progress database must not own this table.
LOCK TABLE monocorpus.catalog_documents IN SHARE ROW EXCLUSIVE MODE;

CREATE TABLE IF NOT EXISTS monocorpus.downloaded_documents (
    md5 bytea PRIMARY KEY,
    CONSTRAINT downloaded_documents_md5_length CHECK (octet_length(md5) = 16)
);

CREATE OR REPLACE FUNCTION monocorpus.register_document_md5()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF NEW.md5 IS NULL OR NEW.md5 !~ '^[0-9A-Fa-f]{32}$' THEN
        RAISE EXCEPTION 'Document MD5 must contain exactly 32 hexadecimal characters';
    END IF;
    INSERT INTO monocorpus.downloaded_documents (md5)
    VALUES (pg_catalog.decode(NEW.md5, 'hex'))
    ON CONFLICT (md5) DO NOTHING;
    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION monocorpus.register_document_md5() FROM PUBLIC;

DROP TRIGGER IF EXISTS catalog_document_md5_registry ON monocorpus.catalog_documents;
CREATE TRIGGER catalog_document_md5_registry
AFTER INSERT OR UPDATE OF md5 ON monocorpus.catalog_documents
FOR EACH ROW EXECUTE FUNCTION monocorpus.register_document_md5();

INSERT INTO monocorpus.downloaded_documents (md5)
SELECT pg_catalog.decode(md5, 'hex') FROM monocorpus.catalog_documents
ON CONFLICT (md5) DO NOTHING;
