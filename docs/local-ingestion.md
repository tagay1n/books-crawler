# Local document ingestion

The shared `cli.py` implements eight acquisition sources and one discovery-only source:

- `magarif`: <https://magarif-uku.ru/documents>, collecting archive attachments.
- `tatarica`: <https://tatarica.org/tat/razdely/tatarika-kitaphanse>, collecting
  document editions linked from the library catalog's books and journal articles.
- `darul_kutub`: <https://darul-kutub.com/search>, collecting originals for books
  and journal issues across all languages in the public search catalog.
- `kazanutlary`: <https://kazanutlary.ru/j-archive>, collecting scanned issue
  images and assembling complete PDFs locally with PyMuPDF.
- `tatkniga`: <https://tatkniga.ru/catalog/biblioteka/>, collecting directly
  linked files with explicit Tatar or Tatar-containing bilingual language labels,
  plus supported public flipbook pages assembled into local PDFs.
- `miras`: <https://miras.info/projects/mirasxane/books/>, collecting exposed
  original book PDFs across all languages using an exported browser session.
- `commons`: <https://commons.wikimedia.org/wiki/Category:Tatar-language_books>,
  discovering document-format book candidates through the public metadata API.
  Only `discover` and `status` are supported for this source.
- `isxaki`: <https://isxaki.com/ijat/>, collecting linked document files from
  original editions, three works periods, and books about Iskhaki.
- `internet_archive`: <https://archive.org>, collecting public original document
  uploads from text items explicitly labelled as Tatar.

All sources use the same local downloader and manifest implementation. Each
adapter follows its selected catalog. Existing legacy collectors remain independent.

### Isxaki books and works

Add `sources.isxaki.archive_url: https://isxaki.com/ijat/` to the operational YAML,
or copy the entry from the example configuration. No credentials are required.

```bash
python cli.py --config ingestion.yaml discover --source isxaki
python cli.py --config ingestion.yaml download --source isxaki --limit 1
python cli.py --config ingestion.yaml run --source isxaki --limit 1
python cli.py --config ingestion.yaml status --source isxaki
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

Both historical editions and supplied modern text PDFs are eligible. Files are
saved unchanged under `__artifacts/ingestion/isxaki/files/` with the shared local
manifest, SHA-256/MD5, integrity checks, budgets, and recheck behavior. HTML-only
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

### Internet Archive originals

Configure `sources.internet_archive.archive_url: https://archive.org` in the
operational YAML. No login, borrowing credentials, or new dependencies are needed.

