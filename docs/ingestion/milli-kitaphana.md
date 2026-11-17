# Milli Kitaphana unified pipeline

Use `.venv/bin/python cli.py milli_kitaphana` to run the pipeline with
`config/local/milli_kitaphana.yaml`. Select a stage with, for example,
`.venv/bin/python cli.py milli_kitaphana status` or
`.venv/bin/python cli.py milli_kitaphana download --limit 1`.
Override configuration with `milli_kitaphana --config PATH [COMMAND]`.
The original `.venv/bin/python cli.py --config config/local/milli_kitaphana.yaml COMMAND --source milli_kitaphana` syntax remains supported.
Provider helpers live in `ingestion/milli_kitaphana_*.py`; the old source directory
and standalone entry point have been removed.

Configuration belongs under `sources.milli_kitaphana` in the selected operational
YAML. The source command creates a missing private file from the public template;
`cli.py configure --source milli_kitaphana` also prepares it without running ingestion.
Existing key names (`priv_key`, `sig_prefix`, `aes`, `yandex.disk`, `database_url`)
are retained. Store all values directly in this complete private file, without
`extends` or environment references. Binary `priv_key`, `sig_prefix`, and the three
`aes` values use YAML `!!binary` or `{base64: ENCODED_VALUE}`. Never commit credentials. The optional `limited_database_url` is the read connection for the
`mark-existing-limited` maintenance command; `database_url` remains the upstream
metadata insert connection.

`artifact_dir` overrides this source's artifact directory, relative to the YAML.
Without it, artifacts live under `<artifacts_root>/milli_kitaphana`. This workspace
can use `__artifacts/milli.kitaphana` for existing documents. Progress, worker
selections and recovery journals live in Postgres; no local indexes or backups
are generated. See [Postgres setup and import](../postgres-migration.md) to import
existing progress, including `--processing-dir` for worker/recovery state.
Explicit `import-state --from DIRECTORY` also accepts a legacy index directory;
it preserves newer database entries and leaves original files untouched.

| Previous command | Root replacement |
| --- | --- |
| index | discover --source milli_kitaphana |
| download | download --source milli_kitaphana |
| decrypt | finalize --source milli_kitaphana, then publish --source milli_kitaphana --target yandex |
| split | split --source milli_kitaphana --parts N |
| merge-index PATH | merge-index PATH --source milli_kitaphana |
| recover.py | recover --source milli_kitaphana |
| mark_existing_limited.py | mark-existing-limited --source milli_kitaphana |

`discover` retains the Tatar, Arabic and collection queries and obeys
`--max-pages`. Pages accumulate in memory; one atomic PostgreSQL checkpoint at
the end of discovery saves observations and scan frontiers together, including
partial results on a handled failure, explicit limit or normal interruption.
A hard kill can require repeating discovery since the preceding saved frontier.
`page_indexed` logs indicate in-memory progress; `discovery_checkpointed` confirms
the database save. Bad cards are logged while other cards/pages continue. A page
failure stops that query, leaves it retryable, and allows other queries and the
download stage to proceed. Incomplete discovery never removes old records.
Discovery identifies previously seen source records;
cross-source identity is established only after a complete PDF has been assembled
and its MD5 computed. Existing processed source records are skipped on later runs.

`download` acquires encrypted metadata and all parts of non-limited books. Limited
responses confirmed by the decrypted manifest are recorded (`limited_verified`)
and skipped by later default downloads; `--recheck` can explicitly revisit them.
A parsed-page access label alone does not prevent an acquisition attempt. Collection records are not downloaded. `finalize` decrypts
verified local inputs and assembles complete PDFs atomically without network
access. PDF IDs are not regenerated, making repeated assembly of identical inputs
stable. Failed records remain retryable while independent finalizations continue.

`run` resumes prepared local work before fresh discovery/download. Milli's source
template and this workspace's private configuration disable processing caps:
`max_pages`, `max_items`, `max_download_bytes`, `max_file_bytes`,
`max_derived_pdf_bytes`, `soft_deadline_seconds` and `disk_reserve_bytes` are YAML
`null`. There is no separate discovery deadline. Explicit positive values restore
individual caps; `--limit` and `--max-pages` can still bound a manual invocation.
Other sources retain their configured caps. Network timeouts/retries still apply.
An existing process keeps the settings loaded at startup; restart to apply changes.

