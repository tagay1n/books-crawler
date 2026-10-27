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
Interactive readers remain deferred. Missing language labels are held for review;
other languages remain visible with an exclusion reason. All files stay local.

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
