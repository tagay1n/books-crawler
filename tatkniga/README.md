# Tatkniga crawler

This folder contains the Tatkniga crawler that discovers book pages, extracts metadata,
and (optionally) downloads files.

## Workflow
1) Collect book page links into `workdir/books_pages.txt`
2) Visit book pages and write metadata to `workdir/books_metas.json`
3) Download files using `books_downloader.py`

The current `tatkniga/main.py` runs steps 1 and 2. Step 3 is present in
`books_downloader.py` but is commented out in `main.py`.

## Commands
- `python tatkniga/main.py` - run page discovery and metadata collection.

## Config
The code reads `../../config.yaml` relative to the script location. Make sure your
config file is accessible from that path or adjust `read_config()` to use
`tatkniga/config.yaml`.

## Artifacts
- `tatkniga/workdir/visited_pages.txt` - non-book pages visited
- `tatkniga/workdir/visited_book_pages.txt` - book pages visited
- `tatkniga/workdir/books_pages.txt` - queue of book pages
- `tatkniga/workdir/books_metas.json` - collected metadata
- `tatkniga/workdir/downloads/` - downloaded files