```bash
python cli.py --config ingestion.yaml discover --source internet_archive --max-pages 2
python cli.py --config ingestion.yaml download --source internet_archive --limit 1
python cli.py --config ingestion.yaml run --source internet_archive --max-pages 2 --limit 1
python cli.py --config ingestion.yaml status --source internet_archive
python cli.py --config ingestion.yaml download --source internet_archive --recheck --limit 1
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

### Shared configuration and operation

Use the repository virtual environment and its existing `requirements.txt`.
Copy `ingestion.example.yaml` to `ingestion.yaml`, review its paths and limits,
then select that operational file explicitly:

```bash
python cli.py sources
python cli.py --config ingestion.yaml discover --source magarif
python cli.py --config ingestion.yaml status --source magarif
python cli.py --config ingestion.yaml download --source magarif --limit 1
python cli.py --config ingestion.yaml run --source magarif
python cli.py --config ingestion.yaml download --source magarif --recheck
python cli.py --config ingestion.yaml discover --source tatarica --max-pages 2
python cli.py --config ingestion.yaml status --source tatarica
python cli.py --config ingestion.yaml download --source tatarica --limit 1
python cli.py --config ingestion.yaml discover --source darul_kutub --max-pages 2
python cli.py --config ingestion.yaml status --source darul_kutub
python cli.py --config ingestion.yaml download --source darul_kutub --limit 1
python cli.py --config ingestion.yaml discover --source kazanutlary --max-pages 2
python cli.py --config ingestion.yaml download --source kazanutlary --limit 1
python cli.py --config ingestion.yaml status --source kazanutlary
python cli.py --config ingestion.yaml discover --source tatkniga --max-pages 2
python cli.py --config ingestion.yaml download --source tatkniga --limit 1
python cli.py --config ingestion.yaml status --source tatkniga
python cli.py --config ingestion.yaml discover --source miras --max-pages 2 --session-file PATH
python cli.py --config ingestion.yaml download --source miras --limit 2 --session-file PATH
python cli.py --config ingestion.yaml status --source miras
```

`sources` and command help do not need configuration. Other commands require
`--config` before the command name. Relative artifact paths resolve against the
YAML file's directory. Environment variables do not override YAML settings, and
example files are never selected automatically. Miras network commands require
`--session-file` from an ordinary verified browser; the other adapters require no
credentials. `--session-file` is rejected for other sources. `status` does not read
a session file or make network requests.

Only the selected source needs a `sources.<source>.archive_url` configuration
entry. Existing Magarif-only YAML files remain valid. To enable Tatarica in an
existing file, add the `sources.tatarica` entry from the example; keep your chosen
paths, budgets, and network settings. Enable Darul-Kutub the same way with the
`sources.darul_kutub` entry.

`discover` follows source-specific catalog pagination and stores record metadata
plus file descriptors without downloading originals. It checkpoints listing
requests and outstanding record URLs. Each invocation resumes an incomplete scan;
after completion, the next invocation starts a fresh scan. A failed record stays
queued for another invocation while independent records can proceed. Successfully
inspected records are not refetched merely because a bounded run resumes.
Records without attachments remain visible. A partial or failed scan never marks
unvisited records absent.
If an attachment disappears from a successfully inspected record, its history
remains retained and it leaves the current download queue.

The parser uses record content and its attachment list. Shared banners and footer
documents are excluded. Supported originals include PDF, DjVu, EPUB, text/HTML,
RTF, and common office formats. Recognized document links outside the source
origin remain listed as `unsupported`; Magarif also retains unsupported entries
from its explicit attachment list. Metadata and archive context are
source claims; downloading does not confirm language, quality, or completeness.

Tatarica's initial page shows only a small catalog window. Its adapter follows
the same read-only form POST pagination as the site's “Тагын” control, using the
current chapter ID and advertised count from the page rather than hardcoded
values. Both observed library URL variants are supported. It extracts document
links only from record content, including extensionless
`/download_file/view/<id>` routes. The shared downloader resolves those routes
to the actual files and determines their document extension.

All linked Tatarica editions are eligible, including Russian and bilingual
editions. No language filter or placeholder language field is added. The adapter
retains bibliographic paragraphs, edition labels, and surrounding source text;
it does not turn them into inferred authors, publication dates, or language facts.
HTML-only records retain their available metadata without generating an HTML or
text artifact. Unrelated encyclopedia navigation and recommendations are excluded.

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

Tatkniga traverses only the current public library, using native `PAGEN_1`
pagination and its advertised last page. It excludes shop menus, recommendations,
filters, and “show all” links. A changed page count restarts the next scan while
retaining committed records. Empty/incomplete pages, repeated batches, invalid
pagination, and failed record inspections keep discovery incomplete. No exact
site-wide record count is advertised; completion describes the linked listing
traversal, not every potentially available historical file or a fixed catalog
snapshot. The catalog's required trailing slash is preserved.

Publication IDs come from the current primary product wrapper. File-path IDs are
separate references. Metadata retains supplied titles, authors, descriptions,
bibliographic property names/values, and language labels. An explicit recognized
Tatar language label (including `тат`) selects an edition; bilingual labels must
explicitly include Tatar. Titles and descriptions are not used to infer language,
and Crimean Tatar is not treated as Tatar. Missing language labels hold direct
files for review; public FlipHTML5 readers may be acquired without a language
label. Unrecognized labels remain held for review for both acquisition methods.
No empty or inferred language claim is synthesized. Reader eligibility is recorded
separately as `reader_language_selection`; the original `language_selection` stays
unchanged.

Directly linked supported documents and recognized FlipHTML5 readers under
`/upload/interactive_books/` on the Tatkniga origin are eligible. Discovery follows
the reader's linked `javascript/config.js`, parses its explicit `fliphtml5_pages`
JSON list without executing JavaScript, and verifies the count against
`totalPageCount`. Recognized PageSpeed script/bundle URLs are resolved to the
original configuration source they name. Display captions and bibliographic page
counts do not define the image sequence. Listed large JPEGs are preferred, with
listed normal JPEGs used when a large image is not declared. Thumbnails and guessed
URLs are not used.
Reader/configuration URLs and raw configuration remain in metadata.

Repeated links collapse to one reader. Multiple distinct supported reader links
require review. An eligible direct PDF takes precedence over reader assembly.
Other readers, audio, archive expansion, and external-host documents remain
deferred or unsupported. `status` and run summaries include optional
`unsupported_reasons` counts: `reader_deferred`, `reader_unsupported`,
`reader_ambiguous`, `reader_superseded`, `language_unknown`, `language_excluded`,
`external_origin`, and `format_unsupported`. Failed reader/configuration requests
or inconsistent declared page lists leave discovery incomplete and retryable.

For Tatkniga, `--limit` and `max_items` count either a direct file or a whole reader
book. Direct files are processed first, with the remaining item budget shared by
reader books. Verified JPEGs are retained in `files/` and assembled in reader
order, including covers and blank pages. Assembled PDFs are published atomically
to `__artifacts/ingestion/tatkniga/derived/<sha256>.pdf` only after all expected
pages are available and the PDF page count is verified. These are image PDFs
without OCR; interactive media and exercises are not included. Image quality,
proportions, and orientation are preserved.

Interrupted books resume from verified images. Missing, damaged, or outdated PDFs
are rebuilt; unchanged complete books require no network requests. `--recheck`
revalidates images and retains old PDF versions when inputs change. A failed
recheck leaves the book incomplete while preserving historical files. PDF results
record ordered input IDs and hashes, assembler version, source observation, size,
and page count. Status adds `pdf_books` completion counts and `image_pages`
progress; it reads the manifest rather than auditing local file integrity.
Parser version 2 restarts discovery to refresh old reader descriptors while
preserving observations and downloads; run `discover` after upgrading.

Tatkniga uses `__artifacts/ingestion/tatkniga/` with the shared manifest and
downloader. The old Selenium scripts have been retired; `tatkniga/workdir/`,
`paid_files.csv`, and the old configuration are preserved as historical data.
They are not read or migrated by the new adapter, and old download markers are
not evidence that verified local bytes exist. No cloud services or credentials
are used. See [the historical-data notes](../tatkniga/README.md).

Kazan Utları follows every linked year listing across Казан утлары, Яңалиф,
Совет әдәбияты, Атака, and Безнең юл. Native year URLs are preserved even when
their slugs differ from their visible labels. Duplicate navigation links are
collapsed. Issue article-index pages and unrelated footer PDFs are excluded.
Issue metadata retains headings, descriptions when supplied, journal/year listing
context, and the literal reader configuration. Listing context is checkpointed
and appended as source evidence when an issue appears in another listing.

The reader's `count` is interpreted as the total image count: indices `000`
through `count - 1`, including the first reader image. Four inspected issues exposed this many
images while their reader's inclusive loop requested an additional nonexistent
image. This indexing discrepancy is preserved in metadata. Unrecognized reader
structures fail discovery instead of producing guessed image sequences. Catalog
completion means traversal of linked listings; no site-wide total is advertised.

For `kazanutlary`, `--limit` and `max_items` count **issues**, including their image
downloads and assembly. Tatkniga uses the mixed file/book units described above;
remaining sources count individual files. Byte, file-size, deadline, pacing,
and disk-reserve controls still apply. Interrupted
issues resume from verified image files on the next invocation. A failed page
does not discard the other pages, and an issue remains incomplete until every
expected page is available. No partial PDF is published.

JPEGs are retained as upstream originals in `files/`. PyMuPDF embeds them in
numeric order, preserving image quality, proportions, and orientation. Generated
PDFs live in `__artifacts/ingestion/kazanutlary/derived/<sha256>.pdf`; they are
derived artifacts, not upstream PDFs. The manifest records PDF hashes, size,
page count, assembler version, source observation, input fingerprint, and ordered
image asset/result IDs and hashes. Assembly enforces the configured file-size cap
and publishes atomically after reopening and checking the page count. There is
no OCR or text extraction.

`download` verifies local images and PDFs, reuses unchanged complete issues, and
rebuilds missing, damaged, or outdated PDFs. `--recheck` revalidates image URLs;
changed inputs create another retained PDF result. Failed rechecks leave the
issue unresolved while preserving historical files. Status includes recorded
image progress and complete/incomplete/failed PDF issue counts; it remains a
read-only manifest view rather than an integrity audit.

With the example configuration, artifacts live under:

```text
__artifacts/ingestion/magarif/
  manifest.json             # schema_version: 1; records, observations, assets, results
  files/<sha256>.<extension> # acquired originals; upstream filenames are metadata
  summaries/<run-id>.json   # structured command summaries
  .tmp/run-*/               # temporary bytes owned by individual runs
  .lock                     # operating-system lock; released when the process exits
