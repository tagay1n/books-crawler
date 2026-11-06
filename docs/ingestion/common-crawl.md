# Common Crawl / FinePDFs

Common Crawl uses the unified CLI as `common_crawl`. The adapter and provider
helpers live in `ingestion/common_crawl*.py`; the old `common-crawl/` directory
and standalone CLI have been removed.

Discovery reads the same `HuggingFaceFW/finepdfs` selections as before:
`tat_Cyrl/test`, `tat_Cyrl/train`, and `tat_Latn/train`. It merges URL, WARC or
parquet path, offset and script evidence while preserving acquisition and
publication fields already stored in Postgres. These are dataset language
selections, without an additional manual content-language review.

## Configuration

Add this source section to your selected operational YAML, alongside the shared
`artifacts_root`, `limits` and `network` sections from `ingestion.example.yaml`:

```yaml
sources:
  common_crawl:
    archive_url: https://huggingface.co/datasets/HuggingFaceFW/finepdfs
    result_dir: ~/.common-crawl/result
    cache_dir: ~/.common-crawl/warcs
    yandex:
      disk:
        oauth_token: <SET ME>
        target_dir: /НейроТатарлар/kitaplar/common_crawl
```

Publication credentials are needed only for `publish`. Discovery, download and
status need no Yandex token. MD5 publication deduplication uses the existing
`monocorpus_models` database session, as in the former uploader.

## Commands

```bash
.venv/bin/python cli.py sources
.venv/bin/python cli.py --config ingestion.yaml discover --source common_crawl
.venv/bin/python cli.py --config ingestion.yaml download --source common_crawl --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source common_crawl --limit 1
.venv/bin/python cli.py --summary-only --config ingestion.yaml status --source common_crawl
.venv/bin/python cli.py --config ingestion.yaml publish --source common_crawl --target yandex
```

The former `index` command is now `discover`; `upload` is now explicit
`publish --target yandex`. `run` composes discovery and download only.
`finalize`, `metadata`, `review`, `--recheck`, `--format text`,
and browser sessions are unsupported.

Downloads try each selected URL directly, then use Common Crawl WARC offsets
for the selected failures, augmenting parquet references when needed. Files are
validated as PDFs, named using MD5 and saved under the existing per-script result
directories. `--limit` and `limits.max_items` bound selected documents across both
attempts. Completed download/upload markers are skipped on repeat runs.
Direct, parquet-cache and WARC payload downloads use shared HTTP timeouts,
pacing, retries, byte/file caps, deadline and disk-reserve checks. FinePDFs
listing uses `datatrove.ParquetReader` and its own Hugging Face I/O; the shared
HTTP byte counters do not include those reads. Discovery checks the deadline
between records and checkpoints each dataset directory and on exit. Its
`--max-pages` cap counts the three dataset directories in the order above;
repeat discovery refreshes the selections from the beginning.

Publishing uses the existing Yandex client and MD5 deduplication, respects the
item cap and checks the deadline between files. Its client controls upload I/O.
Successful publication is checkpointed before deleting the local file, preserving
the former uploader's local cleanup behavior. Publishing is never part of `run`.

## State and paths

- Progress: existing Postgres `ingestion.common_crawl_*` tables, unchanged record
  layout; existing state needs no migration.
- Temporary PDF: `<artifacts_root>/common_crawl/tmp.pdf`; optional `artifact_dir`
  overrides this working directory.
- WARC/parquet cache: `~/.common-crawl/warcs/`, configurable with `cache_dir`.
- Final PDFs: `~/.common-crawl/result/{cyrl,latn}/`, configurable with `result_dir`.
- Relative source path overrides resolve against the operational YAML directory.

Source writers use the shared `common_crawl` Postgres lock. Status reads counts
without writing progress, creating directories or fetching network resources.
Stage results are JSON; `--summary-only` prints compact JSON and suppresses
provider progress. Last-run details remain in Postgres.

## Migration verification (2026-11-06)

Compiled changed Python modules; checked CLI help, source listing, lazy provider
imports, operational YAML loading, unchanged persistence table names and CLI
rejection of unsupported stages/options, excessive limits and missing publication
credentials. `git diff --check` passed. No automated tests were added or run.
Live status/overview could not run because this shell has no `DATABASE_URL`;
no discovery, acquisition or remote publication was performed during migration.

For archived JSON state only, use the existing explicit import command:

```bash
.venv/bin/python cli.py database import --source common_crawl __artifacts/common.crawl/docs-index.json
```

See [database setup and legacy import](../postgres-migration.md).
