# Litres pipeline

This folder contains the Litres crawler and download tools. It builds a local index, then
downloads PDF or text books using Selenium (with selenium-wire).

## Commands
- `python litres/cli.py index` - build or update `__artifacts/litres/books-index.json`.
- `python litres/cli.py pdf` - download PDF books and assemble PDFs from page images.
- `python litres/cli.py text` - download text books and save markdown + media assets.
- `python litres/cli.py metadata` - scrape extra metadata into the index.
- `python litres/cli.py upload` - upload PDFs to Yandex Disk and record links.
- `python litres/cli.py hf` - upload markdown and images to Hugging Face.

## Config
`litres/config.yaml` is required. It typically includes:
- `app-id` (Litres app id for auth)
- `sid` (optional; if absent a new SID is requested)
- `yandex.oauth_token` (for upload)

## Artifacts
- Index: `__artifacts/litres/books-index.json`
- PDF images: `__artifacts/litres/images/<file_id>/`
- PDFs: `__artifacts/litres/docs/`
- Text markdown: `__artifacts/litres/markdown/<book_name>/`
