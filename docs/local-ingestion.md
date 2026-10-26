# Local document ingestion

The shared `cli.py` currently implements the `magarif` source:
<https://magarif-uku.ru/documents>. It collects document attachments from archive
records, including journal issues and educational material. It does not crawl the
whole site. Existing source collectors remain independent.

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
```

`sources` and command help do not need configuration. Other commands require
`--config` before the command name. Relative artifact paths resolve against the
YAML file's directory. Environment variables do not override YAML settings, and
example files are never selected automatically. No credentials are needed for
this adapter.

`discover` follows archive pagination links and stores record metadata plus file
descriptors without downloading originals. It rescans from the archive root on
each invocation, deduplicating page and record URLs. Records without attachments
remain visible. A partial or failed scan never marks unvisited records absent.
If an attachment disappears from a successfully inspected record, its history
remains retained and it leaves the current download queue.

The parser uses record content and its attachment list. Shared banners and footer
documents are excluded. Supported originals include PDF, DjVu, EPUB, text/HTML,
RTF, and common office formats. Package/media attachments and links outside the
source origin remain listed as `unsupported`. Metadata and archive context are
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
Renames or changes to an attachment URL produce separate asset identities.

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

Every mutating command prints progress and a structured summary including errors,
budget stops, request/retry counts, downloaded/skipped/reused files, attempted
download bytes, backlog counts, and the summary file path. Ordinary failures
remove only that run's partial bytes. A forcibly terminated process may leave
its own `.tmp/run-*` directory; a later run does not need or automatically delete
it. A published file whose manifest commit was interrupted may be downloaded
again and deduplicated. The local manifest is the progress authority.

This delivery stores originals locally. It does not upload, import catalog data,
classify language, assemble page sets, expand archives, or run scheduled jobs.
