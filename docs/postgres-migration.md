# Postgres state

All source progress now lives in PostgreSQL. Local originals, temporary downloads
and explicitly requested review/report exports remain files. No progress JSON,
worker-index files, lock files, automatic index backups or run-summary files are
written by processing commands. Existing JSON files are never
automatically imported and database failures never fall back to them.

Set `DATABASE_URL` in the process environment using a secret manager or a shell
prompt; do not put credentials in YAML or Git. PostgreSQL URLs retain their SSL
query parameters. Prefer certificate verification with the provider CA when
configuring production access. Rotate any credentials previously shared in chat.

```bash
read -r -s -p 'Database URL: ' DATABASE_URL
export DATABASE_URL
.venv/bin/python cli.py database init
.venv/bin/python cli.py database status
```

`init` explicitly creates the version-1 schema and tables and can be repeated.
`status`, normal source status commands, and `sources` do not initialize tables.
Run init before starting writers. Normal existing source commands continue to use
the selected operational YAML for source options and the artifact workspace.

## Import established progress

Preview imports first (no database connection or writes):

```bash
.venv/bin/python cli.py database import --source litres __artifacts/litres/books-index.json __artifacts/litres/candidates-index.json
.venv/bin/python cli.py database import --source milli_kitaphana __artifacts/milli.kitaphana/manifest.json
.venv/bin/python cli.py database import --source tatkniga __artifacts/ingestion/tatkniga/manifest.json __artifacts/ingestion/tatkniga-reader-pilot/tatkniga/manifest.json
.venv/bin/python cli.py database import --source common_crawl __artifacts/common.crawl/docs-index.json
```

Append `--apply` to each command to import. Original files remain untouched.
Import only these four sources; other sources start empty. Milli can alternatively
import its legacy `_index/books-index.json`. Use the authoritative file when the
manifest and legacy index disagree; preview reports incompatible overlapping rows
and refuses apply until authoritative inputs are selected.

Import receipts use content fingerprints. Repeating the same import is a no-op;
existing database rows take precedence over later imports. Each source's rows and
receipt commit together. Tatkniga unions observation/result evidence from its two
manifests, preserves downloaded assets and complete assembled books, and starts
new discovery rather than mixing probe checkpoints.

Completed acquisition evidence is retained independently of local file existence:
Milli's `downloaded=full`, Litres acquisition or PDF/Markdown output fields,
Tatkniga downloaded assets and complete assembled books, and Common Crawl's
existing paths/upload flags. Limited downloads remain limited. Completion is not
proof of an S3 upload: this change neither queries S3 nor changes publication.
Uncertain completion stays pending. Imported acquisition completion does not
invent finalization: unfinished assembly still requires its inputs. Explicit
rechecks may acquire files again.

```bash
.venv/bin/python scripts/ingestion_overview.py --database
.venv/bin/python scripts/ingestion_overview.py --database --source litres
.venv/bin/python cli.py --config config/sources/tatkniga.yaml status --source tatkniga
```

Local overview arguments still inspect archived JSON snapshots, explicitly.

## Fresh runners and provider maintenance

Litres books and candidate indexes are accessed through the shared database-backed
runtime throughout discovery, metadata, review, acquisition and publication.
`review --action export` writes a TSV only when explicitly requested; sync reads
that user-edited export and commits the decisions to Postgres.

Milli `split --parts N --prefix worker` stores `selection:worker-1`, etc., in
Postgres. `download --index-name worker-1` resolves the selection against current
record metadata. `--dest DIRECTORY` on split additionally exports JSON on explicit
request; those files are never read as worker state. Selection filters now belong
under `sources.milli_kitaphana.split_filter` (`download_codes` and `titles` lists),
rather than an implicit repository-root filter file. `merge-index PATH` remains
an explicit legacy JSON import into Postgres.

`recover --report NAME` selects a Postgres journal, defaulting to `default`.
It no longer treats that argument as a local path or writes Markdown automatically.
To import old worker selections, recovery journals and auxiliary recovery evidence:

```bash
.venv/bin/python cli.py database import --source milli_kitaphana __artifacts/milli.kitaphana/manifest.json --processing-dir __artifacts/milli.kitaphana
```

Add `--apply` after reviewing the preview. Existing database entries win. The old
`_recovery/report.json` becomes journal `default`; other journal names use the
filename stem. Legacy subindexes become database selections containing record IDs.
Auxiliary recovery JSON is retained as evidence in source state.

Processing commands return `state_key: last_run` (Miras probes use `last_probe`);
full details live in that source's Postgres state table. They do not emit a
`summary_path`. The read-only database overview is suitable for fresh workspaces.

Recorded completed acquisition and unchanged finalization are skipped even when
local files are absent. An unfinished assembly stage lacking its inputs reports
`awaiting_inputs`, without erasing acquisition progress. Restore inputs or use an
explicit `download --recheck` to reacquire them. Document bodies, images and decoded
source content are still files; ensure new outputs reach durable storage before
discarding runner disk. See [S3 publication](ingestion/operations.md#s3-publication) and
[scheduled operations](scheduled-ingestion.md) for durable output handling.

## Storage and connection ownership

The `ingestion` schema contains `<source>_records`, `<source>_assets`, and
`<source>_state` tables, each keyed by the existing identity and carrying JSONB.
Manifest/index payload shapes are retained, with only imported completion markers
added. The bookkeeping table stores schema version and import receipts. Only
primary keys are indexed initially. Strings containing NUL or unpaired Unicode
surrogates use a reversible base64 marker at the repository boundary because
JSONB cannot store them; reads restore the exact original strings. A save updates changed rows in one transaction,
including discovery observations and frontier checkpoints.

Every process reuses an engine per database URL. Defaults: `PG_POOL_SIZE=2`,
`PG_POOL_TIMEOUT=30` seconds, `PG_CONNECT_TIMEOUT=10` seconds, zero overflow.
One checked-out session holds the source advisory lock; the other performs short
transactions. Keep pool size at least two for writers. Separate processes do not
share pools; Aiven free permits 20 connections in total. Account for other clients
before starting concurrent sources. Lock-session identity is checked at saves and
shared network budget checkpoints; connection loss aborts the command.

Use database status to measure table/index and database sizes; monitor provider
storage separately because its 1 GB disk also serves WAL and other overhead.
There is no automatic history deletion. Grow the plan or explicitly archive data
if storage becomes insufficient.

Fresh workers recover progress from Postgres. `run` restores missing unpublished
inputs; assemblies still need their input files in the artifact workspace. See
[scheduled recovery](scheduled-ingestion.md#runtime-and-storage).

## Migration history

The Aiven migration was applied on 2026-11-06. Import counts, backup locations and
manual verification are in the [verification archive](archive/implementation-verification.md#postgres-migration-verification).
