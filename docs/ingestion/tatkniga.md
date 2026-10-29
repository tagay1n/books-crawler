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

For Tatkniga, `--limit` and `max_items` count either a direct file or a whole reader
book. Direct files are processed first, with the remaining item budget shared by
reader books. Verified JPEGs are retained in `files/` and assembled in reader
order, including covers and blank pages. Assembled PDFs are published atomically
to `__artifacts/ingestion/tatkniga/derived/<sha256>.pdf` only after all expected
pages are available and the PDF page count is verified. These are image PDFs
without OCR; interactive media and exercises are not included. Image quality,
proportions, and orientation are preserved.

Interrupted books resume from verified images. Missing, damaged, or outdated PDFs
are rebuilt; unchanged complete books require no network requests. `--recheck`
revalidates images and retains old PDF versions when inputs change. A failed
recheck leaves the book incomplete while preserving historical files. PDF results
record ordered input IDs and hashes, assembler version, source observation, size,
and page count. Status adds `pdf_books` completion counts and `image_pages`
progress; it reads the manifest rather than auditing local file integrity.
Parser version 2 restarts discovery to refresh old reader descriptors while
preserving observations and downloads; run `discover` after upgrading.

Tatkniga uses `__artifacts/ingestion/tatkniga/` with the shared manifest and
downloader. The old Selenium scripts have been retired; `tatkniga/workdir/`,
`paid_files.csv`, and the old configuration are preserved as historical data.
They are not read or migrated by the new adapter, and old download markers are
not evidence that verified local bytes exist. No cloud services or credentials
are used. See [the historical-data notes](../../tatkniga/README.md).
