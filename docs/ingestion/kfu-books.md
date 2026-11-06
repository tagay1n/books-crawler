# KFU historical books and manuscripts

Use the selected `config/sources/kfu_books.yaml` or `kfu_manuscripts.yaml`.
Both collections use the same adapter but maintain independent PostgreSQL state
and discovery checkpoints. All records in the selected collections are admitted; supplied
language labels are retained without filtering or content-language inference.

The current books YAML sets `direct_files_only: true`: only eligible existing
document files are acquired, image readers remain metadata, and PDF assembly is
disabled. The reader/assembly behavior described below applies to manuscripts and
legacy configurations without direct-only mode. The manuscripts YAML is unchanged.

```bash
.venv/bin/python cli.py --config config/sources/kfu_books.yaml discover --source kfu_books --max-pages 1
.venv/bin/python cli.py --config config/sources/kfu_manuscripts.yaml discover --source kfu_manuscripts --max-pages 1
.venv/bin/python cli.py --config config/sources/kfu_books.yaml download --source kfu_books --limit 1
.venv/bin/python cli.py --config config/sources/kfu_manuscripts.yaml download --source kfu_manuscripts --limit 1
.venv/bin/python cli.py --config config/sources/kfu_books.yaml run --source kfu_books --max-pages 1 --limit 1
.venv/bin/python cli.py --config config/sources/kfu_books.yaml status --source kfu_books
.venv/bin/python cli.py --config config/sources/kfu_manuscripts.yaml status --source kfu_manuscripts
```

Discovery follows each collection's native `?offset=` links (currently 20 records
per page), with validated displayed ranges, counts, record identities, and next
offsets. A final root-page count check also consumes the discovery page budget.
Repeat `discover` to resume pending records and the listing frontier. Count changes
or repeated identities require a fresh scan without deleting historical evidence.
An earlier inspection advertised 135 books and 256 manuscripts; these were catalog
records, not public-PDF counts. The current books audit below found 136 records.
Traversal is not a transactional snapshot of the site.

Each record retains its native handle, Dublin Core metadata, bibliographic rows,
original-script titles, collection provenance, and per-file descriptions. Record
identity is the handle; asset identity is the bitstream sequence and native
filename within that handle. If the source changes a bitstream route, it creates
a new asset identity; earlier evidence remains retained. Changing a file's bytes
at the same URL requires an explicit `download --recheck` when no reliable
content-version hint is supplied.

Restriction labels are interpreted per `.fileBlock`, not across the entire book.
A file marked “Ограниченный доступ”, showing a lock, or offering “Запросить копию”
is held as `kfu_restricted`. A public PDF remains eligible even when the same
record's ZIP package is restricted. Supported direct document formats reuse the
shared downloader. HTML and ZIP packages remain metadata; archives are not expanded.
Thumbnails are skipped and duplicate thumbnail/download links do not create separate assets.

When no eligible public direct PDF is available, discovery resolves public
`Set of JPEG` readers. It checks the advertised bitstream range, numbered filename
endpoints, file count, and the reader's explicitly linked IIIF manifest. The manifest
must contain one sequence with the same number of canvases, numbered in order,
with distinct full JPEG resources. Original bitstream URLs are expanded only within
the declared sequence and numbered filename ranges; IIIF image derivatives and
thumbnails are not downloaded. Multiple sets are ordered by nonoverlapping bitstream
ranges. An unrecognized filename pattern (for example `001.jpg ... Целый.jpg`)
holds all public image sets in that record as `reader_unsupported` for review.
Reader fetch or malformed-manifest failures leave the record pending for retry.
Restricted readers are never fetched. Public direct PDFs take priority without
fetching the reader. Reader and manifest requests use the ordinary request pacing,
timeouts, retries, deadline, and 2 MiB text response cap.

KFU image PDFs use **200 DPI colour, JPEG quality 85**, with Lanczos downsampling,
EXIF orientation handling, retained RGB ICC profiles, and the original physical page
dimensions. No grayscale conversion or lower-resolution fallback is used. A source
JPEG without valid DPI metadata, below 200 DPI, or outside RGB/grayscale colour modes
prevents publication and remains available for review; images are not upscaled to
claim missing detail. The original JPEG bytes remain unchanged in `files/`.