```

Tatarica uses the same layout under `__artifacts/ingestion/tatarica/`. Its records
use supplied CMS page IDs when available, and file assets use supplied download
IDs. URLs are the fallback when native IDs are absent. URL aliases and renamed
records retain their provenance without creating another native-ID identity.
Magarif's existing URL identities and saved files require no migration.
Darul-Kutub uses `__artifacts/ingestion/darul_kutub/`, publication IDs from
`/books/<id>/`, and original URLs for file identity within each publication.

Each source uses an exclusive writer lock. `status` only reads the manifest and
does not issue network requests or create artifact files. It reports recorded
counts, not a new filesystem/integrity audit. The manifest is saved atomically
after individual records and completed downloads. Metadata changes append
observations; unchanged consecutive observations are not duplicated. Original
download results retain their captured observation IDs.

<a id="miras-cookie-based-access-pilot"></a>

## Wikimedia Commons discovery only

Add `sources.commons` from the example to the selected operational YAML:

```bash
python cli.py --config ingestion.yaml discover --source commons --max-pages 2
python cli.py --config ingestion.yaml status --source commons
```

The seed is native category ID `70354556` (Tatar-language books). Discovery follows
its subcategories by native ID and API continuation tokens, with ten members per
batch. `--max-pages` counts category-member API batches; file-metadata lookups use
the same pacing, retry, deadline, and 2 MiB inspection limits as other adapters.
Shared categories and files are deduplicated; category cycles do not recurse.
Valid empty batches may advance, while missing categories, API errors, repeated
batches, and invalid cursors leave work incomplete. Expired/cyclic cursors restart
the next scan without discarding prior observations.

Only the existing document formats, excluding HTML/HTM, become candidates. Image
filenames are filtered before file-metadata lookups, and their IDs, titles, and
metadata are not retained as records or descriptors. Returned MIME must agree
with the document format. Category membership is admission evidence, not verified
language or book completeness. No original documents or previews are requested.

File-page IDs supply stable record identities (`file:<id>`), and each record has
one current-original representation. Retained metadata includes the native title,
reported MIME, size, page count, upload timestamp, source SHA-1, description URLs,
and multilingual extended metadata with credits and licensing claims. Unknown
metadata fields remain intact. Source page counts and hashes are upstream claims,
not locally verified results. Tracking parameters are removed from file locators;
continuation tokens remain in checkpoints rather than metadata observations.

Missing or unavailable originals remain metadata-only records. Partial scans do
not establish disappearance. Unchanged scans update last-seen time without new
observations; changed metadata or upload versions retain their history. Files
reached through multiple categories share one record, with API-reported category
membership and the seed scope retained as evidence.

State and summaries live under `__artifacts/ingestion/commons/`. `download` and
`run` are rejected before requests or writes. A source-specific request guard
restricts traffic to the read-only Commons metadata endpoint, including redirects.
Requests identify the crawler with its repository contact URL; no session export
is needed. No database or storage migration is involved.

## Miras books and browser-session access

Miras is a full shared-CLI adapter for the unfiltered **books** catalog. All
languages are eligible, including editions with missing or unrecognized language
labels. Manuscripts, periodicals, other project categories, alphabetical filters,
and search forms are not traversed. Add `sources.miras.archive_url` from the
example to your operational YAML. Both trailing-slash variants are accepted.

Supply a Miras-only session export from your ordinary, manually verified browser
to each network command:

```bash
python cli.py --config ingestion.yaml discover --source miras --max-pages 2 \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
python cli.py --config ingestion.yaml download --source miras --limit 2 \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
python cli.py --config ingestion.yaml run --source miras --max-pages 2 --limit 2 \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
python cli.py --config ingestion.yaml status --source miras

