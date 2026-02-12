# Milli Kitaphana

Crawler/downloader/decryptor for `kitap.tatar.ru`.

Main state lives in `__artifacts/milli.kitaphana/_index/books-index.json`.

## CLI commands

- `python milli_kitaphana/cli.py index`
  - Crawl cards and refresh index entries.
- `python milli_kitaphana/cli.py split --parts N [--dest PATH] [--prefix NAME]`
  - Split pending docs into sub-index files under `__artifacts/milli.kitaphana/subindexes/` by default.
- `python milli_kitaphana/cli.py download [--limited] [--index-name NAME]`
  - Without `--limited`: process docs where `broken != true` and `downloaded is None`.
  - With `--limited`: process docs where `broken != true`, `needs_full_download == true`, and `downloaded in {None, "limited"}`.
- `python milli_kitaphana/cli.py decrypt`
  - Decrypt downloaded parts and update index status.
- `python milli_kitaphana/cli.py merge-index PATH`
  - Merge a worker index into the main index.

## Helper script

- `python milli_kitaphana/mark_existing_limited.py`
  - Reads non-full documents from Postgres, matches them to index records, and marks `needs_full_download`.
  - Uses local upstream metadata cache at `~/.monocorpus/misc/upstream_metadata`.

## Config

- File: `milli_kitaphana/config.yaml`
- Read with `utf-8-sig` to tolerate BOM on Windows.
- Keep placeholders in git (`<SET ME>`); do not commit real tokens/keys.

## Optional filter

If root `filter.json` exists, `split` keeps only entries matching:
- `download_codes`
- `titles`