In reader-enabled configurations, `--limit` counts each direct file or entire
image book as one item; current books mode counts direct files only. Completed image
downloads survive byte caps, deadlines, and interruptions. A later `download` resumes
from verified originals, and publishes `derived/<sha256>.pdf` atomically only after
every expected page is present and the PDF page count is verified. No incomplete
PDF is published. Policy, Pillow version, original hashes, source observation, page
order, and conversion version participate in the assembly fingerprint. Missing or
damaged PDFs are rebuilt; unchanged complete books are reused without network access.
`--recheck` revalidates original images. `status` reports `pdf_books` and `image_pages`.

The optional `limits.max_derived_pdf_bytes` bounds assembled PDFs separately from
individual downloaded originals. Its default is 536870912 bytes (512 MiB); the
existing `max_file_bytes` still bounds each original image/document. Both limits
are enforced, and assembly also respects the shared disk reserve and deadline.
Keeping originals requires additional disk space beyond the compressed PDF.

Discovery parser version 2 originally introduced page descriptors for image-only
records. Current direct-only books use parser version 4. Existing originals and
historical observations remain retained when a new policy refreshes discovery.

Restricted document URLs, names, displayed sizes, formats, and copy-request links
remain available in the manifest. Restrictions are not download failures, and
`status` reports held document assets in `unsupported_reasons.kfu_restricted`.
A later discovery that observes the same file as public can return it to the
download queue. An allegedly public file returning login/error HTML or an
unexpected redirect fails acquisition without becoming a successful document.

Files stay under `__artifacts/ingestion/kfu_books/files/` or
`__artifacts/ingestion/kfu_manuscripts/files/`, with the existing SHA-256/MD5,
byte/file limits, disk reserve, recovery, and atomic publication behavior.
Displayed sizes such as “17,53 MB” are approximate source descriptions; transfer
headers and actual acquired bytes provide integrity evidence. Requests are
read-only, anonymous, and restricted to the repository's HTTPS source routes.

Restricted-file follow-up is deferred: investigate whether registration or
institutional access can legitimately grant permission, contact the library, or
request approved copies. The example `net/28280` (Ядкәр) exposes restricted PDF
and ZIP files; requesting its PDF anonymously returns HTML titled “Вход” despite
HTTP 200. `net/28236` exposes a public PDF and a restricted ZIP. The adapter does
not register accounts, authenticate, contact anyone, or submit request forms.

Initial direct-file verification on 2026-10-27 inspected the first two pages of each
collection: 40 book records and 40 manuscript records. Both scans retained the
next request at `offset=40` and have no unresolved discovery errors. The book
sample exposed 27 eligible direct documents and 13 restricted document assets;
the manuscript sample exposed one eligible direct document, with the other 39
records retained as metadata without direct supported documents. Restricted
packages and image-reader evidence remain in the per-record file inventory.
These are partial-scan results, not full-collection availability counts.

The CLI acquired the public `net/28236` PDF (`t88064.pdf`, 17,947,124 bytes) with
one request and no retries. Re-reading the saved file confirmed its recorded
size, MD5 `c3f8ebbe01bf316fa0c256360aa5c77e`, SHA-256
`12d23afb7a2cfb1ee948c2c112d9e0b3bce899834cfded4b68e5b9e3df3097bd`,
and acquisition-observation link. A repeated CLI download on an isolated copy
of that completed sample skipped it with zero requests. The main queues retain
26 pending book documents and one pending manuscript document at that point. No automated
tests were created or run; verification used code inspection and manual CLI runs.

Colour-reader verification on 2026-10-27 used public manuscript `net/27026`
([Хикмәт]): its two retained RGB JPEGs total 2,572,071 bytes at 300 DPI. The CLI
produced a two-page 1,394,253-byte colour PDF, with embedded image resolution at
least 200 DPI on both axes. Poppler rendering confirmed the red annotations and
blue stamp remain coloured. Repeating the download reused the PDF with zero
requests. A byte-capped run saved the first image without publishing a PDF; its
next invocation skipped that image and acquired only the second. A deliberately
small derived-PDF cap rejected publication, and restoring the cap rebuilt from
the originals without network requests. Bounded CLI discovery also resolved all
558 page descriptors for `net/28071` and 111 pages across two ordered readers for
`net/27974`, then preserved the remaining catalog work at its soft deadline.

## Books: direct files, PostgreSQL and S3

The books source reuses the direct-file policy implemented for Азад халык. Custom
YAML should include `sources.kfu_books.direct_files_only: true`; this optional
boolean selects parser version 4 and records policy plus eligible/held file
counts. Native handles, bitstream identities, DC metadata, raw bibliography,
language labels, file descriptions and restriction evidence remain preserved.
The setting does not add a language filter; `tatar_only: false` retains the
collection's existing all-language admission policy.

