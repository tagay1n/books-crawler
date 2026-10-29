# Безнең мирас issue archive

Add the following entry to the selected operational YAML under `sources`:

```yaml
beznenmiras:
  archive_url: https://beznenmiras.ru/categories/widget/list/svezii-vypusk
```

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source beznenmiras --max-pages 1
.venv/bin/python cli.py --config ingestion.yaml download --source beznenmiras --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source beznenmiras
```

Discovery follows the native «Саннар» issue archive and its forward pagination.
The page cap applies to listings; linked issue records are inspected before moving
to the next listing. Interrupted scans resume from the local manifest. Source
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
