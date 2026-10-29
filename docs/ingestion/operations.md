# Shared configuration and operation

Use the repository virtual environment and its existing `requirements.txt`.
Copy `ingestion.example.yaml` to `ingestion.yaml`, review its paths and limits,
then select that operational file explicitly:

```bash
.venv/bin/python cli.py sources
.venv/bin/python cli.py --config ingestion.yaml discover --source magarif
.venv/bin/python cli.py --config ingestion.yaml status --source magarif
.venv/bin/python cli.py --config ingestion.yaml download --source magarif --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source magarif
.venv/bin/python cli.py --config ingestion.yaml download --source magarif --recheck
.venv/bin/python cli.py --config ingestion.yaml discover --source tatarica --max-pages 2
.venv/bin/python cli.py --config ingestion.yaml status --source tatarica
.venv/bin/python cli.py --config ingestion.yaml download --source tatarica --limit 1
.venv/bin/python cli.py --config ingestion.yaml discover --source darul_kutub --max-pages 2
.venv/bin/python cli.py --config ingestion.yaml status --source darul_kutub
.venv/bin/python cli.py --config ingestion.yaml download --source darul_kutub --limit 1
.venv/bin/python cli.py --config ingestion.yaml discover --source kazanutlary --max-pages 2
.venv/bin/python cli.py --config ingestion.yaml download --source kazanutlary --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source kazanutlary
.venv/bin/python cli.py --config ingestion.yaml discover --source tatkniga --max-pages 2
.venv/bin/python cli.py --config ingestion.yaml download --source tatkniga --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source tatkniga
.venv/bin/python cli.py --config ingestion.yaml discover --source miras --max-pages 2 --session-file PATH
.venv/bin/python cli.py --config ingestion.yaml download --source miras --limit 2 --session-file PATH
.venv/bin/python cli.py --config ingestion.yaml status --source miras
```

`sources`, `inspect` and command help do not need configuration. Acquisition and status commands require
`--config` before the command name. Relative artifact paths resolve against the
YAML file's directory. Environment variables do not override YAML settings, and
example files are never selected automatically. Miras network commands require
`--session-file` from an ordinary verified browser, shared with `miras_periodicals`;
the other adapters require no credentials. `--session-file` is rejected for other sources. `status` does not read
a session file or make network requests.

Only the selected source needs a `sources.<source>.archive_url` configuration
entry. Existing Magarif-only YAML files remain valid. To enable Tatarica in an
existing file, add the `sources.tatarica` entry from the example; keep your chosen
paths, budgets, and network settings. Enable Darul-Kutub the same way with the
`sources.darul_kutub` entry.

For compact machine-readable output, put the global `--summary-only` option
before the command name:

```bash
.venv/bin/python cli.py --summary-only --config ingestion.yaml discover --source magarif
.venv/bin/python cli.py --summary-only --config ingestion.yaml status --source magarif
.venv/bin/python cli.py --summary-only inspect https://tuganzhir.org/archive/ --max-links 8
```

This suppresses per-record progress and prints one compact JSON object with
common counters, stop reasons, error counts, current queue counts and available
report paths. Full structured run summaries and manifests are unchanged. Read the
referenced summary/report only when a count or failure needs investigation.
Status remains read-only, and has no new report file to reference. `records`
counts processed records for a run and retained records for status; run summaries
also include `backlog_records` to make that distinction explicit.
`error_count` concerns this invocation; `discovery_errors` separately counts
unresolved work in the saved scan.

The same option works for inspection, source listing and the retained Miras probe.
Command execution/configuration errors produce a compact error object in this
mode; CLI syntax errors retain Typer's normal error output. Exit status and
default output remain unchanged. Source listing, help and inspection do not load
unrelated adapters or PDF-rendering dependencies. Selecting an adapter loads and
caches it; `sources` still lists the same ordered names.

`discover` follows source-specific catalog pagination and stores record metadata
plus file descriptors without downloading originals. It checkpoints listing
requests and outstanding record URLs. Each invocation resumes an incomplete scan;
after completion, the next invocation starts a fresh scan. A failed record stays
queued for another invocation while independent records can proceed. Successfully
inspected records are not refetched merely because a bounded run resumes.
Each successful observation and the completed record's frontier update are
published together in one atomic checkpoint. Work interrupted before that
checkpoint remains retryable on resumption.
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
Assembled PDFs have a separate optional `limits.max_derived_pdf_bytes` cap,
defaulting to 512 MiB; individual downloaded originals retain the file-size cap.
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

Discovery errors include their scan ID. A successful retry moves the diagnostic
to `discovery_error_history`; replacing a scan archives its unresolved diagnostics
as `scan_replaced`, which does not imply that the remote problem was fixed.
`status` and the overview report active `discovery_errors` separately from
`historical_discovery_errors`. Legacy untagged errors are historical when they
predate the current scan or their request is no longer pending. Unknown dates
keep a still-pending diagnostic active. These read-only commands do not migrate
or rewrite manifests; discovery preserves prior entries when it next writes.
Run summaries retain errors encountered during that invocation and are not
rewritten when a later run resolves them.

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

This delivery stores originals and supported reader-derived PDFs locally. It does not
upload, import catalog data, classify language, expand archives, or run scheduled jobs.
