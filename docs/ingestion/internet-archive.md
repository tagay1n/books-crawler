# Internet Archive originals

Configure `sources.internet_archive.archive_url: https://archive.org` in the
operational YAML. No login, borrowing credentials, or new dependencies are needed.

```bash
.venv/bin/python cli.py --config config/sources/internet_archive.yaml discover --source internet_archive --max-pages 2
.venv/bin/python cli.py --config config/sources/internet_archive.yaml download --source internet_archive --limit 1
.venv/bin/python cli.py --config config/sources/internet_archive.yaml run --source internet_archive --max-pages 2 --limit 1
.venv/bin/python cli.py --config config/sources/internet_archive.yaml status --source internet_archive
.venv/bin/python cli.py --config config/sources/internet_archive.yaml download --source internet_archive --recheck --limit 1
```

The fixed query is `mediatype:texts AND (language:tat OR language:tt OR language:tatar)`.
Advanced Search requests 100 identifiers per listing page, sorted by identifier
ascending; each item's metadata is fetched independently through the metadata API.
Listing offsets, batch sizes, duplicate identifiers, and totals are validated.
After the last page, an additional listing request verifies the total against the
unique enumerated items. It consumes the page budget too. Ordinary numbered
pagination is used because live GET and POST cursor-continuation checks on the
scrape API returned `Bad cursor` for the supplied cursor.

An incomplete discovery resumes pending metadata requests and the listing
frontier. Changed totals or duplicate identities require a fresh scan while
retaining metadata and acquired files. Failed/refused pages remain unresolved;
the adapter does not silently switch queries or skip search-window errors.
Completion describes a traversal of the current search index, not a transactional
snapshot. Subsequent scans start fresh, and partial scans never establish removal.
The existing deadline, pacing, retries, and 2 MiB metadata-response cap apply.

Current item metadata must contain an exact, case-insensitive `tat`, `tt`, or
`Tatar` language label. Multilingual items with an explicit Tatar label qualify.
Missing or malformed labels hold document assets as `language_unknown`; other
labels hold them as `language_excluded`. Crimean Tatar alone does not qualify.
Titles, descriptions, and interface language are not substitutes for these labels.
Language claims are preserved as supplied; no content-language detection runs.

An item identifier is the source record identity; the exact native filename is
the asset identity. Item metadata, the complete supplied file inventory, and
per-file selection reasons remain inspectable. Only supported document files
marked `source=original` are eligible. Derivatives, archives/page packages, images,
HTML, and metadata files remain inventory evidence; private or restricted
document assets are held with explicit reasons. An Archive original upload does
not establish that it is an authentic or complete historical original.

Downloads use canonical `/download/<identifier>/<filename>` URLs, including
correctly encoded Unicode and nested filenames. HTTPS storage-host redirects
must remain under Archive-owned hosts and preserve the exact item and filename
on every hop. Storage-host URLs are response evidence, not durable source locators.
Other adapters retain their existing origin restrictions.

Files are stored unchanged under `__artifacts/ingestion/internet_archive/files/`.
Transfers compute SHA-256 and MD5 and check supplied file size and MD5 when
present before publishing success. Invalid supplied integrity metadata remains
unresolved; mismatches fail acquisition. SHA-256 is still computed when no
upstream MD5 is available. Basic format checks do not assess document quality.
File MD5, size, and modification hints form a source-version fingerprint.
Changed hints trigger acquisition under the same asset identity without stale
conditional headers; earlier results remain retained. Metadata-only changes
leave verified downloads reusable. Byte-identical rechecks update the asset's
verified version without rewriting its original acquisition evidence.

The 2026-10-27 live check inspected 200 items over two listing pages with no
errors or retries and retained 414 eligible original document assets plus three
metadata-only records. The search advertised 5,295 items. The configured page cap
left the overall scan incomplete, with page 3 checkpointed for continuation;
the 414 normal-queue assets remain pending rather than being bulk downloaded.
An isolated pilot under `internet_archive/pilot/` acquired the original
Шиһабетдин Мәрҗани PDF (2,306,792 bytes). Its computed MD5 matched Archive's
`3e07e2a6a70bb4bbfaa4411117f4ce1b`; SHA-256 was
`529b80a546d2c42fea725e9cf818858e21969604382c2b86866b51f3fa55070a`.
The pilot verified the observation link and repeated the CLI download with one
skip and zero network requests. This sample establishes transfer/integrity
behavior, not complete corpus coverage or verified content language.

## File-only outputs and processing

This source acquires actual publisher/uploader-exposed original document files.
It does not extract webpage text, convert HTML to documents, or publish item
descriptions as books. `mediatype:texts` is Archive's catalog category, not a
request to scrape website text. Supported original PDFs, DjVu, EPUB and other
document files follow the existing format policy; derived OCR text and generated
PDF/EPUB files remain excluded. A document uploaded as an original `.txt` file is
a file candidate; that differs from extracting text from a webpage.

