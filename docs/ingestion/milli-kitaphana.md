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
and obeys `--max-pages`. `download` retains `--limited` and `--index-name`, and
acquires encrypted parts and metadata. `finalize` decrypts local inputs, assembles
PDFs atomically, and skips unchanged hashed inputs/outputs without network access.
Missing metadata requires another download. `run` composes discovery, download
and local finalization, with automatic S3 publication at committed checkpoints.
After S3 publication, it also uploads each verified PDF to Yandex Disk and inserts
its upstream bibliographic metadata into PostgreSQL. Each destination step has
its own saved receipt; rerunning skips completed steps for the same PDF hash.
`run` requires S3 settings, provider access values, Yandex Disk token/target
directory and the upstream metadata database connection before starting.
Progress and receipts use top-level `database.url`; upstream metadata uses
`sources.milli_kitaphana.database_url`. Both URLs can point to the same PostgreSQL
service when it has the required schemas and permissions. S3 access credentials,
region, endpoint and document bucket belong in `storage.s3` in this same file.
No shell exports, `.env` file or AWS credential file is needed.

The default download pass fetches complete, non-limited books. It downloads the
encrypted metadata first to check access, and skips book parts when any part is
restricted. Book parts are downloaded before the local finalization pass.
Parsed-page cover images are neither downloaded nor saved as artifacts; textual
bibliographic metadata is retained. Recovery may read a cover URL as a clue to a
broken inventory code, without downloading the image.

Configured page, item, byte and time limits still apply. A single invocation may
stop with a backlog; repeat the same command to resume. Downloads and local
finalization remain available separately without Yandex/database publication
credentials. `--summary-only` includes `yandex_published` and
`upstream_metadata_saved` counts.

`publish --target yandex` uploads verified PDFs and inserts upstream metadata into
PostgreSQL using the existing clients. Each destination step is checkpointed per
record. A process failure after a remote operation but before its checkpoint can
require destination inspection before retrying, especially for insert-only SQL.
The same caveat applies to automatic publication during `run`.

A read-only upstream schema inspection confirmed
`monocorpus.library_upstream_metadata` has required `md5 text` and
`payload_json jsonb` columns, insert permission, no user triggers or row security,
and checks requiring a lowercase 32-character hexadecimal MD5 and a JSON object.
The primary key is `md5`: the current plain insert rejects an existing hash.
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
