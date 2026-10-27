# Books Crawler

The repository retains three independent legacy pipelines for collecting Tatar books and metadata:

- `milli_kitaphana/`
- `litres/`
- `common-crawl/`

Each pipeline has its own CLI/scripts and its own local state in `__artifacts/` or `~/`.

The new shared CLI supports local discovery and document downloads from the
Мәгариф archive, Tatarica library, Darul-Kutub catalog, Kazan Utları archive,
and Tatkniga's public library. Tatkniga downloads direct files for Tatar-labelled
editions and assembles supported public readers, including those with no language
label. Tatkniga and Kazan Utları page images are retained and assembled into PDFs
with PyMuPDF.
See [local ingestion](docs/local-ingestion.md) for configuration,
commands, artifact locations, and recovery. The legacy pipeline commands below
continue to operate independently.

Miras has a cookie-based HTTP access pilot:
`python cli.py --config ingestion.yaml probe --source miras --session-file PATH`.
See [local ingestion](docs/local-ingestion.md#miras-cookie-based-access-pilot)
for its session format and the remembered browser-extension fallback.

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
   For the shared CLI, copy `ingestion.example.yaml` to `ingestion.yaml` and
   select it with `--config`. Tatkniga does not require cloud credentials.

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
  - `python cli.py --config ingestion.yaml discover --source tatkniga`
  - `python cli.py --config ingestion.yaml download --source tatkniga --limit 1`
  - `python cli.py --config ingestion.yaml status --source tatkniga`

## State files

- `__artifacts/milli.kitaphana/_index/books-index.json` stores Milli Kitaphana crawl/download state.
- `__artifacts/litres/books-index.json` stores Litres state.
- `__artifacts/common.crawl/docs-index.json` stores Common Crawl state.
- `~/.common-crawl/` stores downloaded Common Crawl files and caches.
- `__artifacts/ingestion/tatkniga/` stores the new Tatkniga manifest and local files.
- `tatkniga/workdir/` and `paid_files.csv` retain historical data; they are not imported automatically.

See folder READMEs for pipeline-specific behavior, options, and caveats.
