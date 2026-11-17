# Shared configuration and operation

Set `database.url` in the private source YAML and initialize Postgres before ingestion; see
[setup, legacy imports and fresh-runner recovery](../postgres-migration.md).
Processing state and run summaries live in Postgres. Disk holds document
artifacts and explicit exports. Older file-based recovery examples describe
archived snapshots and are not the current source of progress.

Use the repository virtual environment and its existing `requirements.txt`.
Use one complete private file, `config/local/<source>.yaml`, for all source settings,
credentials, database access, S3 access, paths and limits. Source commands create a
missing file from the public template without overwriting existing files. Fill its
null credential fields before running. You can prepare it explicitly with
`cli.py configure --source NAME`. With no stage, the source command runs the pipeline:

```bash
.venv/bin/python cli.py milli_kitaphana
.venv/bin/python cli.py magarif --max-pages 2 --limit 1
.venv/bin/python cli.py magarif status
.venv/bin/python cli.py magarif download --limit 1
.venv/bin/python cli.py magarif --summary-only status
.venv/bin/python cli.py magarif --config config/local/magarif.yaml run --limit 1
```

Each source exposes its supported stages without `--source`. Put stage options
after the stage name; when omitting the stage, put run options after the source
name. Source groups accept `--config`, `--profile` and `--summary-only`; the root
versions of these options also work. An explicit source-level `--config` takes
precedence over the root option. The default configuration path is anchored to the
repository, even when invoking `cli.py` from another working directory. Explicit
paths remain relative to the working directory. Standalone files reject `--profile`,
`extends` and environment references so the selected YAML is the complete configuration.

The original command-first syntax remains supported and requires an explicit
configuration:

```bash
.venv/bin/python cli.py sources
.venv/bin/python cli.py --summary-only --config config/local/magarif.yaml status --source magarif
.venv/bin/python cli.py --summary-only --config config/local/magarif.yaml discover --source magarif --max-pages 2
.venv/bin/python cli.py --summary-only --config config/local/magarif.yaml download --source magarif --limit 1
.venv/bin/python cli.py --summary-only --config config/local/magarif.yaml run --source magarif --max-pages 2 --limit 1
```

`sources`, `inspect` and command help do not need configuration. Command-first acquisition and status commands require
`--config` before the command name; source-first commands infer it as above. Relative artifact paths resolve against the
YAML file's directory. `database.url` supplies the shared state connection.
Miras stores the verified browser export mapping under `sources.<source>.session`
(`format`, `origin`, `user_agent`, `cookies`) in the same YAML. Litres reads SID
from `sources.litres.sid` in that YAML; see [its guide](litres.md). Milli Kitaphana needs its configured cryptographic access values; see [its guide](milli-kitaphana.md). `--session-file` is rejected for other sources. `status` does not read
a session file or make network requests.

Only the selected source needs a `sources.<source>.archive_url` configuration
entry. Existing Magarif-only YAML files remain valid. To enable Tatarica in an
existing file, add the `sources.tatarica` entry from the example; keep your chosen
paths, budgets, and network settings. Enable Darul-Kutub the same way with the
`sources.darul_kutub` entry.

For compact machine-readable output, put the global `--summary-only` option
before the command name:

```bash
.venv/bin/python cli.py --summary-only --config config/local/magarif.yaml discover --source magarif
.venv/bin/python cli.py --summary-only --config config/local/magarif.yaml status --source magarif
.venv/bin/python cli.py --summary-only inspect https://tuganzhir.org/archive/ --max-links 8
```

This suppresses per-record progress and prints one compact JSON object with
common counters, stop reasons, error counts, current queue counts and available
state references. Full structured run summaries live in each source's Postgres
`last_run` entry; processing no longer writes summary files.
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
  files/<sha256>.<extension> # acquired originals; upstream filenames are metadata
  .tmp/run-*/               # temporary bytes owned by individual runs
