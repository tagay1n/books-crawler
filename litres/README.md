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
- `python litres/cli.py s3-media`
  - Upload markdown `media/` images to S3-compatible storage and export markdown with public image URLs to `__artifacts/litres/markdown-s3/`.

## Requirements

- Chrome/Chromium available for Selenium.
- Working network access to Litres endpoints.

## Config

File: `litres/config.yaml`

Used keys:
- `sid` (required)
- `yandex.oauth_token` (for upload step)
- `s3.endpoint_url`
- `s3.aws_access_key_id`
- `s3.aws_secret_access_key`
- `s3.bucket`
- `pdf.jpeg_quality` (optional, default `85`)
- `pdf.max_width` (optional, default `1600`; set `null` to keep raw width)
- `pdf.dpi` (optional, default `150`)
- `pdf.browser_headless` (optional, default `true`; set `false` to solve Litres browser challenges manually)
- `pdf.browser_challenge_wait_seconds` (optional, default `180`)

## Artifacts

- Index: `__artifacts/litres/books-index.json`
- PDFs: `__artifacts/litres/docs/`
- Text output: `__artifacts/litres/markdown/`
- Intermediate images: `__artifacts/litres/images/`
