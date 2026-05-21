# Litres

Litres crawler for index build, PDF/text downloads, metadata enrichment, and uploads.

## Commands

- `python litres/cli.py index`
  - Build/update `__artifacts/litres/books-index.json`.
- `python litres/cli.py pdf`
  - Download PDF books and assemble final PDFs.
- `python litres/cli.py text`
  - Download text books and write markdown/assets.
- `python litres/cli.py metadata`
  - Scrape additional metadata into index records.
- `python litres/cli.py upload`
  - Upload PDFs to Yandex Disk and write document metadata via `monocorpus_models`.
- `python litres/cli.py hf`
  - Upload markdown folder to Hugging Face dataset.

## Requirements

- Chrome/Chromium available for Selenium.
- Working network access to Litres endpoints.

## Config

File: `litres/config.yaml`

Used keys:
- `sid` (required)
- `yandex.oauth_token` (for upload step)

## Artifacts

- Index: `__artifacts/litres/books-index.json`
- PDFs: `__artifacts/litres/docs/`
- Text output: `__artifacts/litres/markdown/`
- Intermediate images: `__artifacts/litres/images/`
