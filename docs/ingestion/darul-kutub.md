# Darul-Kutub originals

Darul-Kutub follows the search catalog's native next-page links. Article results
map to their parent book or journal issue; reader page hints do not create new
publications. Coverage counts raw search rows separately from unique publications.
Adjacent pages can contain different articles from the same issue, so repeated
pages are detected using row titles, links, and source text together.

Publication metadata preserves titles, authors, publisher, description, and raw
bibliographic details when supplied. Language labels remain in the source text;
no inferred language field is added. All exposed original file parts are queued,
including parts in hidden volume tabs. Direct reader originals are preferred over
download buttons of the same format; button URLs remain metadata evidence, and
other offered formats remain eligible. Button-route IDs are not publication IDs.
The adapter does not assume that reader and button responses contain identical
bytes. Unsupported originals remain visible in the backlog.

Parser version 2 preserves each search row in the parent publication's
`catalog_context`, including article titles/authors, reader-page hints and raw
table fields (language, date, pages, publisher, printery, subjects, source and
alternate titles when exposed). The shared frontier accumulates relationships
across listing pages and revisits a publication when new context appears.
These are upstream claims, not normalized language or completeness decisions.
Book identities remain `book:<id>`; article IDs and download-button IDs never
replace them. Repeated scans with the same upstream context are deterministic.

Publication observations also retain badges, subjects, cover URL when exposed,
descriptive HTML, and literal chapter-list JSON with its unknown fields, authors,
page ranges and volume association. Unparseable chapter bindings remain raw
evidence instead of rejecting an otherwise downloadable original. No JavaScript
is evaluated. HTML is source evidence and must not be rendered as trusted markup.
The source scope continues to include all catalog languages.

## Local processing and S3

Select the existing operational YAML explicitly. Set `DATABASE_URL` and initialize
the schema once with `.venv/bin/python cli.py database init`; normal ingestion
does not initialize it or fall back to JSON. PostgreSQL retains observations,
frontier checkpoints, processing results, errors and publication receipts.
Original files remain under the configured artifact root (`__artifacts/ingestion/
darul_kutub/` by default). See [database operations](../postgres-migration.md).

```bash
.venv/bin/python cli.py --summary-only --config config/sources/darul_kutub.yaml discover --source darul_kutub --max-pages 2
.venv/bin/python cli.py --summary-only --config config/sources/darul_kutub.yaml download --source darul_kutub --limit 1
.venv/bin/python cli.py --summary-only --config config/sources/darul_kutub.yaml status --source darul_kutub
.venv/bin/python cli.py --summary-only --config config/sources/darul_kutub.yaml run --source darul_kutub --max-pages 2 --limit 1
.venv/bin/python cli.py --summary-only --config config/sources/darul_kutub.yaml publish --source darul_kutub --target s3 --limit 1
```

`download` is local. `run` downloads originals and publishes finished files to S3
after committed checkpoints; local originals remain intact. Configure `S3_BUCKET`
and standard AWS credentials. Shared S3 publication uses deterministic keys,
SHA-256 object metadata and PostgreSQL receipts. Standalone `publish` retries from
local files and reports missing files. Fresh-runner recovery reacquires missing
unpublished inputs; published originals can be skipped using receipts. No raw
HTML, catalog evidence, unsupported readers or cover images are published as books.

## Manual GitHub workflow

**Ingest darul_kutub** already supports `workflow_dispatch` through the shared
runner; no recurring trigger is added. Initialize PostgreSQL before dispatch.
Required repository secrets: `DATABASE_URL`, `S3_BUCKET`, `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`. Optional: `AWS_SESSION_TOKEN`; repository variables
`S3_ENDPOINT_URL` and `AWS_DEFAULT_REGION`. The runner uses
`config/scheduled.yaml` limits. Runner-local files are temporary; PostgreSQL and
S3 hold durable progress and published originals. See
[runner operations](../scheduled-ingestion.md) for budgets and recovery.

## Bounded review, 2026-11-07 (Europe/Moscow)

Inspected the native public search catalog and its independently advertised
books-only filter. The main catalog advertises 15,573 search rows, including
articles; the books filter advertises 1,591 rows. These are not verified unique
publication totals. The first two main listing pages each contain 20 rows and
share one parent issue; their fingerprints differ and pagination advances to
page 3. All 40 sampled rows now have retained per-publication context.
Publication samples `/books/3160/` (Шура) and `/books/2245/` (biography) expose
same-origin direct PDFs. Шура's chapter tree and distinct download-button URL are
retained; the direct file stays preferred. No full catalog scan was performed.

A bounded transfer of book 2245 acquired 7,823,809 bytes with a valid PDF signature
and complete declared length, SHA-256
`0fcf41ff9db66d90ff05eee3f46b4a446a3fa48ed8548daf72206661659adfa7`
and MD5 `e64cb8b35d732259d9b6474e62c05367`. `pdfinfo` reports 29 pages;
the catalog's 27-page label is retained as an upstream claim, not rewritten.
Rendered pages 3 and 5 show a historical scan with a Russian censor imprint and
Arabic-script narrative. No per-file language or printed completeness claim was
inferred from the render. The source has no publisher checksum for this sample.

Evidence is ignored under `__artifacts/darul-kutub-review-20261107/`; retained
HTTP responses are in `__artifacts/inspections/2026-11-06T21-32-*` and
`2026-11-06T21-33-*` (UTC). These review exports are not processing state.
Manual adapter parsing verified row contexts, chapter metadata, file selection
and pagination; compilation, capability listing, scheduled profile loading,
workflow generator equality and `git diff --check` passed. No automated tests
were added. PostgreSQL/S3 credentials were absent, so durable resume, full
database-backed acquisition, repeat-run skipping and upload receipts remain
unverified. The sample transfer used shared HTTP transport and format validation,
not the full database-backed acquisition stage. No production state, S3 objects
or GitHub workflow runs were changed.
