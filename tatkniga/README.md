# Tatkniga

Legacy Tatkniga crawler for page discovery, metadata extraction, and optional downloads.

## Current state

- `tatkniga/main.py` currently imports `from src.tatkniga ...`.
- In this repository layout there is no `src/` package, so running `python tatkniga/main.py` fails until imports are adjusted.
- Downloader/upload logic exists in `books_downloader.py` but is not executed by `main.py`.

## Intended workflow

1. Collect candidate pages into `tatkniga/workdir/books_pages.txt`.
2. Visit book pages and write metadata to `tatkniga/workdir/books_metas.json`.
3. Download/upload using `books_downloader.py` (manual invocation/integration required).

## Config caveat

Tatkniga config loaders currently read `../../config.yaml` relative to script path.
`tatkniga/config.yaml` exists, but current code does not use it without patching `read_config()`.

## Artifacts

- `tatkniga/workdir/visited_pages.txt`
- `tatkniga/workdir/visited_book_pages.txt`
- `tatkniga/workdir/books_pages.txt`
- `tatkniga/workdir/books_metas.json`
- `tatkniga/workdir/downloads/`
