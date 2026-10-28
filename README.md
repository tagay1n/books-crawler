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
and KFU's Turkic–Tatar books, manuscripts, «Ил» and «Азад халык» newspapers,
and «Шура» journal issues with public direct files and supported public image readers. Tatar Galyame's educational catalog also
supports downloading its explicitly listed hosted documents across all languages.
Tatkniga downloads direct files for Tatar-labelled
editions and assembles supported public readers, including those with no language
label. Tatkniga and Kazan Utları page images are retained and assembled into PDFs
with PyMuPDF.
KFU readers retain their original JPEGs and produce 200 DPI colour PDFs at JPEG
quality 85, preferring an available public direct PDF over image assembly.
See [local ingestion](docs/local-ingestion.md) for configuration,
commands, artifact locations, and recovery. The legacy pipeline commands below
continue to operate independently.

Wikimedia Commons supports discovery and downloading of original document-format
books from its Tatar-language category. Downloads verify the source-reported size
and SHA-1 before publication. Cover/title-page images are skipped entirely.

Miras downloads exposed original PDFs across all languages using a session
exported from an ordinary verified browser. Pass `--session-file PATH` to its
`discover`, `download`, or `run` command; `status` needs no session. The original
`probe --source miras --session-file PATH` diagnostic remains available.
See [local ingestion](docs/local-ingestion.md#miras-books-and-browser-session-access)
for its session format and recovery instructions.

Use `kfu_repository` for automatic discovery across all historical collections on
`repo.kpfu.ru`. It requires explicit Tatar item-language labels and reuses verified
originals from existing KFU manifests. Run:

```bash
python cli.py --config ingestion.yaml run --source kfu_repository --max-pages 25 --limit 1
```

Discovery resumes across invocations. Existing collection-specific sources remain
available; Татар галәме and other KFU domains have separate adapters. See
[repository-wide ingestion](docs/local-ingestion.md#kfu-historical-repository-all-collections).

The separate academic archive is available as `kfu_dspace`. Its native `татар`
topic search discovers candidates; only explicit Tatar item-language metadata or
an individual SHA-256-pinned file review admits a public PDF. Missing labels stay
held, and restricted records are not acquired. See
[academic archive usage and reviews](docs/local-ingestion.md#kfu-academic-electronic-archive).

KFU «Вакыт» is available as `kfu_vakyt`: resumable exact-series discovery,
public JPEG/JPEG2000 originals, and complete 200 DPI colour issue PDFs. Explicit
Tatar item-language labels are required; unlabelled records remain held. See
[usage and limits](docs/local-ingestion.md#kfu-вакыт-newspaper) and the
[earlier pilot](docs/kfu-vakyt-pilot.md).

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
- KFU historical books and manuscripts (all collection languages; public documents and JPEG readers):
  - `python cli.py --config ingestion.yaml discover --source kfu_books --max-pages 1`
  - `python cli.py --config ingestion.yaml discover --source kfu_manuscripts --max-pages 1`
  - `python cli.py --config ingestion.yaml download --source kfu_books --limit 1`
  - `python cli.py --config ingestion.yaml status --source kfu_manuscripts`
- KFU «Ил» newspaper (explicit Tatar language labels required):
  - `python cli.py --config ingestion.yaml discover --source kfu_il --max-pages 1`
  - `python cli.py --config ingestion.yaml download --source kfu_il --limit 1`
  - `python cli.py --config ingestion.yaml status --source kfu_il`
- KFU academic archive (topic discovery, with separate language admission):
  - `python cli.py --config ingestion.yaml discover --source kfu_dspace --max-pages 2`
  - `python cli.py --config ingestion.yaml download --source kfu_dspace --limit 1`
  - `python cli.py --config ingestion.yaml status --source kfu_dspace`
- KFU «Азад халык» newspaper (explicit Tatar language labels required):
  - `python cli.py --config ingestion.yaml discover --source kfu_azad_halyk --max-pages 2`
  - `python cli.py --config ingestion.yaml download --source kfu_azad_halyk --limit 1`
  - `python cli.py --config ingestion.yaml status --source kfu_azad_halyk`
- KFU «Шура» journal (explicit Tatar language labels required):
  - `python cli.py --config ingestion.yaml discover --source kfu_shura --max-pages 2`
  - `python cli.py --config ingestion.yaml download --source kfu_shura --limit 1`
  - `python cli.py --config ingestion.yaml status --source kfu_shura`
- Tatar Galyame (all hosted documents; external references retained as metadata):
  - `python cli.py --config ingestion.yaml discover --source tatargalyame --max-pages 15`
  - `python cli.py --config ingestion.yaml download --source tatargalyame --limit 1`
  - `python cli.py --config ingestion.yaml status --source tatargalyame`
- Wikimedia Commons (Tatar-language books and subcategories; original documents only):
  - `python cli.py --config ingestion.yaml discover --source commons --max-pages 5`
  - `python cli.py --config ingestion.yaml download --source commons --limit 1`
  - `python cli.py --config ingestion.yaml status --source commons`

## State files

- `__artifacts/milli.kitaphana/_index/books-index.json` stores Milli Kitaphana crawl/download state.
- `__artifacts/litres/books-index.json` stores Litres state.
- `__artifacts/common.crawl/docs-index.json` stores Common Crawl state.
- `~/.common-crawl/` stores downloaded Common Crawl files and caches.
- `__artifacts/ingestion/tatkniga/` stores the new Tatkniga manifest and local files.
- `__artifacts/ingestion/isxaki/` stores collection metadata and unchanged original document files.
- `__artifacts/ingestion/internet_archive/` stores Archive metadata, original-upload files, and resumable discovery state.
- `__artifacts/ingestion/kfu_books/` and `kfu_manuscripts/` store independent collection manifests, original files, derived colour PDFs, and restricted-file evidence.
- `__artifacts/ingestion/kfu_il/` stores Il issue metadata, language/access decisions, original files, and an independent resumable discovery queue.
- `__artifacts/ingestion/kfu_azad_halyk/` stores Azad Halyk issue metadata and original public PDFs.
- `__artifacts/ingestion/kfu_shura/` stores Shura issue metadata, original PDFs, and the language-unlabelled 1910 volume's review evidence.
- `__artifacts/ingestion/tatargalyame/` stores educational resource metadata, category provenance, hosted originals, and deferred external references.
- `__artifacts/ingestion/commons/` stores original documents, source SHA-1 checks, category evidence, and licensing metadata.
- `__artifacts/ingestion/miras/` stores the full Miras catalog and PDFs; `pilot/` retains the original access experiment separately.
- `tatkniga/workdir/` and `paid_files.csv` retain historical data; they are not imported automatically.

See folder READMEs for pipeline-specific behavior, options, and caveats.
