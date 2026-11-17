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

`discover` retains the Tatar, Arabic and collection queries, checkpoints pages,
and obeys `--max-pages`. Discovery identifies previously seen source records;
cross-source identity is established only after a complete PDF has been assembled
and its MD5 computed. Existing processed source records are skipped on later runs.

`download` acquires encrypted metadata and all parts of non-limited books. Limited
responses confirmed by the decrypted manifest are recorded (`limited_verified`)
and skipped by later default downloads; `--recheck` can explicitly revisit them.
A parsed-page access label alone does not prevent an acquisition attempt. Collection records are not downloaded. `finalize` decrypts
verified local inputs and assembles complete PDFs atomically without network
access. PDF IDs are not regenerated, making repeated assembly of identical inputs
stable. Failed records remain retryable while independent finalizations continue.

`run` resumes prepared local work before fresh discovery/download. Page, download,
finalization and publication limits bound each invocation. Repeat it to advance
unfinished work; reaching a budget limit does not imply catalog completion.

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

- Yandex Disk: `<target_dir>/full/<md5>.pdf`, with verified MD5, resource ID and
  public sharing information, matching the existing sync workflow's identity.
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
