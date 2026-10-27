# Local document ingestion

The shared `cli.py` implements five sources:

- `magarif`: <https://magarif-uku.ru/documents>, collecting archive attachments.
- `tatarica`: <https://tatarica.org/tat/razdely/tatarika-kitaphanse>, collecting
  document editions linked from the library catalog's books and journal articles.
- `darul_kutub`: <https://darul-kutub.com/search>, collecting originals for books
  and journal issues across all languages in the public search catalog.
- `kazanutlary`: <https://kazanutlary.ru/j-archive>, collecting scanned issue
  images and assembling complete PDFs locally with PyMuPDF.
- `tatkniga`: <https://tatkniga.ru/catalog/biblioteka/>, collecting directly
  linked files with explicit Tatar or Tatar-containing bilingual language labels.

All sources use the same local downloader and manifest implementation. Each
adapter follows its selected catalog. Existing legacy collectors remain independent.

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
```

`sources` and command help do not need configuration. Other commands require
`--config` before the command name. Relative artifact paths resolve against the
YAML file's directory. Environment variables do not override YAML settings, and
example files are never selected automatically. No credentials are needed for
these adapters.

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
and Crimean Tatar is not treated as Tatar. Missing or unrecognized language labels
remain visible for review. No empty language claim is synthesized.

Only directly linked supported document files on the Tatkniga origin are queued.
HTML readers, page sets, audio, archive expansion, and external-host documents are
deferred or unsupported. Interactive-reader links are retained without following
them. Repeated read links collapse to one descriptor. `status` and run summaries
include optional `unsupported_reasons` counts: `reader_deferred`,
`language_unknown`, `language_excluded`, `external_origin`, and
`format_unsupported`. These counts describe current attachment descriptors;
record metadata also retains each publication's `language_selection`.

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
downloads and assembly. Other sources continue counting individual files. Byte,
file-size, deadline, pacing, and disk-reserve controls still apply. Interrupted
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

## Miras cookie-based access pilot

Miras currently has an HTTP access pilot, not a full discovery/download adapter
listed by `sources`. Add `sources.miras.archive_url` from the example to your
operational YAML and supply a Miras-only session export from your ordinary,
manually verified browser:

```bash
python cli.py --config ingestion.yaml probe --source miras \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
```

The existing session export remains compatible. The command uses its cookies
and actual browser user agent with the shared HTTP downloader. It does not
launch or control a browser. Cookie values are never logged. Session JSON is
sensitive: keep it private and out of Git. The helper's former export filename,
`miras-session.json`, is explicitly ignored by the repository.

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
Normal `discover`, `download`, `run`, and `status` commands remain unavailable
for Miras until the full adapter is implemented.

Live check on 2026-10-27: exported cookies enabled HTTP access to the catalog,
sample record, and its 5,486,334-byte, 64-page PDF without retries. This verifies
that session and sample, not full catalog coverage or future session lifetime.

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
