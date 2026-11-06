# Tatkniga public library

Tatkniga traverses only the current public library, using native `PAGEN_1`
pagination and its advertised last page. It excludes shop menus, recommendations,
filters, and “show all” links. A changed page count restarts the next scan while
retaining committed records. Empty/incomplete pages, repeated batches, invalid
pagination, and failed record inspections keep discovery incomplete. No exact
site-wide record count is advertised; completion describes the linked listing
traversal, not every potentially available historical file or a fixed catalog
snapshot. The catalog's required trailing slash is preserved.

Publication IDs come from the current primary product wrapper. File-path IDs are
separate references. Metadata retains supplied titles, authors, descriptions,
bibliographic property names/values, and language labels. An explicit recognized
Tatar language label (including `тат`) selects an edition; bilingual labels must
explicitly include Tatar. Titles and descriptions are not used to infer language,
and Crimean Tatar is not treated as Tatar. Missing language labels hold direct
files for review; public FlipHTML5 readers may be acquired without a language
label. Unrecognized labels remain held for review for both acquisition methods.
No empty or inferred language claim is synthesized. Reader eligibility is recorded
separately as `reader_language_selection`; the original `language_selection` stays
unchanged.

Directly linked supported documents and recognized FlipHTML5 readers under
`/upload/interactive_books/` on the Tatkniga origin are eligible. Discovery follows
the reader's linked `javascript/config.js`, parses its explicit `fliphtml5_pages`
JSON list without executing JavaScript, and verifies the count against
`totalPageCount`. Recognized PageSpeed script/bundle URLs are resolved to the
original configuration source they name. Display captions and bibliographic page
counts do not define the image sequence. Listed large JPEGs are preferred, with
listed normal JPEGs used when a large image is not declared. Thumbnails and guessed
URLs are not used.
Reader/configuration URLs and raw configuration remain in metadata.

Repeated links collapse to one reader. Multiple distinct supported reader links
require review. An eligible direct PDF takes precedence over reader assembly.
Other readers, audio, archive expansion, and external-host documents remain
deferred or unsupported. `status` and run summaries include optional
`unsupported_reasons` counts: `reader_deferred`, `reader_unsupported`,
`reader_ambiguous`, `reader_superseded`, `language_unknown`, `language_excluded`,
`external_origin`, and `format_unsupported`. Failed reader/configuration requests
or inconsistent declared page lists leave discovery incomplete and retryable.

## Unified CLI stages

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source tatkniga --max-pages 2
.venv/bin/python cli.py --config ingestion.yaml download --source tatkniga --limit 1
.venv/bin/python cli.py --config ingestion.yaml finalize --source tatkniga --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source tatkniga --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source tatkniga
```

Use `sources.tatkniga` from `ingestion.example.yaml` in your selected operational
YAML. Add global `--summary-only` for compact JSON.

`download` acquires direct documents and ordered reader JPEGs without assembling
PDFs. Its `--limit` and `max_items` count a direct file or a whole reader book;
direct files are processed first. Interrupted books resume from verified images.
`--recheck` revalidates images; a failed recheck leaves the book incomplete while
preserving historical files.

`finalize` operates entirely offline. It requires all current ordered pages with
verified hashes and valid image content. Missing or damaged images require
`download` first. PDFs are published atomically under
`__artifacts/ingestion/tatkniga/derived/<sha256>.pdf`, after page-count validation.
Unchanged verified PDFs are reused; missing or damaged PDFs are rebuilt.
Standalone `finalize --limit N` processes up to N books needing assembly or repair;
unchanged verified outputs do not consume that limit.

`run` composes discovery, acquisition, and finalization for its selected reader
batch. Completed selected books can finalize after an acquisition item or byte
cap, subject to the shared deadline. Older downloaded backlog is processed with
standalone `finalize`. Other stage capabilities are unsupported.

Original JPEGs remain in `files/`. PDFs include covers and blank pages in reader
order, preserving image quality, proportions, and orientation. They contain no
OCR, interactive media, or exercises. Results retain input IDs and hashes,
assembler version, source observation, size, and page count. `status` reads the
manifest without auditing files, making requests, or writing artifacts; it reports
`pdf_books` and `image_pages` counts.

Existing shared manifests and PDFs remain compatible. Parser version 2 restarts
discovery to refresh older reader descriptors while retaining observations and
downloads; run `discover` after upgrading from an older parser.

The obsolete Selenium implementation and its unused top-level configuration and
historical crawler lists have been removed. They are not imported by this adapter.
All active source code lives under `ingestion/`, and current state stays under
`__artifacts/ingestion/tatkniga/`. No cloud services or credentials are used.

## Stage migration verification

Manual checks used `/tmp/tatkniga-stage-verification/operational.yaml` and an
isolated two-book manifest with synthetic JPEG inputs. Local-only download
started one book at the item cap and created no PDFs. Finalization created one
PDF at the cap, then completed the backlog; a third invocation reused both.
Every finalization reported zero requests. A damaged PDF was rebuilt, and a
missing image produced a structured error requesting another download.
Explicit selected-record finalization completed only the selected book.
The shared helper's default combined mode still assembled the remaining book
and reused the complete book without network requests. Root CLI status reported
book/page counts and review was rejected as unsupported. Compilation and
`git diff --check` passed. No automated tests were added. Live catalog traversal,
network acquisition, and a complete end-to-end `run` were not exercised in this
verification; existing active artifacts were left untouched.
