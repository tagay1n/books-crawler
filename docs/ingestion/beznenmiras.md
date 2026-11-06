# Безнең мирас issue archive

Add the following entry to the selected operational YAML under `sources`:

```yaml
beznenmiras:
  archive_url: https://beznenmiras.ru/categories/widget/list/svezii-vypusk
```

```bash
.venv/bin/python cli.py --config config/sources/beznenmiras.yaml discover --source beznenmiras --max-pages 1
.venv/bin/python cli.py --config config/sources/beznenmiras.yaml download --source beznenmiras --limit 1
.venv/bin/python cli.py --config config/sources/beznenmiras.yaml status --source beznenmiras
```

Discovery follows the native «Саннар» issue archive and its forward pagination.
The page cap applies to listings; linked issue records are inspected before moving
to the next listing. Interrupted scans resume from PostgreSQL checkpoints. Source
identity uses the issue URL slug, including the observed `7-2025` spelling;
titles are not identity keys. Metadata retains issue number/year claims, displayed
date, description, cover URL, catalog context, and document links. These claims
do not establish document language or completeness. This source is distinct from
Miras (`miras.info`) and Безнең гәҗит (`beznen.ru`).

Only supported original document links inside `.single__content` become assets.
Footer policy PDFs, cover images, and article/navigation links are excluded.
External document links remain inspectable as unsupported; requests and redirects
stay on the configured HTTPS origin. Same-origin originals use the shared bounded
downloader, SHA-256/MD5, immutable local files, and recheck behavior. No page images
are assembled and no PDF is generated from HTML.

Issues without document links remain metadata-only records with an explicit
`acquisition_note`; `status` counts them as `records_without_attachments`.
An empty download queue does not mean complete journal issues were acquired.
Artifacts live under `<artifacts_root>/beznenmiras/`. The initial live inspection
on 2026-10-28 found 41 issue cards across three listing pages, from April 2023
through October 2026, with gaps. Sample issue pages exposed cover/issue metadata
but no document links. The archive supplies no independent total count; do not
infer complete publication coverage from traversal completion.

Manual CLI verification completed all 41 issue records in 44 HTTP requests,
split across two invocations to verify page-cap recovery (one listing followed
by two). Both invocations finished without errors. Every inspected issue had zero
document attachments; the download phase made zero requests and acquired no files.
This verifies metadata discovery and resume behavior, not original-file acquisition.
The isolated verification manifest and summaries are under
`/tmp/beznenmiras-verification/beznenmiras/`.

## Metadata and execution

Parser version 2 also preserves publisher content HTML (`content_html`), issue lead
(`lead_raw` when present), raw subscription-index paragraphs, relevant HTML meta
tags, content links and embedded-reader evidence. Existing normalized fields and
`issue:<slug>` identities remain unchanged. HTML is upstream evidence, not a
generated magazine or a safe-to-render page. Reader links remain unsupported
until their delivery is verified. Subscription indexes do not establish language.

Metadata observations, discovery frontier, download results and S3 receipts live
in PostgreSQL. Set `DATABASE_URL` and initialize the schema once with
`.venv/bin/python cli.py database init`; processing does not initialize it or fall
back to local JSON. See [database operations](../postgres-migration.md).

After configuring `S3_BUCKET` and standard AWS credentials, run the complete
pipeline locally:

```bash
.venv/bin/python cli.py --summary-only --config config/sources/beznenmiras.yaml run --source beznenmiras
.venv/bin/python cli.py --summary-only --config config/sources/beznenmiras.yaml publish --source beznenmiras --target s3
```

`download` retains originals locally without publishing; `run` downloads and
publishes finished documents using shared checkpoints. Standalone `publish`
retries publication from local files. Originals remain under the configured
artifact root. No metadata-only records or covers are uploaded as magazines.

The **Ingest beznenmiras** GitHub workflow supports manual dispatch and uses the
shared runner. Required repository secrets are `DATABASE_URL`, `S3_BUCKET`,
`AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY`; `AWS_SESSION_TOKEN` is optional.
Optional variables are `S3_ENDPOINT_URL` and `AWS_DEFAULT_REGION`. Initialize the
database before dispatch. The workflow retains durable state in PostgreSQL and
published documents in S3; runner-local files are temporary. No schedule is added.
See [runner operations](../scheduled-ingestion.md) for limits and recovery.

## Bounded review, 2026-11-07 (Europe/Moscow)

Native homepage navigation advertises the configured issue archive. All three
listing pages returned HTTP 200 and parsed as 15 + 15 + 11 distinct issue cards,
ending at April 2023; forward pagination stops on page 3. October 2026 and April
2023/2024 issue pages exposed no document attachments or embedded readers in
issue content. Footer policy PDFs remain excluded. The public robots file allows
crawling and advertises a sitemap index; that index was inspected separately
from crawler routes. This is bounded evidence, not exhaustive file availability.

Manual verification used `cli.py inspect`, configured adapter parsing of retained
responses, `cli.py sources --details --source beznenmiras`, module compilation,
and workflow generator/configuration inspection. Evidence is in ignored
`__artifacts/inspections/2026-11-06T21-*` directories (UTC), plus the October issue
and homepage responses under `2026-11-06T17-53-*` and `2026-11-06T18-03-*`.
No original was found in these samples. Live checkpoint/resume, acquisition,
hash skipping and upload/receipt checks remain unverified: this shell had no
PostgreSQL or S3 credentials. No bulk acquisition, remote publication or workflow
dispatch was performed, and no automated tests were added.
