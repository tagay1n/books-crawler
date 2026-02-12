# Books Crawler

Repository with four independent pipelines for collecting Tatar books and metadata:

- `milli_kitaphana/`
- `litres/`
- `common-crawl/`
- `tatkniga/`

Each pipeline has its own CLI/scripts and its own local state in `__artifacts/` or `~/`.

## Setup

1. Create and activate a virtual environment.
   Linux/macOS:
   `python -m venv .venv && source .venv/bin/activate`
   Windows PowerShell:
   `python -m venv .venv; .\.venv\Scripts\Activate.ps1`
   Windows Git Bash:
   `python -m venv .venv && source .venv/Scripts/activate`
2. Install dependencies:
   `python -m pip install -r requirements.txt`
3. Fill config templates with your real credentials only in local files:
   - `milli_kitaphana/config.yaml`
   - `litres/config.yaml`
   - `tatkniga/config.yaml` (note: current Tatkniga code reads another path; see folder README)

## Pipeline entry points

- Milli Kitaphana:
  - `python milli_kitaphana/cli.py index`
  - `python milli_kitaphana/cli.py split --parts 4`
  - `python milli_kitaphana/cli.py download`
  - `python milli_kitaphana/cli.py decrypt`
- Litres:
  - `python litres/cli.py index`
  - `python litres/cli.py pdf`
  - `python litres/cli.py text`
  - `python litres/cli.py metadata`
  - `python litres/cli.py upload`
  - `python litres/cli.py hf`
- Common Crawl:
  - `python common-crawl/cli.py index`
  - `python common-crawl/cli.py download`
  - `python common-crawl/cli.py upload`
- Tatkniga:
  - `python tatkniga/main.py` (currently requires import-path fix; see `tatkniga/README.md`)

## State files

- `__artifacts/milli.kitaphana/_index/books-index.json` stores Milli Kitaphana crawl/download state.
- `__artifacts/litres/books-index.json` stores Litres state.
- `__artifacts/common.crawl/docs-index.json` stores Common Crawl state.
- `~/.common-crawl/` stores downloaded Common Crawl files and caches.

See folder READMEs for pipeline-specific behavior, options, and caveats.
