# Internet Archive originals

Configure `sources.internet_archive.archive_url: https://archive.org` in the
operational YAML. No login, borrowing credentials, or new dependencies are needed.

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source internet_archive --max-pages 2
.venv/bin/python cli.py --config ingestion.yaml download --source internet_archive --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source internet_archive --max-pages 2 --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source internet_archive
.venv/bin/python cli.py --config ingestion.yaml download --source internet_archive --recheck --limit 1
```

The fixed query is `mediatype:texts AND (language:tat OR language:tt OR language:tatar)`.
Advanced Search requests 100 identifiers per listing page, sorted by identifier
ascending; each item's metadata is fetched independently through the metadata API.
Listing offsets, batch sizes, duplicate identifiers, and totals are validated.
After the last page, an additional listing request verifies the total against the
unique enumerated items. It consumes the page budget too. Ordinary numbered
pagination is used because live GET and POST cursor-continuation checks on the
scrape API returned `Bad cursor` for the supplied cursor.

An incomplete discovery resumes pending metadata requests and the listing
frontier. Changed totals or duplicate identities require a fresh scan while
retaining metadata and acquired files. Failed/refused pages remain unresolved;
the adapter does not silently switch queries or skip search-window errors.
Completion describes a traversal of the current search index, not a transactional
snapshot. Subsequent scans start fresh, and partial scans never establish removal.
The existing deadline, pacing, retries, and 2 MiB metadata-response cap apply.

Current item metadata must contain an exact, case-insensitive `tat`, `tt`, or
`Tatar` language label. Multilingual items with an explicit Tatar label qualify.
Missing or malformed labels hold document assets as `language_unknown`; other
labels hold them as `language_excluded`. Crimean Tatar alone does not qualify.
Titles, descriptions, and interface language are not substitutes for these labels.
Language claims are preserved as supplied; no content-language detection runs.

An item identifier is the source record identity; the exact native filename is
the asset identity. Item metadata, the complete supplied file inventory, and
per-file selection reasons remain inspectable. Only supported document files
marked `source=original` are eligible. Derivatives, archives/page packages, images,
HTML, and metadata files remain inventory evidence; private or restricted
document assets are held with explicit reasons. An Archive original upload does
not establish that it is an authentic or complete historical original.

Downloads use canonical `/download/<identifier>/<filename>` URLs, including
correctly encoded Unicode and nested filenames. HTTPS storage-host redirects
must remain under Archive-owned hosts and preserve the exact item and filename
on every hop. Storage-host URLs are response evidence, not durable source locators.
Other adapters retain their existing origin restrictions.

Files are stored unchanged under `__artifacts/ingestion/internet_archive/files/`.
Transfers compute SHA-256 and MD5 and check supplied file size and MD5 when
present before publishing success. Invalid supplied integrity metadata remains
unresolved; mismatches fail acquisition. SHA-256 is still computed when no
upstream MD5 is available. Basic format checks do not assess document quality.
File MD5, size, and modification hints form a source-version fingerprint.
Changed hints trigger acquisition under the same asset identity without stale
conditional headers; earlier results remain retained. Metadata-only changes
leave verified downloads reusable. Byte-identical rechecks update the asset's
verified version without rewriting its original acquisition evidence.

The 2026-10-27 live check inspected 200 items over two listing pages with no
errors or retries and retained 414 eligible original document assets plus three
metadata-only records. The search advertised 5,295 items. The configured page cap
left the overall scan incomplete, with page 3 checkpointed for continuation;
the 414 normal-queue assets remain pending rather than being bulk downloaded.
An isolated pilot under `internet_archive/pilot/` acquired the original
Шиһабетдин Мәрҗани PDF (2,306,792 bytes). Its computed MD5 matched Archive's
`3e07e2a6a70bb4bbfaa4411117f4ce1b`; SHA-256 was
`529b80a546d2c42fea725e9cf818858e21969604382c2b86866b51f3fa55070a`.
The pilot verified the observation link and repeated the CLI download with one
skip and zero network requests. This sample establishes transfer/integrity
behavior, not complete corpus coverage or verified content language.