After discovery, `run` processes each newly downloaded book through assembly and
publication before downloading the next book. Individual download, assembly or
publication errors remain retryable and do not prevent independent books from
proceeding. Per-book acquisition, assembly and upload-receipt checkpoints remain;
the catalog transaction still waits for both uploads. Standalone `download`
continues to perform acquisition only. Source-lock or database failures can stop
the run because safely saving work then requires restoring shared infrastructure.

Milli stores only its latest processing observation per source record. The first
mutating invocation after this change compacts older snapshots under the source
writer lock; later observations replace previous snapshots. First/last seen fields,
current parsed metadata, completion/restriction/duplicate decisions, unfinished
inputs and upload receipts remain. Catalog upstream metadata is unaffected.
Discovery scan state retains a scalar count and retry frontier instead of an array
of every seen ID. Historical imported arrays are removed at the next discovery
save. Count discrepancies leave the scan incomplete for a fresh attempt; counts
alone do not prove unique coverage of a changing catalog across runs.

The storage audit found about 34 MiB in Milli records and 2.8 MiB in Milli state,
including historical snapshots and repeated scan inventories. Read-only compaction
verification reduced 26,543 observations to 16,604 with identical latest metadata.
The 16 KiB empty asset table remains required by the shared repository interface.
Catalog tables used for publications, identities, contributions and extraction
were preserved. Smaller payloads reduce future growth; PostgreSQL may reuse freed
space without immediately shrinking database files.

Normal commands emit timestamped JSON progress lines to stderr and the final
result to stdout. Logs include a run ID, stages, indexed pages and discovery saves, download
attempts and parts, confirmed restrictions, PDF assembly, MD5 decisions, upload
receipts, catalog registration and error classes/HTTP status codes. A heartbeat
every 30 seconds reports activity during long requests, database operations or
assembly. Request logs omit query parameters, headers and bodies; helper tracebacks
and crypto/session material remain suppressed. Errors include up to five code
locations (filename, line and function), without exception messages or locals.
Logs are console output, not local
processing-state files.

`--summary-only` retains its quiet behavior. Add `--log-progress` to keep live
stderr logs alongside a compact stdout result, including under GitHub Actions:

```bash
.venv/bin/python -u cli.py milli_kitaphana --summary-only --log-progress
```

The shared workflow enables these logs for Milli and skips the capped scheduled
overlay for this source. GitHub's job timeout can still interrupt a run; PostgreSQL
checkpoints let the next runner resume unfinished work. The workflow has not been
deployed or dispatched by this change.

Summary `skipped` and `not_full_skipped` counters count stage visits, so the same
source record can contribute more than once. `started_items` counts download
attempts, including confirmed restricted books and failures. For example, 25
attempts consisting of 21 restricted manifests and four HTTP failures correctly
produce zero downloaded or finalized books; the final result retains failure
records and HTTP status codes for retry/debugging.

Publication computes and verifies the PDF hashes, then checks
`monocorpus.downloaded_documents` before creating any remote object. A known MD5
is marked `duplicate` in the progress publication state; it receives no PDF uploads
or new upstream metadata. A completed source record is not processed again merely
because its local files disappeared. Imported legacy `decrypted` completion flags
are honored too, avoiding reacquisition of previously published books. `pending`, `not_full`, `duplicate` and `complete` counts
are available in `publication_counts` (including `--summary-only`).

For a new MD5, publication requires `downloaded: full` and a `complete: true`
marker attached to the hashed PDF by successful full-part finalization. Known
previews are skipped (`not_full`); old or ambiguous full flags remain pending with
`full_verification_required` and are rebuilt/reacquired by `run` before publication.
Network failures and corrupt/truncated inputs remain retryable errors rather than
being permanently classified as restricted books. An existing catalog MD5 can
still be skipped without uploading it again.

For a new MD5, publication verifies the following destinations:

