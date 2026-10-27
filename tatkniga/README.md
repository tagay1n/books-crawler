# Tatkniga

Tatkniga now runs through the shared local-ingestion CLI. The obsolete Selenium
crawler scripts have been retired.

```bash
python cli.py --config ingestion.yaml discover --source tatkniga --max-pages 2
python cli.py --config ingestion.yaml download --source tatkniga --limit 1
python cli.py --config ingestion.yaml run --source tatkniga
python cli.py --config ingestion.yaml status --source tatkniga
```

Use the `sources.tatkniga` entry from `ingestion.example.yaml`. The adapter follows
`https://tatkniga.ru/catalog/biblioteka/` and downloads directly linked supported
document files for explicitly Tatar-labelled or Tatar-containing bilingual editions.
It also downloads the ordered JPEG pages of public FlipHTML5 readers and assembles
one image PDF per book, including covers and blank pages. An eligible direct PDF
is preferred when available. Reader books with missing language labels are allowed
without making a language claim; explicit non-Tatar languages are excluded, and
unrecognized labels remain held for review. Direct-file language rules are unchanged.
Other reader formats remain visible as deferred or unsupported. All files stay local.

Run `discover` once after upgrading to resolve readers already in your manifest.
Then use the existing `download` or `run` command. For Tatkniga, `--limit 1` counts
one direct document or one entire reader book. Direct files are processed first.
Interrupted books resume from verified images; a PDF is published only after all
expected pages are acquired and validated. `--recheck` revalidates source images.

Original JPEGs remain in `__artifacts/ingestion/tatkniga/files/`; assembled PDFs
are in `__artifacts/ingestion/tatkniga/derived/<sha256>.pdf`. The manifest retains
page order, reader configuration, image hashes, and PDF provenance. `status`
reports `pdf_books` completion counts and `image_pages` progress. PDFs preserve
the source image quality and have no OCR; audio, video, and exercises are omitted.


See [local ingestion](../docs/local-ingestion.md) for budgets, recovery, metadata,
and language-selection behavior.

## Preserved historical data

The following remain unchanged as historical evidence:

- `workdir/books_pages.txt` and `workdir/books_metas.json`
- `workdir/visited_pages.txt` and `workdir/visited_book_pages.txt`
- `workdir/downloaded_files.txt`
- `paid_files.csv`
- `config.yaml` (legacy configuration; unused by the shared CLI)

The new adapter does not import or revisit these lists. It discovers today's
catalog afresh under `__artifacts/ingestion/tatkniga/`. A historical downloaded
marker does not prove that a complete local file is available. Historical
`/books/<id>` page URLs, reader links, and direct-file URLs may have different
availability and are not automatically mapped to current product identities.

The retired implementation depended on obsolete page selectors, broken `src`
imports and config paths, and upload integrations. None of those integrations
or their import-time credential checks are used by the shared CLI.
