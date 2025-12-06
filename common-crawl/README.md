Common Crawl finepdfs helper
============================

This folder keeps a tiny pipeline for incrementally pulling Tatar PDFs from the HuggingFace `HuggingFaceFW/finepdfs` dataset (Common Crawl derived) and optionally pushing them to Yandex Disk. Everything revolves around the JSON index stored at `__artifacts/common.crawl/docs-index.json`.

Workflow
--------
- `python common-crawl/cli.py index` refreshes the index from the HF parquet shards (tat_Cyrl test/train, tat_Latn train) via `datatrove.ParquetReader`. It merges into the existing index, so reruns keep old flags while updating URL/file_path/offset/script.
- `python common-crawl/cli.py download` first tries to fetch missing docs directly from `url` (`download_directly`), then falls back to Common Crawl WARC downloads (`download_cc`).
  - Successful PDFs are checked with `pymupdf`, hashed (md5), and moved to `~/.common-crawl/result/{script}/<md5>-<source>.pdf`. The index is updated with `md5`, `path_to_file`.
  - For WARC-only entries, `_augment` pulls the parquet index (cached under `~/.common-crawl/warcs`) to discover the real `warc_filename` for each doc and then `_fetch_record_from_offset` streams the PDF by byte-range from `https://data.commoncrawl.org/...`.
  - Temporary files live in `__artifacts/common.crawl/tmp.pdf`; every run writes a timestamped backup of the index before mutating it.
- `python common-crawl/cli.py upload` pushes downloaded PDFs to Yandex Disk under `/НейроТатарлар/kitaplar/common_crawl` (set `token` in `upload.py`). It de-duplicates by MD5 against the `monocorpus_models.Document` table and marks `uploaded` in the index.

Index fields to remember
------------------------
- `url`, `file_path`, `offset`, `script` come from the HF parquet metadata.
- `augmented_file_path` is filled when a parquet index points to a WARC file and we have to look it up.
- `md5`, `path_to_file`, `uploaded` are filled by the download/upload steps to keep things incremental.

Typical incremental run
-----------------------
1) Update the list of docs: `python common-crawl/cli.py index`
2) Download anything new: `python common-crawl/cli.py download`
3) (Optional) Upload to Yandex after setting the token: `python common-crawl/cli.py upload`
