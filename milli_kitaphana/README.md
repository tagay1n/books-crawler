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
  - Documents with missing parts are treated as limited and ignored without changing their index entry.
- `python milli_kitaphana/cli.py decrypt`
  - Decrypt downloaded parts, upload PDFs to Yandex Disk, persist upstream metadata in PostgreSQL, and update index status.
- `python milli_kitaphana/cli.py merge-index PATH`
  - Merge a worker index into the main index.

## Helper script

- `python milli_kitaphana/mark_existing_limited.py`
  - Reads non-full documents from Postgres, matches them to index records, and marks `needs_full_download`.
  - Uses local upstream metadata cache at `~/.monocorpus/misc/upstream_metadata`.

## Config

- File: `milli_kitaphana/config.yaml`
- Example: `milli_kitaphana/config.example.yaml`
- Read with `utf-8-sig` to tolerate BOM on Windows.
- Keep placeholders in git (`<SET ME>`); do not commit real tokens/keys.
- Set `database_url` to the TLS-enabled Aiven PostgreSQL URI for the insert-only crawler user before running `decrypt`.

The Aiven login `books_crawler` inherits the non-login role
`library_upstream_metadata_insert`. That role has only `CONNECT` on `defaultdb`,
`USAGE` on `monocorpus`, and column-level `INSERT (md5, payload_json)` on
`monocorpus.library_upstream_metadata`. It must not be granted read, update, or
delete access.

## Optional filter

If root `filter.json` exists, `split` keeps only entries matching:
- `download_codes`
- `titles`
