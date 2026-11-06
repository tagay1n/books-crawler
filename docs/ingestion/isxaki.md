# Isxaki books and works

Add `sources.isxaki.archive_url: https://isxaki.com/ijat/` to the operational YAML,
or copy the entry from the example configuration. No credentials are required.

```bash
.venv/bin/python cli.py --config config/sources/isxaki.yaml discover --source isxaki
.venv/bin/python cli.py --config config/sources/isxaki.yaml download --source isxaki --limit 1
.venv/bin/python cli.py --config config/sources/isxaki.yaml run --source isxaki --limit 1
.venv/bin/python cli.py --config config/sources/isxaki.yaml status --source isxaki
```

Discovery covers these five collections: `/ijat/kitaplar/` (original editions),
`/ijat/asarlar/` (1896–1907), `/asarlar-1908-1918-ellar/` (1908–1918),
`/1919-1947/`, and `/ijat/about/kitaplar/` (books about Iskhaki).
The entry point and five collection listing requests consume six discovery pages;
each collection is also inspected as a record through the shared discovery core.
A lower page cap resumes the saved frontier on the next invocation.

Each collection is one source record. Its metadata retains the book cards,
supplied bibliographic descriptions, cards without attachments, and source notes.
Document links within cards become assets; repeated links within a collection
share an asset, while overlapping collections retain separate provenance.
HTTP links on the source host are normalized to HTTPS and the observed `/tt/`
collection aliases are normalized to their canonical paths. Original link URLs
remain in card metadata. Navigation, cover images, news, letters, and diaries
are outside this adapter's scope. External document links remain unsupported.
Transport uses the shared GET-only guard with the existing native HTTPS-origin
rule, including same-origin redirects. External redirects and HTTP downgrades
remain rejected; link normalization does not relax the transport origin check.

Both historical editions and supplied modern text PDFs are eligible. Files are
saved unchanged under `__artifacts/ingestion/isxaki/files/` with PostgreSQL-backed
processing state, SHA-256/MD5, integrity checks, budgets, and recheck behavior. HTML-only
texts remain metadata; no HTML/text artifact or PDF is generated. A title or
bibliographic claim does not establish language, edition accuracy, or completeness.
Malformed or broken file links are retained and reported when downloads fail;
they are not silently repaired or dropped.

The 2026-10-27 live check completed all five configured collections in six
listing requests and five record requests: 64 document relationships pointing
to 63 unique file URLs. It downloaded “Бай углы” (31,535,638 bytes), verified the
saved SHA-256/MD5, size, and observation link, and checked that a repeated CLI
download skipped an isolated copy of the completed sample with zero requests.
The other 63 relationships remain pending; their file availability and integrity
have not been verified. Traversal completion covers these five sections, not
the entire website, and the source supplies no independent catalog count.

## Metadata and execution

Parser version 2 preserves each card's description HTML, cover URL and
non-document link evidence in addition to existing bibliographic text and file
links. Cards without supported file links have an explicit metadata-only note.
Per-collection `file_counts` distinguish eligible documents, held documents and
cards without document links. Repeated URLs across collections retain their
existing provenance; summed relationships are not a unique-file count. Raw HTML
is evidence, not trusted renderable content. Covers and HTML-only works are never
acquired or converted to documents. Existing source URLs, asset identities and
file selection remain unchanged; publisher-supplied modern PDFs remain eligible.

PostgreSQL stores observations, frontier checkpoints, processing results, errors
and S3 receipts. Set `DATABASE_URL` and initialize the schema once with
`.venv/bin/python cli.py database init`; processing does not initialize it or
fall back to JSON. See [database operations](../postgres-migration.md).

`download` retains originals locally. `run` downloads and publishes finished
documents to S3 after committed checkpoints, retaining local files. Standalone
`publish` retries from local files and reports missing originals:

```bash
.venv/bin/python cli.py --summary-only --config config/sources/isxaki.yaml run --source isxaki --max-pages 6 --limit 1
.venv/bin/python cli.py --summary-only --config config/sources/isxaki.yaml publish --source isxaki --target s3 --limit 1
```

Set `S3_BUCKET` and standard AWS credentials for publication. Shared S3 transfer
uses deterministic keys, SHA-256 metadata and PostgreSQL receipts. Fresh runners
reacquire missing unpublished inputs; receipts allow published originals to be
skipped. Metadata-only cards and unsupported links never become published books.

The existing **Ingest isxaki** workflow supports manual dispatch through the
shared runner and `config/scheduled.yaml` limits. No schedule is added. Initialize
PostgreSQL before dispatch. Required repository secrets: `DATABASE_URL`,
`S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. Optional:
`AWS_SESSION_TOKEN`; repository variables `S3_ENDPOINT_URL` and
`AWS_DEFAULT_REGION`. Runner-local files are temporary; PostgreSQL and S3 retain
durable state and published originals. See
[runner operations](../scheduled-ingestion.md) for budgets and recovery.

## Bounded review, 2026-11-07 (Europe/Moscow)

Live entry-point navigation and all five configured collections were inspected:
six requests, no retries, 83 cards and 64 eligible document relationships pointing
to 63 unique file URLs. Sixteen cards expose no supported file link. Two cards
contain the malformed `http://3hatinile` target; version 2 retains it as metadata
evidence and never requests it. All retained collection responses were re-parsed
with version 2. No new collection, guessed filename or external download route
was introduced. Traversal covers the configured sections, not the entire website.

One publisher-linked modern text PDF, «Мансур» (`4-mansur.pdf`), was acquired:
437,423 bytes, five pages, SHA-256
`b0189c67795b77ab34d0f373b28136f97832720d78a17f89fee6681d50039710`,
MD5 `82b3c216016ab5b8f2251b9adfe668ba`. Declared response length and PDF signature
passed; rendered page 2 contains Tatar text. These are computed hashes, not
publisher-supplied checksum matches. The crawler downloaded the existing PDF
unchanged; it did not generate a document from webpage text. Other files'
availability, language composition and printed completeness were not refreshed.

Evidence is ignored under `__artifacts/isxaki-review-20261107/`: six page bodies,
records/summary exports and sample PDF/render/hash report. These review exports
are not operational state. Compilation, configured parsing, file counts,
capability listing, scheduled profile loading, manual workflow generator equality
and `git diff --check` passed. No automated tests were added. The sample used
shared HTTP/native guards and format validation, not the full database-backed
acquisition stage. Database/storage credentials were unset, so live checkpoint/
resume, repeat-run skipping and S3 receipts remain unverified. No production
database writes, S3 uploads or workflow dispatch occurred.
