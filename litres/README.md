# Litres

Litres crawler for index build, PDF/text downloads, metadata enrichment, and uploads.

## Commands

- `python litres/cli.py index`
  - Build/update `__artifacts/litres/books-index.json`.
- `python litres/cli.py discover`
  - Discover likely Tatar books from broad Litres searches and write reviewable candidates to `__artifacts/litres/candidates-index.json`.
  - Search pages are filtered to subscription books with Litres `art_types=text_book` and non-Tatar language tags `ru`, `en`, and `ba`.
- `python litres/cli.py export-candidates-review`
  - Export candidates to `__artifacts/litres/candidates-review.tsv` for manual review.
- `python litres/cli.py sync-candidates-review`
  - Sync edited TSV statuses back into `candidates-index.json`.
- `python litres/cli.py import-candidates`
  - Import only `accepted` candidates into `books-index.json`.
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
- `python litres/cli.py s3-media`
  - Upload markdown `media/` images to S3-compatible storage and export markdown with public image URLs to `__artifacts/litres/markdown-s3/`.

## Requirements

- Chrome/Chromium available for Selenium.
- Working network access to Litres endpoints.

## Config

File: `litres/config.yaml`

Required keys:
- `sid` (required)
- `yandex.oauth_token` (for upload step)
- `s3.endpoint_url`
- `s3.aws_access_key_id`
- `s3.aws_secret_access_key`
- `s3.bucket`
- `pdf.jpeg_quality`
- `pdf.max_width` (set `null` to keep raw width)
- `pdf.dpi`
- `pdf.lossless_first_pages` (keep the first N pages as lossless PNG in the final PDF)
- `pdf.browser_headless` (set `false` to solve Litres browser challenges manually)
- `pdf.browser_challenge_wait_seconds`
- `discover.search_queries`
- `discover.max_pages_per_query` (values above `20` are capped to `20`)
- `discover.min_score`
- `discover.search_request_retries`
- `discover.browser_headless`

The CLI fails fast when required config values are missing instead of applying code defaults.

## Artifacts

- Index: `__artifacts/litres/books-index.json`
- Discovery candidates: `__artifacts/litres/candidates-index.json`
- Discovery review table: `__artifacts/litres/candidates-review.tsv`
- PDFs: `__artifacts/litres/docs/`
- Text output: `__artifacts/litres/markdown/`
- Intermediate images: `__artifacts/litres/images/`