Direct-only resolution never enumerates page readers. Download bypasses image
assembly; S3 inventory also excludes previously assembled outputs when this
setting is enabled, including before observations refresh. Public direct files
remain eligible when the same record also has restricted packages. No ZIPs are
expanded and no webpage text or HTML is converted to documents. Metadata-only
and held records remain in PostgreSQL without being published as books.

Set `DATABASE_URL` and initialize the schema once with
`.venv/bin/python cli.py database init`. Processing stores observations, frontier
checkpoints, results, errors and S3 receipts in PostgreSQL, without JSON-state
fallback. Local originals remain under the configured artifact root. See
[database operations](../postgres-migration.md).

`download` is local. `run` acquires original documents and publishes finished
files to S3 after committed checkpoints, retaining local files. Standalone
`publish` retries from local files and reports missing originals:

```bash
.venv/bin/python cli.py --summary-only --config config/sources/kfu_books.yaml run --source kfu_books --max-pages 1 --limit 1
.venv/bin/python cli.py --summary-only --config config/sources/kfu_books.yaml publish --source kfu_books --target s3 --limit 1
```

Configure `S3_BUCKET` and standard AWS credentials. Shared publication uses
deterministic object keys, SHA-256 metadata and PostgreSQL receipts. Fresh runners
reacquire missing unpublished originals; receipts allow published files to be
skipped. The **Ingest kfu_books** workflow already supports manual dispatch using
the shared runner and `config/scheduled.yaml` limits. No schedule is added.
Initialize PostgreSQL before dispatch. Required repository secrets:
`DATABASE_URL`, `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. Optional:
`AWS_SESSION_TOKEN`; repository variables `S3_ENDPOINT_URL` and
`AWS_DEFAULT_REGION`. Runner-local files are temporary; PostgreSQL and S3 retain
durable state and published originals. See
[runner operations](../scheduled-ingestion.md).

## Books audit, 2026-11-07 (Europe/Moscow)

Live traversal inspected seven native listing pages and all 136 book records,
then rechecked the advertised total: 144 requests, no retries/errors, verified
count 136 and no remaining frontier. It found 111 eligible direct document files
(110 PDFs, one DOCX) across 110 records. Twenty-six records have no eligible direct
file. Twenty-five supported document assets remain restricted and two public
reader entries are held as `reader_policy_excluded`. The complete inventory also
retains 51 restricted file blocks, including unsupported packages; none was
requested. File and record counts describe exposed candidates, not successful
downloads or verified standalone-book completeness.

All 136 observations retain `direct_files_only` policy, DC tags, bibliography,
file descriptions and collection provenance. Actual reader records `net/28290`
and `net/27345` stayed metadata without reader/manifest requests or image
enumeration. `net/28236` retained its public PDF despite its restricted ZIP;
`net/28280` retained its restricted PDF as held evidence. No access requests,
registration or restricted-file probes were performed.

One bounded original transfer reverified `net/28236`, `t88064.pdf`: 17,947,124
bytes, 52 PDF pages, SHA-256
`12d23afb7a2cfb1ee948c2c112d9e0b3bce899834cfded4b68e5b9e3df3097bd`,
MD5 `c3f8ebbe01bf316fa0c256360aa5c77e`, matching the earlier sample. Native file
identity, declared response length and PDF signature passed. Rendered page 5
shows the historical illustrated alphabet book. These are computed local hashes,
not source-checksum matches; no language-composition or printed-completeness
claim was inferred. The remaining 110 eligible files were not freshly acquired.

Evidence is ignored under `__artifacts/kfu-books-review-20261107/`: seven listing
responses, 136 item responses, final count verification, metadata/catalog/summary
exports and sample PDF/render/hash report. Review exports are not operational
state. The adapter/pipeline implementation is reused unchanged; this source's
YAML now enables the existing direct-file setting. Configuration checks confirmed
books and Азад халык use parser version 4 while manuscripts, Ил and Шура retain
their prior configuration and parser version 3.

Compilation, configured parsing, count/file-policy checks, capability listing,
scheduled profile loading, manual workflow generator equality and
`git diff --check` passed. No automated tests were added. The sample used shared
HTTP/native guards and format validation, not the full database-backed acquisition
stage. Database/storage credentials were unset, so live PostgreSQL checkpoint/
resume, repeat-run skipping and S3 upload receipts remain unverified. No production
state writes, S3 uploads or GitHub workflow dispatch occurred.
