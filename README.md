# Books Crawler

This repository contains small crawlers and pipelines for collecting Tatar book data from
multiple sources (websites and Common Crawl). Each subfolder is a mostly independent workflow.

## Layout
- `common-crawl/` - index, download, and optional upload pipeline for Common Crawl "finepdfs".
- `litres/` - Litres indexing and PDF/text downloads, plus metadata and upload helpers.
- `milli_kitaphana/` - Milli Kitaphana indexing, download, decrypt, and list splitting.
- `tatkniga/` - Tatkniga page discovery, metadata collection, and download helpers.
- `__artifacts/` - local indices and intermediate artifacts (per source).
- `proxy-compose.yml` - optional HTTP proxy service for download workflows.
- `requirements.txt` - Python dependencies.

## Setup
1) Install dependencies:
   `python -m pip install -r requirements.txt`
2) Fill in the required tokens in each crawler's `config.yaml`.

## Quick start
- Common Crawl:
  `python common-crawl/cli.py index`
  `python common-crawl/cli.py download`
  `python common-crawl/cli.py upload`
- Litres:
  `python litres/cli.py index`
  `python litres/cli.py pdf`
  `python litres/cli.py text`
  `python litres/cli.py metadata`
  `python litres/cli.py upload`
  `python litres/cli.py hf`
- Milli Kitaphana:
  `python milli_kitaphana/cli.py index`
  `python milli_kitaphana/cli.py split --parts 4`
  `python milli_kitaphana/cli.py download`
  `python milli_kitaphana/cli.py decrypt`
- Tatkniga:
  `python tatkniga/main.py`

## Artifacts and state
- Most workflows store JSON indices and work files in `__artifacts/<source>/`.
- The Common Crawl pipeline also writes downloads under `~/.common-crawl/`.
- Milli Kitaphana list splitting uses `__artifacts/milli.kitaphana/subindexes`.
- The optional `filter.json` in the repo root is used by Milli Kitaphana list splitting.

See the per-folder READMEs for source-specific details and required config fields.