- Yandex Disk: `<target_dir>/full/<md5>.pdf`, with verified MD5. Milli saves only
  `ya_path` for this destination; it does not publish the file or set
  `ya_resource_id`, `ya_public_url` or `ya_public_key`. Sharing and those fields
  belong to the separate sync script. Existing values are preserved.
- S3: the configured document bucket, key `<md5>.pdf`. This source uses the catalog's
  MD5 naming convention rather than the generic source/SHA-256 prefix layout.

Only after both PDFs are confirmed does a single catalog transaction create the
pending document through `public.document`, record the verified storage locations,
and insert parsed-page JSON into `monocorpus.library_upstream_metadata`. The
catalog's trigger adds the MD5 registry entry in that transaction. Existing catalog
records and extracted metadata are preserved. Prefill leaves Gemini extraction and
evaluation pending; it does not promote page claims into extracted bibliography.

Upstream metadata is stored only in catalog PostgreSQL, never as a ZIP or S3
metadata artifact. Its payload retains title, author, raw page properties, year,
language, tags, description, classification and source links. Acquisition keys,
local file paths, progress flags and cover images are excluded. The downstream
Gemini consumer must read this JSON table; the legacy ZIP-only reader in older
`monocorpus` code is not modified by this change.

Progress and per-destination receipts use `database.url`; the document catalog,
registry and upstream JSON use `sources.milli_kitaphana.database_url`. Uploads and
the independent progress database cannot share the catalog transaction. Upload
receipts are checkpointed as pending work. If catalog commit succeeds but progress
saving fails, the next run reconciles the catalog locations and metadata, including
when runner-local PDFs disappeared. Re-uploading after a lost receipt uses the
same MD5 filename and safely reconciles/replaces the same object.

`publish --target s3` and `publish --target yandex` can stage individual destination
uploads through the same MD5 gate. Catalog registration and processed status wait
until both destination receipts exist. `run` performs both automatically.

Manual verification used temporary encrypted two-part PDFs: two pages assembled,
unchanged finalization skipped, reassembly produced identical bytes, and no provider
requests occurred. Part ordering, password authentication and declared page counts
are checked before publication. Empty part lists are rejected and every advertised
part must transfer successfully before acquisition is marked full. Simulated destinations covered known duplicates, new files,
partial upload failures, staged publication and interrupted progress checkpoints.
Rollback-only catalog verification confirmed pending Gemini state, metadata
preservation, verified location projection and the MD5 trigger; no fixture rows
remained. These controlled checks did not run the downstream GitHub/Gemini workflow.
Later live verification below covers actual acquisition and Yandex publication.

A read-only upstream schema inspection confirmed
`monocorpus.library_upstream_metadata` has required `md5 text` and
`payload_json jsonb` columns, insert permission, no user triggers or row security,
and checks requiring a lowercase 32-character hexadecimal MD5 and a JSON object.
The primary key is `md5`; publication preserves existing payloads using conflict-ignore insertion.
Insert planning succeeded over TLS without executing a write. No ingestion
progress tables were present in that inspected database; configure progress
storage separately via `database.url` and initialize it explicitly.

The separate progress database was subsequently verified over TLS in a read-only
transaction: schema version 1, `ingestion.bookkeeping`, and all three
`ingestion.milli_kitaphana_{records,assets,state}` tables were present. Each has
required `key text` and `payload jsonb` columns with a primary key on `key`.
Read/insert/update/delete and advisory-lock permissions were available; repository
upsert/delete planning succeeded without execution. No user triggers or row
security were enabled on those tables. No database changes were made by the check.

`split` stores named worker selections in Postgres. `--dest` explicitly exports
JSON in addition; filters belong under `sources.milli_kitaphana.split_filter`.
`recover` retains `--report`, `--workers`, `--download`, `--retry-failed` and
`--download-workers`; its default journal is the Postgres entry `default`; `--report` selects a name. Recovery
keeps its combined download/local assembly behavior and never publishes.
Source writers share a lock. Network operations use shared time/byte/retry limits;
provider transfers are serialized for consistent accounting. Recovery candidates
are capped by the configured item limit. `status` is read-only and needs no keys.
Use global `--summary-only` for compact results; detailed errors remain in the
source's `last_run` entry in Postgres.

