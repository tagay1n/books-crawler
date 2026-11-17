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
responses are recorded and skipped by later default downloads; `--recheck` can
explicitly revisit them. Collection records are not downloaded. `finalize` decrypts
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
are honored too, avoiding reacquisition of previously published books. `pending`, `duplicate` and `complete` counts
are available in `publication_counts` (including `--summary-only`).

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
are checked before publication. Simulated destinations covered known duplicates, new files,
partial upload failures, staged publication and interrupted progress checkpoints.
Rollback-only catalog verification confirmed pending Gemini state, metadata
preservation, verified location projection and the MD5 trigger; no fixture rows
remained. These checks do not constitute a live book acquisition/upload or a run
of the downstream GitHub/Gemini workflow. Live public-catalog probing still failed
TLS certificate verification in this environment; verification remains enabled.

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
No automated tests were added. Live provider downloads and remote publication
require separate operational verification.

The bounded live catalog check reached the configured retry limit because the
provider certificate could not be verified in this environment. TLS verification
remains enabled. Live discovery/resume and acquisition remain unverified.
