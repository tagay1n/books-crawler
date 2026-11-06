# Common Crawl

Incremental pipeline for Tatar PDFs sourced from the `HuggingFaceFW/finepdfs` dataset.

Progress lives in the shared Postgres `ingestion.common_crawl_*` tables.
See [database setup and legacy import](../docs/postgres-migration.md).

## Commands

- `python common-crawl/cli.py index`
  - Read parquet shards via `datatrove.ParquetReader`.
  - Merge `url`, `file_path`, `offset`, `script` into the database index.
- `python common-crawl/cli.py download`
  - Tries direct PDF download by `url`.
  - Falls back to Common Crawl WARC offset fetch.
  - Validates PDFs, computes MD5, and moves files to `~/.common-crawl/result/{script}/`.
- `python common-crawl/cli.py upload`
  - Uploads downloaded files to Yandex Disk.
  - Deduplicates by MD5 using `monocorpus_models`.
  - Marks `uploaded` in the index.

## Runtime files

- Index: Postgres; legacy JSON is used only for explicit import.
- Temporary PDF: `__artifacts/common.crawl/tmp.pdf`
- WARC/parquet cache: `~/.common-crawl/warcs/`
- Final downloaded files: `~/.common-crawl/result/`

## Notes

- `upload.py` uses a hardcoded `token = "<<set me>>"` placeholder; set it before `upload`.
- Processing commands do not write index files or automatic backups.
