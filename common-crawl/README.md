# Common Crawl

Incremental pipeline for Tatar PDFs sourced from the `HuggingFaceFW/finepdfs` dataset.

Main state file: `__artifacts/common.crawl/docs-index.json`

## Commands

- `python common-crawl/cli.py index`
  - Read parquet shards via `datatrove.ParquetReader`.
  - Merge `url`, `file_path`, `offset`, `script` into local index.
- `python common-crawl/cli.py download`
  - Tries direct PDF download by `url`.
  - Falls back to Common Crawl WARC offset fetch.
  - Validates PDFs, computes MD5, and moves files to `~/.common-crawl/result/{script}/`.
- `python common-crawl/cli.py upload`
  - Uploads downloaded files to Yandex Disk.
  - Deduplicates by MD5 using `monocorpus_models`.
  - Marks `uploaded` in the index.

## Runtime files

- Index: `__artifacts/common.crawl/docs-index.json`
- Temporary PDF: `__artifacts/common.crawl/tmp.pdf`
- WARC/parquet cache: `~/.common-crawl/warcs/`
- Final downloaded files: `~/.common-crawl/result/`

## Notes

- `upload.py` uses a hardcoded `token = "<<set me>>"` placeholder; set it before `upload`.
- Index backups are written during download/upload operations.