Manual verification used isolated `/tmp/milli-cli-check` artifacts: repeated
import, split, local encrypted PDF assembly with zero requests, and a second
finalization that skipped the verified output. Placeholder publishing credentials
were rejected. Original local settings were compared without printing values.
No automated tests were added. Later live operational verification is recorded below.

The November 2026 live run found that the provider omitted the GlobalSign GCC R46
AlphaSSL CA 2025 intermediate from its TLS chain. Supplying that public intermediate
as `network.additional_ca_certificates` in the private source YAML restored verified
HTTPS. Discovery then resumed and checkpointed new records in PostgreSQL. Keep
`artifact_dir` pointed at existing Milli artifacts when reusing local encrypted
inputs; the runtime creates a missing artifact directory for a fresh installation.

Live verification on 2026-11-17 increased source records from 16,579 to 16,604.
Restricted manifests were checkpointed and skipped. Three selected 1918 *Чаян*
issues exposed a download-worker context propagation bug; using the shared
`ConfiguredThreadPoolExecutor` fixed it. All advertised encrypted parts then
downloaded (52,578,777 transfer bytes), and offline assembly produced complete
14-, 16- and 16-page PDFs. Repeating the selected download made zero requests.

Primary storage is Backblaze B2: bucket `ttdocs`, region `eu-central-003`, endpoint
`https://s3.eu-central-003.backblazeb2.com`. Working credentials and this destination
were saved only in the ignored private source YAML. Yandex Disk remains the second
PDF destination.

All three PDFs were uploaded to Yandex Disk under their canonical MD5 names;
independent remote metadata checks matched MD5, size, resource ID and public
sharing. Repeating Yandex publication uploaded nothing. Publication remained
`pending`, without catalog or registry inserts, until Backblaze was configured.
Resuming S3 publication then uploaded all three PDFs and registered all three
documents and upstream JSON payloads with zero errors. Documents and MD5 registry
counts both increased from 71,755 to 71,758, and upstream metadata rows increased
from 7,885 to 7,888. Independent Backblaze GETs reproduced each PDF's MD5; HEAD
metadata and sizes matched too. The catalog MD5 trigger was enabled and all three
new hashes were present in its registry. Extraction/evaluation methods remain
unset and catalog inclusion remains pending.

PostgreSQL processing state now marks these three source records complete and
retains both destination receipts. Repeating S3 publication uploaded nothing and
registered no additional documents. The selected worker selection also lives in
PostgreSQL (`selection:live-verification-1`); no local processing-state file was used.
The remaining catalog scan and acquisition backlog can be continued with the normal
source command; this was a bounded operational verification, not a complete crawl.
That historical run published Yandex files and stored sharing/resource metadata.
The current uploader leaves publishing to the other script and stores only the
Yandex path; recovery matches that path and the S3 URL rather than a resource ID
that can change when the separate script replaces a file.

Database round trips are reduced without removing recovery boundaries. An
unchanged repository save returns before opening a connection or checking the
source lease; checkpoint callbacks still run. Changed saves perform one mandatory
ownership check after obtaining the transaction connection. Supplied-connection
saves retain their own ownership check. Periodic lease checks during active work
remain enabled.

Publication determines registry membership and matching-location/metadata recovery
in one catalog query. A cached hash checked before file hashing is not queried
again in the same attempt when the verified hash agrees. Known duplicates and
recovered publications save their terminal state once; new files still checkpoint
pending hashes before uploads. The final catalog transaction independently
rechecks MD5 membership to handle concurrent writers.

Manual SQL instrumentation using session-local temporary tables confirmed zero
SQL statements for unchanged/repeated saves and one ownership query plus one
upsert for a changed row. A deliberately rejected write rolled back without
advancing the baseline; temporary tables were removed. Read-only queries against
the three published books confirmed recovered and duplicate classifications, and
an unseen hash was classified new. The existing parser process was left running
with its loaded code; these improvements apply on its next start.