```

Tatarica uses the same layout under `__artifacts/ingestion/tatarica/`. Its records
use supplied CMS page IDs when available, and file assets use supplied download
IDs. URLs are the fallback when native IDs are absent. URL aliases and renamed
records retain their provenance without creating another native-ID identity.
Magarif's URL identities and artifact naming remain unchanged.
Darul-Kutub uses `__artifacts/ingestion/darul_kutub/`, publication IDs from
`/books/<id>/`, and original URLs for file identity within each publication.

Each source uses an exclusive Postgres advisory writer lock. `status` reads
recorded database state without contacting source websites or creating files. It reports recorded
counts, not a new filesystem/integrity audit. Postgres state is committed atomically
after individual records and completed downloads. Metadata changes append
observations; unchanged consecutive observations are not duplicated. Original
download results retain their captured observation IDs.

`download` processes pending/failed current assets and skips recorded successful
acquisition even if runner-local copies are missing. Restore missing assembly
inputs or explicitly reacquire them; unfinished assembly reports `awaiting_inputs`.
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
download bytes, backlog counts, and the database state key. Ordinary failures
remove only that run's partial bytes. A forcibly terminated process may leave
its own `.tmp/run-*` directory; a later run does not need or automatically delete
it. A published file whose manifest commit was interrupted may be downloaded
again and deduplicated. Postgres is the progress authority.

`download` and `finalize` store outputs locally. `run` also publishes completed
documents to S3; [scheduled workflows](../scheduled-ingestion.md) use the same CLI.

## Per-source configuration

Use `cli.py <source> [stage]`. Its default is the ignored file
`config/local/<source>.yaml`; `--config PATH` can select another complete file.
The CLI creates missing files with owner-only permissions (`0600`) from
`config/sources/<source>.yaml` and `config/defaults.yaml`, flattening those templates
into a single file. Those public templates are not reread during processing.
Existing private files are never overwritten or automatically merged.

Private files have `standalone: true`. Store secrets directly in them. Environment
references, `extends` and `--profile` are rejected in this mode. `database.url`
selects progress storage; `database.pool_size`, `pool_timeout_seconds` and
`connect_timeout_seconds` configure the connection pool. `storage.s3` contains
`bucket`, `region`, `endpoint_url`, `prefix`, `access_key_id`, `secret_access_key`
and optional `session_token`. Neither `DATABASE_URL` nor the AWS credential chain
supplies missing credentials in standalone mode.

Binary values can use YAML `!!binary` or `{base64: ENCODED_VALUE}`. Values are
decoded without printing them. Leave unused destination secrets null for local
stages. Keep credential files out of Git; `config/local/` is already ignored.

If a provider omits an intermediate TLS certificate, `network.additional_ca_certificates`
can contain its public PEM certificate directly in this same YAML. The HTTP client
adds it to the existing CA store and continues verifying certificates and hostnames.
Use a certificate obtained from the issuer; this does not disable TLS verification.

For compatibility, explicitly selected public/scheduled configurations without
`standalone: true` retain `extends`, environment references and AWS/environment
fallbacks. This does not affect the default private source configuration.

Provider helpers read invocation-local `sources.<source>.operational` settings,
grouped by helper module. Configured URLs and allowed origins control native
request checks; changing an origin does not adapt provider-specific URL patterns
or HTML parsers. Parser versions, regexes, format signatures, protocol details and
language-admission rules remain implementation constants. Library defaults remain
implicit where no application override is needed.

CLI page/item limits still restrict configured caps. Source listing and help need
no credentials. Database inspection can select the same source file:

```bash
.venv/bin/python cli.py --config config/local/milli_kitaphana.yaml database init
.venv/bin/python scripts/ingestion_overview.py --database --source milli_kitaphana
```

The overview selects each source's private file; `--config PATH` overrides it for
one `--source`. See [scheduled operations](../scheduled-ingestion.md) for the
legacy Actions configuration.

## S3 publication

All sources support `publish --source NAME --target s3` (S3 is the default target).
`run` checkpoints finished local documents and publishes them automatically.
`download` and `finalize` remain local stages. Existing explicitly selected legacy
publication targets remain available. Local files are retained.

Configure a single destination in the selected operational YAML:

```yaml
storage:
  s3:
    bucket: your-bucket
    endpoint_url: https://your-s3-compatible-endpoint
    region: us-east-1
    prefix: books
    access_key_id: YOUR_ACCESS_KEY
    secret_access_key: YOUR_SECRET_KEY
    session_token: null
```

Endpoint is optional for AWS; set the region explicitly. Credentials are read
from this same YAML, including an optional session token. `database.url` selects
progress storage; provider-specific upstream metadata connections remain under
`sources.<source>.database_url`.

`ingestion/publication.py` projects native source state into
`PublishableArtifact` values. Extend that projection for new output layouts;
reuse the transfer implementation. Completed direct documents, assembled PDFs,
and Markdown with relative media are published; scan inputs, encrypted parts,
ZIP packages, and temporary files are excluded. Objects have deterministic
source/content keys and SHA-256 object metadata. PostgreSQL `s3_publications`
receipts retain destination, provenance and object hashes. Legacy Yandex flags
never count as S3 receipts. Run restores missing unpublished inputs; standalone
publish reports missing files without visiting upstream sites.

Publication runs after committed checkpoints under the source lock; receipts
are committed after uploads. An interrupted upload/checkpoint pair is reconciled
with S3 HEAD on retry. Upload work is capped by the configured item count and
uses bounded SDK retries/timeouts. A scan/download budget stop leaves publication
backlog eligible for the next command. Status reports recorded publication counts
without contacting S3. No public bucket access or metadata sidecar is required.