Parser version 2 adds per-item `file_counts`: eligible original documents, held
original documents, and ignored inventory entries. `acquisition_note` explicitly
identifies items without an eligible public document. These counts describe
candidate files, not completed downloads or verified file availability. Search
item totals must never be presented as downloadable-file totals. Item metadata,
all supplied file entries and per-file reasons remain in PostgreSQL for provenance,
admission and retries. Native item/filename identities and integrity hints remain
unchanged; the observation refresh does not invalidate unchanged acquired bytes.

PostgreSQL stores observations, discovery frontier/checkpoints, processing results,
errors and S3 receipts. Set `DATABASE_URL` and initialize the schema once using
`.venv/bin/python cli.py database init` before processing. Normal commands do not
initialize it or fall back to JSON. Local originals stay under the configured
artifact root (`__artifacts/ingestion/internet_archive/` by default). See
[database operations](../postgres-migration.md).

`download` retains originals locally. `run` downloads originals and publishes
finished documents to S3 after committed checkpoints, retaining local files.
Standalone `publish` retries from local files and reports missing originals:

```bash
.venv/bin/python cli.py --summary-only --config config/sources/internet_archive.yaml run --source internet_archive --max-pages 1 --limit 1
.venv/bin/python cli.py --summary-only --config config/sources/internet_archive.yaml publish --source internet_archive --target s3 --limit 1
```

Set `S3_BUCKET` and standard AWS credentials for publication. Shared publication
uses deterministic keys, SHA-256 metadata and PostgreSQL receipts. Fresh runners
reacquire missing unpublished originals while receipts allow published files to
be skipped. Metadata-only items and held files are never uploaded as documents.

The existing **Ingest internet_archive** workflow supports manual dispatch through
the shared runner and `config/scheduled.yaml` limits. No schedule is added.
Initialize PostgreSQL before dispatch. Required repository secrets:
`DATABASE_URL`, `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. Optional:
`AWS_SESSION_TOKEN`; repository variables `S3_ENDPOINT_URL` and
`AWS_DEFAULT_REGION`. Runner-local files are temporary; PostgreSQL and S3 retain
durable state and published originals. See
[runner operations](../scheduled-ingestion.md) for budgets and recovery.

## Bounded review, 2026-11-07 (Europe/Moscow)

Two native search pages each enumerated 100 identifiers; ten item inventories
from each were inspected (20 total, 22 requests, no retries/errors). Search
advertised 5,343 items. This is a partial sample, not a completed discovery scan
or a corpus-wide downloadable-file count. The API was inspected independently
before the adapter run and a separate current inventory confirmed an exposed
original PDF. No webpage text was acquired or converted.

The 20 sampled inventories contain 47 eligible original PDFs, zero held originals
and 567 ignored entries: 467 derivatives, 80 unsupported formats and 20 entries
with unknown origin. All 47 candidates have supplied MD5 and size metadata.
Every sampled item has at least one eligible file; metadata-only/restricted/
missing-language cases were inspected in code rather than freshly sampled live.
All item metadata, file inventories and per-file decisions remain in the review
records and in operational PostgreSQL observations when real discovery is run.

One bounded original transfer verified the Unicode filename and exact item/file
identity through a native storage redirect: item `07-08-2018-no-85`, file
`07-08-2018_ШахриКазан_№85.pdf`, 1,945,345 bytes, eight PDF pages. Measured MD5
`2eb1f2230a35d887ad8c1d957a8e792c` and size match Archive's supplied metadata;
SHA-256 is `2a3bc3addf107550afacff3ea3b610623c2f52546c6780511976757711017d11`.
The response length and PDF signature passed; rendered page 2 contains Tatar
newspaper text. This sample is a newspaper file, not a standalone book; no
printed-completeness or corpus-wide language claim is inferred. No bulk original
acquisition occurred. The other 46 files are candidates, not verified downloads.

Evidence is ignored under `__artifacts/internet-archive-review-20261107/`: two
listing responses, 20 item responses, records/catalog/summary exports, and sample
PDF/render/hash report. Independent inspection responses are under
`__artifacts/inspections/2026-11-06T21-52-*` and `2026-11-06T21-53-*` (UTC).
Review exports are not operational state.

Configured parsing, eligibility counts, native redirect identity checks,
source size/MD5 validation, compilation, capability listing, scheduled profile
loading, manual workflow generator equality and `git diff --check` passed.
No automated tests were added. Existing PostgreSQL/S3/manual Actions integration
is retained. The sample used shared HTTP transport and adapter integrity
callbacks, not the full database-backed acquisition stage. Database/storage
credentials were unset, so live persistence/resume, repeat-run skipping and S3
upload receipts remain unverified. No production writes, S3 uploads or workflow
dispatch occurred.
