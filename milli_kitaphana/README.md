# Milli Kitaphana pipeline

This folder indexes, downloads, and decrypts documents from the Milli Kitaphana site.
Downloads can be split into sublists to run workers in parallel.

## Commands
- `python milli_kitaphana/cli.py index` - build or update `__artifacts/milli.kitaphana/books-index.json`.
- `python milli_kitaphana/cli.py split --parts N` - split pending docs into N sublists.
- `python milli_kitaphana/cli.py download` - download missing docs (supports `--proxy`).
- `python milli_kitaphana/cli.py decrypt` - decrypt downloaded parts into PDFs.
- `python milli_kitaphana/cli.py merge-index <path>` - merge a partial index into the main one.

## Config
`milli_kitaphana/config.yaml` holds API endpoints, crypto keys, and storage credentials.

## Artifacts
- Index: `__artifacts/milli.kitaphana/books-index.json`
- Split lists: `__artifacts/milli.kitaphana/subindexes/`
- Download and decrypt artifacts are stored under `__artifacts/milli.kitaphana/`.

## Filtering
If `filter.json` exists in the repo root, `split` will only include entries that match
`download_codes` or `titles` in that file.
