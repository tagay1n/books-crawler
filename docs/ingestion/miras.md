# Miras books and browser-session access

Miras is a full shared-CLI adapter for the unfiltered **books** catalog. All
languages are eligible, including editions with missing or unrecognized language
labels. Manuscripts, periodicals, other project categories, alphabetical filters,
and search forms are not traversed. Add `sources.miras.archive_url` from the
example to your operational YAML. Both trailing-slash variants are accepted.

Supply a Miras-only session export from your ordinary, manually verified browser
to each network command:

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source miras --max-pages 2 \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
.venv/bin/python cli.py --config ingestion.yaml download --source miras --limit 2 \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
.venv/bin/python cli.py --config ingestion.yaml run --source miras --max-pages 2 --limit 2 \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
.venv/bin/python cli.py --config ingestion.yaml status --source miras

# Retained diagnostic: inspect the catalog and download one fixed sample.
.venv/bin/python cli.py --config ingestion.yaml probe --source miras \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
```

Discovery follows native `/books/page/N/` links in sequence. The numbered links
are a moving window, so their highest visible number is not a catalog total or
last-page guarantee. The adapter follows the linked next page until forward
pagination ends. Missing pagination, empty/incomplete pages, wrong active pages,
and repeated batches leave discovery incomplete. Completion describes the linked
catalog traversal; no exact site-wide count is advertised.

Books use their native numeric record ID (`book:<id>`), preserving renamed URL
relationships. Thumbnail/title links collapse to one entry. Supplied titles in
both scripts, authors, bibliography, page descriptions, publication year, and
other recognized properties are preserved. Listing-only language, publication
place, and subject information remains in `catalog_context`. The website's
general document title is not used as the book title; the catalog label supplies
a title when the detail page has no recognizable heading. No language is inferred.

PDFs are extracted from the primary book content's direct links and reader
`viewer.html?file=...` references. Repeated URLs collapse to one descriptor; all
distinct exposed PDF parts are eligible. External documents and unsupported
formats remain visible with reasons, and metadata-only records are retained.
The shared downloader verifies file signatures, lengths, hashes, budgets, and
atomic publication; PyMuPDF verifies a nonempty readable PDF and records the actual
PDF page count. A bibliographic page count is a source claim and need not equal
the PDF page count. Original files are preserved without conversion or OCR.

Full ingestion uses `__artifacts/ingestion/miras/manifest.json`, `files/`, and
`summaries/`. The existing `pilot/` directory is preserved separately and is not
automatically imported. `--limit` counts individual PDFs, including separate parts
of a book. Incomplete scans and transfers resume using the same shared checkpoints
and verified-local-file behavior as the other adapters.

The existing session export format remains compatible. Commands use its cookies
and actual browser user agent with the shared HTTP downloader, without launching
or controlling a browser. Cookie values and the exported user agent are not
written to manifests, summaries, or logs. Session JSON is sensitive: keep it
private and out of Git. `miras-session.json` is explicitly ignored by the repository.

Recognized access rejections (including HTTP 468) and challenge HTML stop a full
ingestion run promptly with an `access` error and a nonzero CLI exit status. The
remaining queue and previous successful downloads are retained. Ordinary missing
records or invalid PDFs remain individually retryable. A challenge or HTML page
cannot be published as a successful PDF.

When access expires, verify Miras again in your normal browser and refresh the
export. A cookie-export tool can supply browser cookie fields; wrap the
Miras-only cookies and current browser user agent in this format:

```json
{
  "format": "miras-session-v1",
  "origin": "https://miras.info",
  "user_agent": "YOUR_ACTUAL_BROWSER_USER_AGENT",
  "cookies": [
    {
      "domain": "miras.info",
      "name": "EXPORTED_COOKIE_NAME",
      "value": "EXPORTED_COOKIE_VALUE",
      "path": "/",
      "secure": true
    }
  ]
}
```

Preserve cookie domains and paths exactly. `expirationDate` is optional and uses
Unix seconds; expired cookies are skipped. Domains outside `miras.info` and
`.miras.info` are rejected. Do not include cookies from other websites.

The pilot reads one catalog page and the sample «Авыл кызы» record, extracts the
current PDF URL from its reader, and acquires one PDF. Shared pacing, retries,
timeouts, byte/file-size limits, disk reserve, hashes, format checks, and atomic
publication apply. PyMuPDF also verifies that the PDF opens. Files, a manifest,
and diagnostic reports remain under `__artifacts/ingestion/miras/pilot/`.
Successful sample history is retained if a later access attempt fails.
Earlier pilot check on 2026-10-27: exported cookies enabled HTTP access to the catalog,
sample record, and its 5,486,334-byte, 64-page PDF without retries. This verifies
that session and sample, not full catalog coverage or future session lifetime.
The later full-adapter access check rejected the saved session and stopped after
one request with its initial catalog checkpoint retained. A successful two-page,
two-language live check requires renewed browser verification and a refreshed
session export.

## Remembered fallback: ordinary-browser extension

If cookie-based HTTP access becomes insufficient, reconsider a small extension
that reads Miras pages and downloads PDFs inside a normal verified browser,
without a debugging connection. The experiment on 2026-10-27 downloaded a PDF
with the same SHA-256 as the HTTP copy. Its implementation and sample-import CLI
have been removed; this is a fallback idea only. The earlier Playwright approach
was rejected by SafeLine WAF with “Debugging Detected” and has also been removed.