# Retained diagnostic: inspect the catalog and download one fixed sample.
python cli.py --config ingestion.yaml probe --source miras \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
```

Discovery follows native `/books/page/N/` links in sequence. The numbered links
are a moving window, so their highest visible number is not a catalog total or
last-page guarantee. The adapter follows the linked next page until forward
pagination ends. Missing pagination, empty/incomplete pages, wrong active pages,
and repeated batches leave discovery incomplete. Completion describes the linked
catalog traversal; no exact site-wide count is advertised.

Books use their native numeric record ID (`book:<id>`), preserving renamed URL
relationships. Thumbnail/title links collapse to one entry. Supplied titles in
both scripts, authors, bibliography, page descriptions, publication year, and
other recognized properties are preserved. Listing-only language, publication
place, and subject information remains in `catalog_context`. The website's
general document title is not used as the book title; the catalog label supplies
a title when the detail page has no recognizable heading. No language is inferred.

PDFs are extracted from the primary book content's direct links and reader
`viewer.html?file=...` references. Repeated URLs collapse to one descriptor; all
distinct exposed PDF parts are eligible. External documents and unsupported
formats remain visible with reasons, and metadata-only records are retained.
The shared downloader verifies file signatures, lengths, hashes, budgets, and
atomic publication; PyMuPDF verifies a nonempty readable PDF and records the actual
PDF page count. A bibliographic page count is a source claim and need not equal
the PDF page count. Original files are preserved without conversion or OCR.

Full ingestion uses `__artifacts/ingestion/miras/manifest.json`, `files/`, and
`summaries/`. The existing `pilot/` directory is preserved separately and is not
automatically imported. `--limit` counts individual PDFs, including separate parts
of a book. Incomplete scans and transfers resume using the same shared checkpoints
and verified-local-file behavior as the other adapters.

The existing session export format remains compatible. Commands use its cookies
and actual browser user agent with the shared HTTP downloader, without launching
or controlling a browser. Cookie values and the exported user agent are not
written to manifests, summaries, or logs. Session JSON is sensitive: keep it
private and out of Git. `miras-session.json` is explicitly ignored by the repository.

Recognized access rejections (including HTTP 468) and challenge HTML stop a full
ingestion run promptly with an `access` error and a nonzero CLI exit status. The
remaining queue and previous successful downloads are retained. Ordinary missing
records or invalid PDFs remain individually retryable. A challenge or HTML page
cannot be published as a successful PDF.

When access expires, verify Miras again in your normal browser and refresh the
export. A cookie-export tool can supply browser cookie fields; wrap the
Miras-only cookies and current browser user agent in this format:

```json
{
  "format": "miras-session-v1",
  "origin": "https://miras.info",
  "user_agent": "YOUR_ACTUAL_BROWSER_USER_AGENT",
  "cookies": [
    {
      "domain": "miras.info",
      "name": "EXPORTED_COOKIE_NAME",
      "value": "EXPORTED_COOKIE_VALUE",
      "path": "/",
      "secure": true
    }
  ]
}
```

Preserve cookie domains and paths exactly. `expirationDate` is optional and uses
Unix seconds; expired cookies are skipped. Domains outside `miras.info` and
`.miras.info` are rejected. Do not include cookies from other websites.

The pilot reads one catalog page and the sample «Авыл кызы» record, extracts the
current PDF URL from its reader, and acquires one PDF. Shared pacing, retries,
timeouts, byte/file-size limits, disk reserve, hashes, format checks, and atomic
publication apply. PyMuPDF also verifies that the PDF opens. Files, a manifest,
and diagnostic reports remain under `__artifacts/ingestion/miras/pilot/`.
Successful sample history is retained if a later access attempt fails.
Earlier pilot check on 2026-10-27: exported cookies enabled HTTP access to the catalog,
sample record, and its 5,486,334-byte, 64-page PDF without retries. This verifies
that session and sample, not full catalog coverage or future session lifetime.
The later full-adapter access check rejected the saved session and stopped after
one request with its initial catalog checkpoint retained. A successful two-page,
two-language live check requires renewed browser verification and a refreshed
session export.

### Remembered fallback: ordinary-browser extension

If cookie-based HTTP access becomes insufficient, reconsider a small extension
that reads Miras pages and downloads PDFs inside a normal verified browser,
without a debugging connection. The experiment on 2026-10-27 downloaded a PDF
with the same SHA-256 as the HTTP copy. Its implementation and sample-import CLI
have been removed; this is a fallback idea only. The earlier Playwright approach
was rejected by SafeLine WAF with “Debugging Detected” and has also been removed.

`download` processes pending/failed current assets, verifies existing local bytes
before skipping successes, and reacquires missing or damaged local copies.
`--recheck` additionally checks completed assets with ETag/Last-Modified
conditions when available, or downloads again when no validator exists. Use it
explicitly to detect replacements at an unchanged URL. New bytes get a new
content-addressed file and retained result; old versions remain on disk. Exact
byte duplicates share a file while retaining their source relationships.
Changes to an attachment URL produce separate identities for URL-identified
assets. A Tatarica download-route alias with the same supplied file ID retains
its asset identity.

Transfers stream to a temporary file, compute SHA-256/MD5 and actual size, check
applicable response lengths and basic format signatures, and publish the file
before committing success. HTML error/login responses in place of documents,
empty bodies, and known size mismatches do not become successful downloads.
These checks do not perform structural document validation or OCR.

The local-pilot example caps discovery at 25 pages, acquisition at 25 started
items, attempted download body bytes at 1 GiB, and individual files at 100 MiB.
It reserves 512 MiB of disk and uses a 15-minute soft deadline. Requests are
sequential, paced one second apart, and use 10-second connection/60-second read
timeouts with at most three attempts for retryable transport/server failures.
An in-flight read may take up to its configured timeout before a soft deadline
can be observed. Retry bytes count against the same acquisition cap; discovery
HTML requests are counted separately and limited to 2 MiB per response.

`--limit` on `download`/`run` and `--max-pages` on `discover`/`run` can lower YAML
caps; edit YAML explicitly to raise them. Reaching a budget boundary leaves
remaining work eligible and returns zero when no run errors occurred. Unknown
length transfers that exhaust the byte budget before EOF remain unresolved.
An item failure is saved and independent items can continue; authentication or
availability errors are reported, and disk/storage failures stop acquisition.
Failed downloads are retried on the next download command; unsupported backlog
is reported separately. Commands return nonzero for newly encountered failures.

Discovery summaries and `status` include coverage: catalog entries enumerated,
unique URLs and native records inspected, remaining listing/record work, and
the provider's advertised count when available. Listing requests, including a final count check,
consume the page cap; record-detail requests are bounded by the shared deadline
and network controls. A page cap or deadline keeps discovery incomplete and
preserves the pending frontier for the next invocation.

Tatarica and Darul-Kutub advertise substantially more catalog entries than the default
page cap can enumerate in one run. Repeat `discover` to continue. The count is
catalog entries, not available PDFs or confirmed Tatar documents. Empty or short
responses before the expected end, repeated batches, missing structure, and
failed records prevent completion. A final root-page check compares the current
advertised count with enumeration; a mismatch reports an error and makes the
next invocation start a fresh scan, retaining committed records and files.
Completion means the selected catalog traversal finished, not that every file
anywhere on the provider's website has been found. Count verification also does
not establish a transactional snapshot of a changing remote catalog.

Every mutating command prints progress and a structured summary including errors,
budget stops, request/retry counts, downloaded/skipped/reused files, attempted
download bytes, backlog counts, and the summary file path. Ordinary failures
remove only that run's partial bytes. A forcibly terminated process may leave
its own `.tmp/run-*` directory; a later run does not need or automatically delete
it. A published file whose manifest commit was interrupted may be downloaded
again and deduplicated. The local manifest is the progress authority.

This delivery stores originals and Kazan Utları derived PDFs locally. It does not
upload, import catalog data, classify language, expand archives, or run scheduled jobs.
