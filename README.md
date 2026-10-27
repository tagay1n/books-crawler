# Books Crawler

The repository retains three independent legacy pipelines for collecting Tatar books and metadata:

- `milli_kitaphana/`
- `litres/`
- `common-crawl/`

Each pipeline has its own CLI/scripts and its own local state in `__artifacts/` or `~/`.

The new shared CLI supports local discovery and document downloads from the
Мәгариф archive, Tatarica library, Darul-Kutub catalog, Kazan Utları archive,
Tatkniga's public library, Miras books, Isxaki's book/work collections, and
Tatar-labelled Internet Archive text items with public original document uploads,
and KFU's Turkic–Tatar books and manuscript collections with public direct files.
Tatkniga downloads direct files for Tatar-labelled
editions and assembles supported public readers, including those with no language
label. Tatkniga and Kazan Utları page images are retained and assembled into PDFs
with PyMuPDF.
See [local ingestion](docs/local-ingestion.md) for configuration,
commands, artifact locations, and recovery. The legacy pipeline commands below
continue to operate independently.

Wikimedia Commons also supports discovery of document-format books through its
metadata API. Use `discover --source commons` and `status --source commons`;
cover/title-page images are skipped entirely. This source does not support
document downloads or the combined `run` command.

Miras downloads exposed original PDFs across all languages using a session
exported from an ordinary verified browser. Pass `--session-file PATH` to its
`discover`, `download`, or `run` command; `status` needs no session. The original
`probe --source miras --session-file PATH` diagnostic remains available.
See [local ingestion](docs/local-ingestion.md#miras-books-and-browser-session-access)
for its session format and recovery instructions.

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
- Miras (books, all languages):
  - `python cli.py --config ingestion.yaml discover --source miras --session-file PATH --max-pages 2`
  - `python cli.py --config ingestion.yaml download --source miras --session-file PATH --limit 2`
  - `python cli.py --config ingestion.yaml status --source miras`
- Isxaki (original editions, works, and books about Iskhaki):
  - `python cli.py --config ingestion.yaml discover --source isxaki`
  - `python cli.py --config ingestion.yaml download --source isxaki --limit 1`
  - `python cli.py --config ingestion.yaml status --source isxaki`
- Internet Archive (explicit Tatar language labels; original uploads only):
  - `python cli.py --config ingestion.yaml discover --source internet_archive --max-pages 2`
  - `python cli.py --config ingestion.yaml download --source internet_archive --limit 1`
  - `python cli.py --config ingestion.yaml status --source internet_archive`
- KFU historical books and manuscripts (all collection languages; public direct documents only):
  - `python cli.py --config ingestion.yaml discover --source kfu_books --max-pages 1`
  - `python cli.py --config ingestion.yaml discover --source kfu_manuscripts --max-pages 1`
  - `python cli.py --config ingestion.yaml download --source kfu_books --limit 1`
  - `python cli.py --config ingestion.yaml status --source kfu_manuscripts`

## State files

- `__artifacts/milli.kitaphana/_index/books-index.json` stores Milli Kitaphana crawl/download state.
- `__artifacts/litres/books-index.json` stores Litres state.
- `__artifacts/common.crawl/docs-index.json` stores Common Crawl state.
- `~/.common-crawl/` stores downloaded Common Crawl files and caches.
- `__artifacts/ingestion/tatkniga/` stores the new Tatkniga manifest and local files.
- `__artifacts/ingestion/isxaki/` stores collection metadata and unchanged original document files.
- `__artifacts/ingestion/internet_archive/` stores Archive metadata, original-upload files, and resumable discovery state.
- `__artifacts/ingestion/kfu_books/` and `kfu_manuscripts/` store independent collection manifests, files, and restricted-file evidence.
- `__artifacts/ingestion/miras/` stores the full Miras catalog and PDFs; `pilot/` retains the original access experiment separately.
- `tatkniga/workdir/` and `paid_files.csv` retain historical data; they are not imported automatically.

See folder READMEs for pipeline-specific behavior, options, and caveats.
