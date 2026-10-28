# Local document ingestion

The shared `cli.py` implements these acquisition sources:

- `magarif`: <https://magarif-uku.ru/documents>, collecting archive attachments.
- `magarif_vakyt`: <https://magarif-vakyt.ru/online2>, retaining publisher-linked
  Tatar textbook ZIPs and assembling PDFs from their explicit reader page lists.
- `beznenmiras`: <https://beznenmiras.ru/categories/widget/list/svezii-vypusk>,
  discovering issue metadata and linked original documents; cover images are skipped.
- `tatarica`: <https://tatarica.org/tat/razdely/tatarika-kitaphanse>, collecting
  document editions linked from the library catalog's books and journal articles.
- `darul_kutub`: <https://darul-kutub.com/search>, collecting originals for books
  and journal issues across all languages in the public search catalog.
- `kazanutlary`: <https://kazanutlary.ru/j-archive>, collecting scanned issue
  images and assembling complete PDFs locally with PyMuPDF.
- `tatkniga`: <https://tatkniga.ru/catalog/biblioteka/>, collecting directly
  linked files with explicit Tatar or Tatar-containing bilingual language labels,
  plus supported public flipbook pages assembled into local PDFs.
- `miras`: <https://miras.info/projects/mirasxane/books/>, collecting exposed
  original book PDFs across all languages using an exported browser session.
- `miras_periodicals`: <https://miras.info/projects/mirasxane/periodicals/>,
  periodical-series discovery and explicitly exposed PDFs with Tatar source claims;
  live reader verification is pending a refreshed session.
- `commons`: <https://commons.wikimedia.org/wiki/Category:Tatar-language_books>,
  discovering document-format books through the public metadata API and acquiring
  their checksum-verified original uploads.
- `isxaki`: <https://isxaki.com/ijat/>, collecting linked document files from
  original editions, three works periods, and books about Iskhaki.
- `turuz`: <https://turuz.com/index/pitik/category/2>, collecting direct Tatar-labelled
  dictionary PDFs, DjVu and Word originals from the native dictionary listing.
- `yazuchy`: <https://sptatar.com/yazuchy-n-shriyaty/>, collecting publisher book
  PDFs with explicit Tatar target-language claims or individually reviewed hashes.
- `internet_archive`: <https://archive.org>, collecting public original document
  uploads from text items explicitly labelled as Tatar.
- `tataroved`: <https://tataroved.ru/publication/>, collecting linked originals
  with bibliographic Tatar-language claims or individual reviewed-file evidence.
- `kfu_dspace`: <https://dspace.kpfu.ru/xmlui/discover>, discovering native Tatar
  topic results and acquiring public PDFs with explicit language or reviewed-file evidence.
- `kfu_repository`: <https://repo.kpfu.ru/jspui/community-list>, discovering all
  historical repository collections with explicit Tatar item-language admission.
- `kfu_vakyt`: <https://repo.kpfu.ru/jspui/handle/net/86/simple-search>, collecting
  exact-series Vakyt results with explicit Tatar item-language admission.
- `kfu_books`: <https://repo.kpfu.ru/jspui/handle/net/27574>, collecting public
  direct document files and supported JPEG readers from the Turkic–Tatar books collection.
- `kfu_manuscripts`: <https://repo.kpfu.ru/jspui/handle/net/18503>, collecting public
  direct document files and supported JPEG readers from the Turkic–Tatar manuscript collection.
- `kfu_il`: <https://repo.kpfu.ru/jspui/handle/net/28060>, collecting public
  «Ил» newspaper issue files with explicit Tatar source language labels.
- `kfu_azad_halyk`: <https://repo.kpfu.ru/jspui/handle/net/27528>, collecting public
  «Азад халык» newspaper issue files with explicit Tatar source language labels.
- `kfu_shura`: <https://repo.kpfu.ru/jspui/handle/net/25046>, collecting public
  «Шура» journal issue files with explicit Tatar source language labels.
- `tatargalyame`: <https://tatargalyame.kpfu.ru/catalogue>, collecting explicitly
  listed hosted educational documents across all languages.

All sources use the same local downloader and manifest implementation. Each
adapter follows its selected catalog. Existing legacy collectors remain independent.

### Yazuchy publisher catalog

Add this entry under `sources` in your operational YAML:

```yaml
yazuchy:
  archive_url: https://sptatar.com/yazuchy-n-shriyaty/
```

```bash
python cli.py --config ingestion.yaml discover --source yazuchy --max-pages 1
python cli.py --config ingestion.yaml download --source yazuchy --limit 1
python cli.py --config ingestion.yaml status --source yazuchy
```

The initial slice follows book-card links on this publisher page, not the whole
Writers' Union website. Each native detail URL becomes a separate book record.
Observations preserve title, full annotation/bibliography, raw PDF links, listing
context and language evidence. Only direct same-origin HTTPS PDFs inside the
book article are candidates; covers, sidebars, policy documents and reader
assembly are outside the slice. Unexpected catalog pagination holds discovery
for review. Current totals are observed catalog entries, not site-wide holdings.

The catalog mixes Tatar originals, translations into Tatar and Russian editions
of Tatar works. A Tatar interface, title or author does not admit a PDF. Explicit
`татар теленә тәрҗемә` target-language evidence admits a file; missing claims and
Russian target-language claims hold acquisition unless an individual file review
identifies Tatar content. Raw translation descriptions remain in metadata.

The checked-in `ingestion/yazuchy-language-reviews.json` records nine individually
sampled Tatar PDFs with SHA-256, observed byte/page counts, sampled page numbers
and reviewer/reason. For review-based admission, the acquired SHA-256 must match
before publication. Changed bytes stay failed for a new review. The review
identifies Tatar content in sampled pages; it does not certify monolinguality or
edition completeness. Several PDF page counts differ from catalog print-page
claims, which remain separately preserved in raw bibliography.

Optional `<artifacts_root>/yazuchy/language-reviews.json` uses the same version-1
`files` mapping as the checked-in file and overrides matching built-in reviews.
Each entry requires a hosted PDF URL, `sha256`, `languages` including `tt`,
`reviewer` and `reason`; do not grant a review from a filename or annotation alone.
The adapter refreshes review decisions before downloading, without a catalog
rescan. Removing a local override falls back to the checked-in review, rather
than withdrawing it. A built-in review must be removed from the checked-in file
to withdraw it. Discovery still determines which files are current candidates.

Originals use the shared bounded downloader and immutable SHA-256 file paths in
`<artifacts_root>/yazuchy/files/`, with manifest observations and acquisition
results. No conversion, account, media API or package handling is needed.
Byte/time/disk limits, signature checks, retry behavior and verified-local-file
reuse are shared with other adapters. `--recheck` revalidates completed files.

During implementation, nine PDFs completed bounded manual inspection under
`/tmp/yazuchy-review/`. The likely Tatar translation of `1993` exceeded the 25 MiB
inspection cap; its file language remains unverified and acquisition stays held.
Four Russian editions were not downloaded for language review. Review artifacts
are distinct from CLI acquisition evidence under `/tmp/yazuchy-verification/`.

Live CLI verification on 2026-10-28 inspected all 14 detail records in 15 HTTP
requests, without errors: nine eligible PDFs and five held files (three explicit
Russian-language exclusions and two without an admitted language claim/review).
The CLI saved the complete `Шамил Гәрәй` PDF: 20,638,673 bytes, 70 PDF pages,
SHA-256 `079f0cc30d6e8ac117d97b9b103fa2fd8d4249bb359a074e04e900f74fec0a89`.
Its result records the matching reviewed SHA-256. An isolated single-asset replay
under `/tmp/yazuchy-replay/` skipped the verified original with zero requests.
The other eight admitted files have manual byte/language inspections, but were
not all reacquired through the CLI.

### Turuz dictionaries

Add this entry under `sources` in your selected operational YAML:

```yaml
turuz:
  archive_url: https://turuz.com/index/pitik/category/2
```

```bash
python cli.py --config ingestion.yaml discover --source turuz --max-pages 1
python cli.py --config ingestion.yaml download --source turuz --limit 1
python cli.py --config ingestion.yaml status --source turuz
```

This initial slice covers the single native dictionary-category table, not the
whole Turuz library. One collection record retains individual dictionary cards,
raw row numbers, titles, formats, displayed sizes, links and selection decisions.
The manifest's record count is therefore a collection count, not a book count.
Discovery inspects the listing twice (enumeration and metadata observation).
Displayed row numbers are provenance, not permanent book identifiers; asset URLs
identify files, and duplicate selected file URLs share one acquisition entry.

Selection requires a dictionary title beginning with `Tatar`, `Tatarca` or
`Lehceyi Tatari`, allowing accents, spaces, hyphens and underscores. Explicit
Crimean Tatar titles and general multilingual titles are excluded. Tatar–English
and Tatar–Turkish dictionaries are included. These are catalog language
claims, not verified monolingual Tatar content. Every keyword-matching row,
including exclusions, remains in collection metadata for review. Unlabelled
works and Tatar titles elsewhere on the site are outside this slice.

Only same-origin HTTPS `/storage/` PDF, DjVu and Word files are acquired.
RAR/archive links remain unsupported in the manifest; no package expansion,
executable content, reader conversion, account or external delivery is used.
Source checksums are not supplied by this listing: the shared downloader checks
transport length when available, file signatures, local SHA-256/MD5, configured
byte/time/disk limits and atomic publication. These checks do not establish
completeness against a printed edition. Originals are retained unchanged under
`<artifacts_root>/turuz/files/`, alongside `manifest.json` and metadata observations.
Ordinary repeated downloads skip verified local files; missing/corrupt files are
eligible again. `--recheck` requests source revalidation. Run discovery again to
refresh the collection observation and mark removed links inactive.

Pre-implementation access checks downloaded two complete PDFs: the Tatar–English
dictionary (9,929,569 bytes, 103 PDF pages) and Tatar–Turkish dictionary (624,650
bytes, 178 pages). The first record claims 200 pages; preserve that claim separately
from observed PDF pages. Its scan has noisy OCR; the smaller Latin-script
dictionary exposes readable bilingual text. This is not an assessment of every
file's extraction quality, edition completeness, reuse rights or unique coverage.

Manual adapter verification on 2026-10-28 completed discovery in two requests:
18 keyword rows, 13 selected file URLs, 11 eligible originals and two unsupported
RAR links. Five rows were excluded (including duplicated general multilingual
links and explicit Crimean Tatar titles). In an isolated single-asset copy of the
live manifest, CLI acquisition saved the complete 624,650-byte / 178-page
Tatar–Turkish PDF with SHA-256
`7c272fcff13f159342972e8d6d6aff3db96deece71e21d24eb0b8f1565d5a9a3`,
matching the earlier independent sample. A repeated CLI download skipped it with
zero network requests. Evidence is under `/tmp/turuz-verification/` (full
discovery) and `/tmp/turuz-small-verification/` (isolated PDF acquisition/reuse).
The full-discovery manifest also acquired the first phraseological-dictionary
DjVu unchanged: 24,682,420 bytes, SHA-256
`cdd230c94398d507a2d3637264086048964d91a1505056f23170f60deadb0fbf`.
`djvused` opened it and reported 494 pages. That transfer took approximately
188 seconds; allow sufficient deadline for larger files. Word originals and the
remaining file layouts have not been verified through acquisition.

### Мәгариф–Вакыт textbook packages

The publisher's electronic-format catalog is separate from the `magarif`
magazine archive. Add this entry under `sources` in your operational YAML:

```yaml
magarif_vakyt:
  archive_url: https://magarif-vakyt.ru/online2
```

```bash
python cli.py --config ingestion.yaml discover --source magarif_vakyt --max-pages 1
python cli.py --config ingestion.yaml download --source magarif_vakyt --limit 1
python cli.py --config ingestion.yaml status --source magarif_vakyt
```

Discovery selects public Yandex Disk shares attached to publisher-labelled
«Әдәби уку», «Татар Теле», and «Татар әдәбияты» textbook cards. Arabic textbooks,
Google Drive links, and the publisher's other catalogs are outside this slice.
The titles establish admission context, not verified language of every file.
Each share is one source record, with its publisher title/link and Yandex name,
size, resource ID, timestamps, and checksums retained. `yadi.sk` aliases normalize
to `disk.yandex.ru`. No login, OAuth token, session export, or new dependency is
required. Metadata-only discovery does not download package bytes.

Downloads resolve a fresh temporary delivery URL through Yandex's public API,
verify source size/MD5/SHA-256, and retain the unchanged ZIP under
`<artifacts_root>/magarif_vakyt/files/`. Signed URLs are excluded from persisted
metadata, transfer errors, and acquisition results. A changed upstream identity
requires rediscovery. `--limit` counts started packages, including retries or
local PDF reconstruction; already verified complete packages are skipped.

The package reader parses literal `fliphtml5_pages` arrays and `totalPageCount`
from `javascript/config.js` without executing JavaScript. It reads only explicitly
declared large JPEGs in their supplied order; HTML page counts, thumbnails, audio,
Flash assets, and installation manuals do not determine the page sequence. Each
recognized reader configuration produces a separate PDF under `derived/`, with
original JPEGs embedded without resampling. Page geometry uses an explicit assumed
200 DPI; this is a rendering recipe, not measured scan resolution. PDFs omit
interactive/audio features and are derived representations, not original files.

Each derived result records the source ZIP acquisition and observation, archive
and configuration SHA-256, ordered member names and page hashes, image dimensions,
CRC values, and assembler version. Missing pages, inconsistent counts, corrupt
required members, or unsupported reader configurations fail assembly while retaining
an already verified ZIP. Completion means every declared page in every recognized
reader was assembled; it does not establish completeness against printed editions.
Missing derived PDFs rebuild from the retained ZIP without another download.

Bounds apply to both network acquisition and local processing. The package reader
allows at most 20,000 ZIP entries, 2 GiB declared uncompressed bytes, 20 reader
configurations, and 2,000 total declared pages. Configurations are capped at 1 MiB,
individual page images at 32 MiB and 40 megapixels. Duplicate/unsafe paths,
symlinks, encrypted members, and compression other than stored/deflate are rejected.
Members are read directly from the ZIP; arbitrary paths are not extracted. The
shared deadline, disk reserve, transfer caps, and `max_derived_pdf_bytes` also apply;
declared page bytes plus 1 MiB PDF overhead must fit the derived-PDF cap before
assembly. Failed work remains retryable after configuration or source changes.

The 2026-10-28 catalog has 14 selected packages, ranging from 50,796,553 to
592,563,294 bytes. The example's 100 MiB per-file cap admits only the smallest;
larger files fail before requests/transferred bytes. To acquire them, explicitly
raise `limits.max_file_bytes` in your operational YAML (600 MiB, or `629145600`,
covers the current largest file), with sufficient run-byte, deadline, and disk
budgets. No saved limits are increased automatically.

Manual CLI verification discovered all 14 packages in 15 requests, without errors.
A one-package download verified the 50,796,553-byte original ZIP and generated
a 20,863,967-byte, 114-page PDF. Hashes, archive-parent links, and all 114 image
inputs were checked; rendered first/middle/last pages were visually inspected.
An isolated repeat made zero requests and reused the PDF. Removing that isolated
derived copy rebuilt it from the retained ZIP with zero requests. A real oversized
second-grade package failed before any network request. The remaining 13 packages
were discovered but not downloaded or layout-validated. Verification artifacts
are under `/tmp/magarif-vakyt-verification/`; separate reuse/recovery and oversized
checks are under `/tmp/magarif-vakyt-replay/` and `/tmp/magarif-vakyt-oversized/`.
No automated tests were created or run.

### Безнең мирас issue archive

Add the following entry to the selected operational YAML under `sources`:

```yaml
beznenmiras:
  archive_url: https://beznenmiras.ru/categories/widget/list/svezii-vypusk
```

```bash
python cli.py --config ingestion.yaml discover --source beznenmiras --max-pages 1
python cli.py --config ingestion.yaml download --source beznenmiras --limit 1
python cli.py --config ingestion.yaml status --source beznenmiras
```

Discovery follows the native «Саннар» issue archive and its forward pagination.
The page cap applies to listings; linked issue records are inspected before moving
to the next listing. Interrupted scans resume from the local manifest. Source
identity uses the issue URL slug, including the observed `7-2025` spelling;
titles are not identity keys. Metadata retains issue number/year claims, displayed
date, description, cover URL, catalog context, and document links. These claims
do not establish document language or completeness. This source is distinct from
Miras (`miras.info`) and Безнең гәҗит (`beznen.ru`).

Only supported original document links inside `.single__content` become assets.
Footer policy PDFs, cover images, and article/navigation links are excluded.
External document links remain inspectable as unsupported; requests and redirects
stay on the configured HTTPS origin. Same-origin originals use the shared bounded
downloader, SHA-256/MD5, immutable local files, and recheck behavior. No page images
are assembled and no PDF is generated from HTML.

Issues without document links remain metadata-only records with an explicit
`acquisition_note`; `status` counts them as `records_without_attachments`.
An empty download queue does not mean complete journal issues were acquired.
Artifacts live under `<artifacts_root>/beznenmiras/`. The initial live inspection
on 2026-10-28 found 41 issue cards across three listing pages, from April 2023
through October 2026, with gaps. Sample issue pages exposed cover/issue metadata
but no document links. The archive supplies no independent total count; do not
infer complete publication coverage from traversal completion.

Manual CLI verification completed all 41 issue records in 44 HTTP requests,
split across two invocations to verify page-cap recovery (one listing followed
by two). Both invocations finished without errors. Every inspected issue had zero
document attachments; the download phase made zero requests and acquired no files.
This verifies metadata discovery and resume behavior, not original-file acquisition.
The isolated verification manifest and summaries are under
`/tmp/beznenmiras-verification/beznenmiras/`.

### Isxaki books and works

Add `sources.isxaki.archive_url: https://isxaki.com/ijat/` to the operational YAML,
or copy the entry from the example configuration. No credentials are required.

```bash
python cli.py --config ingestion.yaml discover --source isxaki
python cli.py --config ingestion.yaml download --source isxaki --limit 1
python cli.py --config ingestion.yaml run --source isxaki --limit 1
python cli.py --config ingestion.yaml status --source isxaki
```

Discovery covers these five collections: `/ijat/kitaplar/` (original editions),
`/ijat/asarlar/` (1896–1907), `/asarlar-1908-1918-ellar/` (1908–1918),
`/1919-1947/`, and `/ijat/about/kitaplar/` (books about Iskhaki).
The entry point and five collection listing requests consume six discovery pages;
each collection is also inspected as a record through the shared discovery core.
A lower page cap resumes the saved frontier on the next invocation.

Each collection is one source record. Its metadata retains the book cards,
supplied bibliographic descriptions, cards without attachments, and source notes.
Document links within cards become assets; repeated links within a collection
share an asset, while overlapping collections retain separate provenance.
HTTP links on the source host are normalized to HTTPS and the observed `/tt/`
collection aliases are normalized to their canonical paths. Original link URLs
remain in card metadata. Navigation, cover images, news, letters, and diaries
are outside this adapter's scope. External document links remain unsupported.

Both historical editions and supplied modern text PDFs are eligible. Files are
saved unchanged under `__artifacts/ingestion/isxaki/files/` with the shared local
manifest, SHA-256/MD5, integrity checks, budgets, and recheck behavior. HTML-only
texts remain metadata; no HTML/text artifact or PDF is generated. A title or
bibliographic claim does not establish language, edition accuracy, or completeness.
Malformed or broken file links are retained and reported when downloads fail;
they are not silently repaired or dropped.

The 2026-10-27 live check completed all five configured collections in six
listing requests and five record requests: 64 document relationships pointing
to 63 unique file URLs. It downloaded “Бай углы” (31,535,638 bytes), verified the
saved SHA-256/MD5, size, and observation link, and checked that a repeated CLI
download skipped an isolated copy of the completed sample with zero requests.
The other 63 relationships remain pending; their file availability and integrity
have not been verified. Traversal completion covers these five sections, not
the entire website, and the source supplies no independent catalog count.

### Internet Archive originals

Configure `sources.internet_archive.archive_url: https://archive.org` in the
operational YAML. No login, borrowing credentials, or new dependencies are needed.

```bash
python cli.py --config ingestion.yaml discover --source internet_archive --max-pages 2
python cli.py --config ingestion.yaml download --source internet_archive --limit 1
python cli.py --config ingestion.yaml run --source internet_archive --max-pages 2 --limit 1
python cli.py --config ingestion.yaml status --source internet_archive
python cli.py --config ingestion.yaml download --source internet_archive --recheck --limit 1
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

### KFU historical books and manuscripts

Configure the two source entries from `ingestion.example.yaml`. Both collections
use the same adapter but maintain independent local manifests and discovery
checkpoints. All records in the selected collections are admitted; supplied
language labels are retained without filtering or content-language inference.

```bash
python cli.py --config ingestion.yaml discover --source kfu_books --max-pages 1
python cli.py --config ingestion.yaml discover --source kfu_manuscripts --max-pages 1
python cli.py --config ingestion.yaml download --source kfu_books --limit 1
python cli.py --config ingestion.yaml download --source kfu_manuscripts --limit 1
python cli.py --config ingestion.yaml run --source kfu_books --max-pages 1 --limit 1
python cli.py --config ingestion.yaml status --source kfu_books
python cli.py --config ingestion.yaml status --source kfu_manuscripts
```

Discovery follows each collection's native `?offset=` links (currently 20 records
per page), with validated displayed ranges, counts, record identities, and next
offsets. A final root-page count check also consumes the discovery page budget.
Repeat `discover` to resume pending records and the listing frontier. Count changes
or repeated identities require a fresh scan without deleting historical evidence.
The current advertised totals, 135 books and 256 manuscripts, are catalog records,
not counts of public PDFs. Traversal is not a transactional snapshot of the site.

Each record retains its native handle, Dublin Core metadata, bibliographic rows,
original-script titles, collection provenance, and per-file descriptions. Record
identity is the handle; asset identity is the bitstream sequence and native
filename within that handle. If the source changes a bitstream route, it creates
a new asset identity; earlier evidence remains retained. Changing a file's bytes
at the same URL requires an explicit `download --recheck` when no reliable
content-version hint is supplied.

Restriction labels are interpreted per `.fileBlock`, not across the entire book.
A file marked “Ограниченный доступ”, showing a lock, or offering “Запросить копию”
is held as `kfu_restricted`. A public PDF remains eligible even when the same
record's ZIP package is restricted. Supported direct document formats reuse the
shared downloader. HTML and ZIP packages remain metadata; archives are not expanded.
Thumbnails are skipped and duplicate thumbnail/download links do not create separate assets.

When no eligible public direct PDF is available, discovery resolves public
`Set of JPEG` readers. It checks the advertised bitstream range, numbered filename
endpoints, file count, and the reader's explicitly linked IIIF manifest. The manifest
must contain one sequence with the same number of canvases, numbered in order,
with distinct full JPEG resources. Original bitstream URLs are expanded only within
the declared sequence and numbered filename ranges; IIIF image derivatives and
thumbnails are not downloaded. Multiple sets are ordered by nonoverlapping bitstream
ranges. An unrecognized filename pattern (for example `001.jpg ... Целый.jpg`)
holds all public image sets in that record as `reader_unsupported` for review.
Reader fetch or malformed-manifest failures leave the record pending for retry.
Restricted readers are never fetched. Public direct PDFs take priority without
fetching the reader. Reader and manifest requests use the ordinary request pacing,
timeouts, retries, deadline, and 2 MiB text response cap.

KFU image PDFs use **200 DPI colour, JPEG quality 85**, with Lanczos downsampling,
EXIF orientation handling, retained RGB ICC profiles, and the original physical page
dimensions. No grayscale conversion or lower-resolution fallback is used. A source
JPEG without valid DPI metadata, below 200 DPI, or outside RGB/grayscale colour modes
prevents publication and remains available for review; images are not upscaled to
claim missing detail. The original JPEG bytes remain unchanged in `files/`.

`--limit` counts each direct file or entire image book as one item. Completed image
downloads survive byte caps, deadlines, and interruptions. A later `download` resumes
from verified originals, and publishes `derived/<sha256>.pdf` atomically only after
every expected page is present and the PDF page count is verified. No incomplete
PDF is published. Policy, Pillow version, original hashes, source observation, page
order, and conversion version participate in the assembly fingerprint. Missing or
damaged PDFs are rebuilt; unchanged complete books are reused without network access.
`--recheck` revalidates original images. `status` reports `pdf_books` and `image_pages`.

The optional `limits.max_derived_pdf_bytes` bounds assembled PDFs separately from
individual downloaded originals. Its default is 536870912 bytes (512 MiB); the
existing `max_file_bytes` still bounds each original image/document. Both limits
are enforced, and assembly also respects the shared disk reserve and deadline.
Keeping originals requires additional disk space beyond the compressed PDF.

Discovery parser version 2 starts a fresh collection scan so previously observed
image-only records can acquire page descriptors. Existing original files and
historical observations remain retained. Repeat discovery to complete that scan.

Restricted document URLs, names, displayed sizes, formats, and copy-request links
remain available in the manifest. Restrictions are not download failures, and
`status` reports held document assets in `unsupported_reasons.kfu_restricted`.
A later discovery that observes the same file as public can return it to the
download queue. An allegedly public file returning login/error HTML or an
unexpected redirect fails acquisition without becoming a successful document.

Files stay under `__artifacts/ingestion/kfu_books/files/` or
`__artifacts/ingestion/kfu_manuscripts/files/`, with the existing SHA-256/MD5,
byte/file limits, disk reserve, recovery, and atomic publication behavior.
Displayed sizes such as “17,53 MB” are approximate source descriptions; transfer
headers and actual acquired bytes provide integrity evidence. Requests are
read-only, anonymous, and restricted to the repository's HTTPS source routes.

Restricted-file follow-up is deferred: investigate whether registration or
institutional access can legitimately grant permission, contact the library, or
request approved copies. The example `net/28280` (Ядкәр) exposes restricted PDF
and ZIP files; requesting its PDF anonymously returns HTML titled “Вход” despite
HTTP 200. `net/28236` exposes a public PDF and a restricted ZIP. The adapter does
not register accounts, authenticate, contact anyone, or submit request forms.

Initial direct-file verification on 2026-10-27 inspected the first two pages of each
collection: 40 book records and 40 manuscript records. Both scans retained the
next request at `offset=40` and have no unresolved discovery errors. The book
sample exposed 27 eligible direct documents and 13 restricted document assets;
the manuscript sample exposed one eligible direct document, with the other 39
records retained as metadata without direct supported documents. Restricted
packages and image-reader evidence remain in the per-record file inventory.
These are partial-scan results, not full-collection availability counts.

The CLI acquired the public `net/28236` PDF (`t88064.pdf`, 17,947,124 bytes) with
one request and no retries. Re-reading the saved file confirmed its recorded
size, MD5 `c3f8ebbe01bf316fa0c256360aa5c77e`, SHA-256
`12d23afb7a2cfb1ee948c2c112d9e0b3bce899834cfded4b68e5b9e3df3097bd`,
and acquisition-observation link. A repeated CLI download on an isolated copy
of that completed sample skipped it with zero requests. The main queues retain
26 pending book documents and one pending manuscript document at that point. No automated
tests were created or run; verification used code inspection and manual CLI runs.

Colour-reader verification on 2026-10-27 used public manuscript `net/27026`
([Хикмәт]): its two retained RGB JPEGs total 2,572,071 bytes at 300 DPI. The CLI
produced a two-page 1,394,253-byte colour PDF, with embedded image resolution at
least 200 DPI on both axes. Poppler rendering confirmed the red annotations and
blue stamp remain coloured. Repeating the download reused the PDF with zero
requests. A byte-capped run saved the first image without publishing a PDF; its
next invocation skipped that image and acquired only the second. A deliberately
small derived-PDF cap rejected publication, and restoring the cap rebuilt from
the originals without network requests. Bounded CLI discovery also resolved all
558 page descriptors for `net/28071` and 111 pages across two ordered readers for
`net/27974`, then preserved the remaining catalog work at its soft deadline.

### KFU «Ил» newspaper

`kfu_il` selects only <https://repo.kpfu.ru/jspui/handle/net/28060> and keeps its
own manifest under `__artifacts/ingestion/kfu_il/`. Add the `kfu_il` source entry
from `ingestion.example.yaml` to the selected operational YAML. The existing
KFU books and manuscripts sources continue to admit all collection languages.

```bash
python cli.py --config ingestion.yaml discover --source kfu_il --max-pages 1
python cli.py --config ingestion.yaml download --source kfu_il --limit 1
python cli.py --config ingestion.yaml run --source kfu_il --max-pages 1 --limit 1
python cli.py --config ingestion.yaml status --source kfu_il
```

Il requires an explicit `DC.language` value of `tt`, `tat`, `Tatar`, `татарский`,
`татарча`, or `татар теле` (case and surrounding whitespace are normalized).
Multiple source language fields are allowed when at least one identifies Tatar.
Recognized other-language-only records are held as `language_excluded`;
missing or unrecognized labels are held as `language_unknown` for review.
Crimean Tatar (`crh`) does not count as Tatar. Titles, Arabic script, and collection
membership do not substitute for the source language label. Held records retain
metadata and file inventories; their public document/reader assets remain
unsupported and no reader requests or downloads are made. Existing restriction
markers take priority in each asset's unsupported reason.

The manifest retains the native handle, original issue title, publication dates,
series descriptions, full bibliographic rows, supplied script descriptions,
collection provenance, and language/access evidence. Issue titles and dates stay
as supplied; no calendar conversion or issue numbering is inferred. Different
handles remain distinct records even when issue titles repeat. File bytes are
deduplicated by hash within the source's existing file store.

Il reuses KFU's validated native offset pagination, count verification, anonymous
GET-only acquisition, restriction handling, and resumable original-file downloads.
Eligible public direct PDFs take priority. When only a supported public JPEG
reader exists, the inherited assembler retains originals and derives a complete
200 DPI colour PDF at JPEG quality 85. `--limit` counts a direct file or whole
image-based issue as one item. No ZIP expansion, login, or copy-request submission
is performed. Restrictions remain explicit follow-up candidates in the file inventory.

The collection advertised 110 catalog records during selection on 2026-10-27;
this is not a count of distinct issues or guaranteed public files. Two inspected
records, `net/28231` (№39, 1917) and `net/28230` (№31, 1917), both identify `tt`
and expose public PDFs alongside restricted ZIPs. Small byte-range requests
returned PDF signatures and total lengths of 7,911,593 and 8,066,846 bytes.

Manual CLI verification on 2026-10-27 discovered the first 20 records, all labelled
`tt`, with 20 eligible PDFs and 20 restricted ZIP blocks retained as metadata.
Discovery stopped cleanly at its one-page cap with `offset=20` saved for resumption.
One bounded download acquired `net/28231`'s `1917-39.pdf` (7,911,593 bytes) in one
request without retries. Local inspection verified four readable PDF pages,
matching SHA-256/MD5, and its acquisition-to-observation link. A repeat download
on an isolated copy skipped the completed file with zero network requests. The
main queue retains 19 pending PDFs; these are partial-scan results. Compilation,
code inspection, and manual CLI verification were used; no automated tests were added.

### Tataroved publication archive

`tataroved` selects `https://tataroved.ru/publication/`. Add its source entry from
`ingestion.example.yaml` to the operational YAML. The Latin-domain publication
archive is distinct from the separately supplied Cyrillic `татаровед.рф` library
address; this adapter covers only `tataroved.ru` and its `www` alias.

```bash
python cli.py --config ingestion.yaml discover --source tataroved --max-pages 2
python cli.py --config ingestion.yaml download --source tataroved --limit 1
python cli.py --config ingestion.yaml run --source tataroved --max-pages 2 --limit 1
python cli.py --config ingestion.yaml status --source tataroved
```

The root catalog exposes a flattened native link hierarchy. Initial inspection
found 389 entries in the main catalog region, including categories, books,
chapters, and other publication pages. This is not a count of downloadable books
or an independently advertised numerical total. Discovery inspects every linked
entry once and preserves catalog titles/descriptions and native publication paths.
The final catalog fetch checks both the link count and the complete set of
identities. A changed catalog requires a fresh scan. Durable record checkpoints
allow interrupted discovery to resume; bounded runs stay incomplete while any
record or verification request remains. `--max-pages` counts catalog requests,
not individual publication records; time limits also bound record inspection.

The source's UTF-8 content is decoded explicitly by the shared HTTP layer. Old
absolute HTTP links and `www` aliases normalize to stable publication/file IDs.
The legacy site redirects public metadata pages and originals to HTTP, including
metadata rewrite routes with equivalent `url`/`bso_rewrite_url` parameters. Requests
start from normalized HTTPS URLs; native HTTP redirects are accepted only when
the resource identity is unchanged. Actual final transfer URLs are retained in
results. No authenticated sessions or credentials are used. Requests and redirects stay on the
two native aliases. Unrelated query parameters, rewrite-path changes, unsafe paths,
external download origins, and resource-changing redirects are rejected.

Per-entry titles, bibliographic subtitles, body descriptions, HTML references and
file inventories are retained. HTML-only pages, including books rendered as web
text, remain metadata; HTML is not converted to PDF. Direct supported document
originals include PDF, DjVu, EPUB, text and office formats. ZIP/RAR/7z packages
remain unsupported inventory, without expansion. External file references remain
metadata and are not fetched. Original bytes, colours and resolution are retained;
no image assembly, OCR, resampling, or content-language classifier is introduced.
The shared file, transfer, item, deadline and disk limits apply, along with atomic
publication, SHA-256/MD5 hashes, local integrity checks and conditional rechecks.

Language admission uses explicit statements in the entry's own bibliographic
subtitle, such as `(на татарском языке)` or a declared multilingual-language list.
Tatar titles, the site interface, topic categories, and bibliography references
are insufficient by themselves. The matched source statement is retained as
`language_evidence`; it is a source claim, not independent content verification.
Recognized other-language claims are excluded, and unknown/missing claims remain
held. A bibliographic claim about a web-text edition does not invent a file asset.

For an individually inspected multilingual original, use
`<artifacts_root>/tataroved/language-reviews.json` with the same version-1 schema
as the academic KFU adapter. Keys must be exact normalized original URLs from the
manifest. A review requires SHA-256, Tatar-containing language labels, reviewer
and reason. Example for the inspected 240-page conference volume:

```json
{
  "version": 1,
  "files": {
    "https://tataroved.ru/publicat/new/Gasprin_sbornik.pdf": {
      "sha256": "dab17261171565340e2f2d3777421386e35e3408e3e91e1bbd45ce76443efbe6",
      "languages": ["tt", "ru"],
      "reviewer": "Codex manual PDF text inspection",
      "reason": "Russian title/front matter and substantive Tatar articles on PDF pages 106, 130 and 139."
    }
  }
}
```

These are individual byte-pinned reviews, not collection-level language overrides.
A changed PDF hash fails before publication. Reviews cannot admit external URLs,
unsupported packages or formats. Discovery records applicable reviews; download
also refreshes them for existing records without requiring a catalog rescan.
Withdrawn reviews restore the source's language hold, retaining previous bytes and
observation/result history. New file URLs still require discovery. Review parsing,
refresh and pin enforcement are shared with the academic KFU adapter; its existing
review behavior remains in place.

Artifacts live under `__artifacts/ingestion/tataroved/`. The previously requested
Belem deferral note remains unchanged below; Belem is not part of this adapter.

Manual CLI verification inspected all 389 native catalog entries and verified
both their count and final identities, with no discovery errors. Of those records,
9 had recognized Tatar claims in their own subtitles, 2 had other-language claims,
and 378 required review; those counts include HTML-only pages. The scan inventoried
116 file references, with 111 held for missing language evidence and 4 external
references excluded. One multilingual PDF had an individual content review.

The reviewed `Gasprin_sbornik.pdf` downloaded as 1,762,258 original bytes and opened
as 240 pages. Its SHA-256 matched the review above; MD5 was
`a6592804280a068fa80d84292087da01`. Repeat download reused the verified original
with zero requests. In isolated CLI checks, withdrawing its review held the file
without requests while retaining its bytes/history; an incorrect review hash
rejected the transfer and published no original. A same-count changed catalog
identity triggered `restart_required`. The academic KFU adapter also reused both
of its existing reviewed PDFs with zero requests after the shared-review refactor.
Compilation and diff checks passed; no automated tests were added.

### KFU academic electronic archive

`kfu_dspace` is a separate source from `kfu_repository`. Configure
`sources.kfu_dspace.archive_url: https://dspace.kpfu.ru/xmlui/discover` in the
operational YAML (also shown in `ingestion.example.yaml`).

```bash
python cli.py --config ingestion.yaml discover --source kfu_dspace --max-pages 2
python cli.py --config ingestion.yaml download --source kfu_dspace --limit 1
python cli.py --config ingestion.yaml run --source kfu_dspace --max-pages 2 --limit 1
python cli.py --config ingestion.yaml status --source kfu_dspace
```

Discovery follows the native `татар` topic search, with ten items per page. The
initial search advertised 248 records. This is a candidate-search slice, not
exhaustive coverage of every Tatar document in the academic repository. Search
terms, subjects and titles do not establish document language. The source's UI
did not offer a working language filter during inspection. Native pagination,
displayed ranges, unique handles, count changes and final root-count verification
are checked. Bounded discovery resumes from saved pages and record checkpoints.
A changed count or repeated identity requires a fresh scan.

Each item is fetched using its native `?show=full` route. Full metadata rows,
raw DC tags, authors, dates, series, rights and file inventories are retained.
The third metadata-table column is the locale of a metadata value; `ru_RU` there
is not treated as the document's language. `dc.language.iso`, `dc.language` and
`DC.language` values supply the explicit item-language claims. Recognized Tatar
labels admit files; recognized other-language labels exclude them. Missing,
blank or unknown language labels remain held. Existing historical KFU language
policies are unchanged.

Public original PDFs are resolved from the explicitly linked native viewer's
record ID, filename and sequence using the same path construction as the site's
PDF.js script. Explicit native original links are supported too. Access flags and
record-level restrictions are retained; “только для КФУ” and other explicit access
restrictions take precedence over language evidence. Restricted files are not
requested, and account/institutional access follow-up is deferred. Only same-origin
HTTPS GET requests on the fixed search, item and original routes are permitted;
login/resource-changing redirects, unsafe filenames and mismatched record/file
identities are rejected. Unsupported formats remain inventory. PDFs retain their
original bytes; no OCR, image assembly, resampling, or automated language classifier
is introduced. Acquired PDFs must have a PDF signature, readable page structure,
and no password requirement. File/transfer/item/time/disk limits, atomic publication,
SHA-256/MD5 hashes, conditional rechecks and verified local reuse apply.

#### File-level language reviews

For files without usable item-language labels, inspect the actual PDF before
admitting it. Record the review at
`<artifacts_root>/kfu_dspace/language-reviews.json`. It is optional and local to the
artifact directory; it is not a default allowlist embedded in the adapter.

```json
{
  "version": 1,
  "files": {
    "https://dspace.kpfu.ru/xmlui/bitstream/handle/net/22102/10_179_000944.pdf?sequence=1&isAllowed=y": {
      "sha256": "ebc76333771db7ce4969665ffc4d2a300bd658e8823aef0eab89e18369975f50",
      "languages": ["tt", "ru"],
      "reviewer": "Codex manual PDF text inspection",
      "reason": "Title page and body pages 5, 18, 45, 90 and 141 contain substantive Tatar and Russian textbook text."
    }
  }
}
```

The example hash is from the inspected original, not a wildcard. Use the exact
original URL recorded in the manifest. Each review requires a lowercase SHA-256,
Tatar-containing language labels, a reviewer and a reason; additional audit fields
such as inspection date and page numbers are retained. Reviews affect only their
individual PDF and never lift access restrictions or format exclusions. They can
override an inaccurate non-Tatar source label while preserving the raw source claim.

Discovery records matching reviews. `download` also reapplies current reviews to
already discovered records and writes an observation when evidence changes, so a
full catalog rescan is unnecessary to grant or withdraw a review. A new URL still
needs discovery before acquisition. Withdrawing a review holds the file again;
existing original bytes and acquisition history are retained. A changed hash
forces fresh acquisition and validation. A PDF whose bytes differ from its review
hash fails before publication and needs a new manual review. Language uncertainty
is not silently replaced by a title-based guess.

Artifacts live under `__artifacts/ingestion/kfu_dspace/`; separate source manifests
and existing collectors are unaffected. Language inspection samples used during
implementation are retained separately under `__artifacts/kfu-dspace-inspection/`.

Manual verification completed the full 248-record search scan, including native
pagination, a resumed invocation, and final advertised-count verification. Older
thesis records without URI metadata are matched using their native full/short-view
self-links; separate cover viewers remain unsupported-format inventory. There are
no remaining discovery errors. Source language claims selected no records directly:
82 records had recognized other-language labels, while 166 had missing or unknown
labels. Seven records explicitly declared KFU-only access. These categories do not
imply that every record exposes a downloadable original.

Two individual PDF reviews were recorded after actual content inspection:

| Record | Original | Size | PDF pages | Review evidence |
| --- | --- | ---: | ---: | --- |
| `net/176943` | `kils2022_480_484.pdf` | 284,735 bytes | 5 | Tatar prose on pages 1 and 3; references on page 5 |
| `net/22102` | `10_179_000944.pdf` | 4,891,338 bytes | 147 | Tatar and Russian text across the title and five sampled body pages |

Both were acquired through normal CLI downloads and matched their pinned SHA-256.
Repeat download reused both with zero HTTP requests. An isolated withdrawn-review
run held the original without requests while retaining its bytes and acquisition
history. An isolated deliberately incorrect review hash fetched one PDF, rejected
it and published no original. Compilation and diff checks passed. No automated
tests were added, and no corpus-wide content-language inference was performed.

### KFU historical repository: all collections

`kfu_repository` selects `https://repo.kpfu.ru/jspui/community-list`. Add the
matching entry from `ingestion.example.yaml` to the operational YAML. This covers
all collections explicitly listed by that historical repository, including new
collections appearing on later scans. Other domains such as `dspace.kpfu.ru`,
`allfind.kpfu.ru` and `tatargalyame.kpfu.ru` are outside this adapter.

```bash
python cli.py --config ingestion.yaml discover --source kfu_repository --max-pages 25
python cli.py --config ingestion.yaml download --source kfu_repository --limit 1
python cli.py --config ingestion.yaml run --source kfu_repository --max-pages 25 --limit 1
python cli.py --config ingestion.yaml status --source kfu_repository
```

The native tree advertised 180 collections and 20,645 collection memberships
when inspected. These counts include non-Tatar holdings and overlaps; they are
not a count of unique eligible documents. Each collection is enumerated using
its own native offset pagination and advertised count, then its first page is
fetched again to verify that count. Duplicate records within a collection trigger
a restart; records shared by different collections retain all discovered
memberships under one handle. Collection titles, handles, community ancestry,
source counts, issue titles, dates, type labels and series values are retained.

Work proceeds one collection at a time, starting with existing Tatar-focused
slices. The durable frontier retains remaining collections, page offsets and
record checkpoints. A final fetch checks that the complete collection tree is
unchanged. A changed count, repeated identity within a collection or changed
final tree requires a new scan. Bounded invocations report incomplete discovery.
Counts are verified per collection; the shared `count_verified` field remains
false because there is no single repository-wide unique-item count. Completion
requires exhausting every collection and its verification request, the final tree
check, and all pending records. A new invocation after completion refreshes the tree.

All collections use explicit item-level Tatar admission, including multilingual
records containing a recognized Tatar label. Missing labels remain held; recognized
other languages are excluded. Neither collection title nor script substitutes for
a language label. Existing books/manuscripts adapters retain their original
all-language policy. Restricted files and unsupported formats remain inventories;
no authentication, copy-request submission, or archive expansion is introduced.
Explicit native “no files” records are retained as metadata rather than errors.
Public direct documents and supported JPEG/JPEG2000 readers reuse the shared KFU
downloader; complete page sets produce 200 DPI colour PDFs under existing limits.

Before acquisition, the adapter looks for matching original URLs, formats and
source versions in other `kfu_*` manifests under the same configured artifact root.
It verifies file size and SHA-256, then imports by hard link (or atomic copy) into
its own content-addressed store. Imported results retain the original source,
asset, result and observation IDs alongside their new observation relationship.
Existing manifests are not changed. Derived PDFs are rebuilt locally if needed;
page originals are reused. `--recheck` still performs normal HTTP revalidation.
This avoids repeat original transfers between the old slices and this adapter;
content identity of different previously unseen URLs is established after retrieval.
Artifacts live under `__artifacts/ingestion/kfu_repository/`. Existing source names
remain available for narrowly scoped collection runs.

Manual verification discovered the live 180-collection tree and 19 records in the
first two collections, including one explicit metadata-only record. A separate
invocation resumed the same scan and inspected 20 Il records without errors.
Two live Il listing batches correctly advanced offsets 0 → 20 → 40 and retained
40 distinct identities. A Russian-labelled record was excluded and an unlabelled
Vakyt record remained held. The final-tree verification branch was checked against
the saved native tree; a complete repository traversal was not performed.

Acquisition imported an existing 8,466,638-byte PDF from `kfu_azad_halyk` and
retrieved one new 8,751,131-byte PDF with one HTTP request. Both originals opened
as eight-page PDFs. An isolated repeat reused both with zero requests. Request
identities remain compact while larger resume snapshots stay in the frontier;
legacy adapters retain their original request-key behavior. After that change,
a fresh bounded CLI scan verified the first collection's complete 15-record count
without errors. Compilation and diff checks passed; no automated tests were added.

### KFU «Азад халык» newspaper

`kfu_azad_halyk` selects <https://repo.kpfu.ru/jspui/handle/net/27528> and keeps
its own manifest under `__artifacts/ingestion/kfu_azad_halyk/`. Add its source entry
from `ingestion.example.yaml` to the operational YAML.

```bash
python cli.py --config ingestion.yaml discover --source kfu_azad_halyk --max-pages 2
python cli.py --config ingestion.yaml download --source kfu_azad_halyk --limit 1
python cli.py --config ingestion.yaml run --source kfu_azad_halyk --max-pages 2 --limit 1
python cli.py --config ingestion.yaml status --source kfu_azad_halyk
```

This source reuses KFU's native collection traversal, durable checkpoints,
advertised-count verification, guarded public-file acquisition, atomic storage,
SHA-256/MD5 hashes, and local-file reuse. Publication metadata identifies
`Азад халык` as a newspaper and preserves the original issue title, dates and
series values. Each original file consumes one download item.

The explicit item-language filter is the same as for Il and Shura: recognized
Tatar labels admit files, recognized non-Tatar labels exclude them, and missing
or unknown labels remain held for review. Source language claims are retained
without claiming content verification. Restricted files remain inventoried for
later legitimate access follow-up; they are not requested. Eligible public direct
PDFs are retained unchanged, so there is no resampling or image assembly for
those files. The existing KFU reader fallback applies if public page sets appear
later, with the same 200 DPI colour policy and complete-issue requirement.

Manual CLI verification completed discovery of all 15 records, with the final
advertised count verified and no discovery errors. All 15 had `tt` labels and one
eligible public PDF each. A bounded `run --max-pages 2 --limit 1` downloaded
`net/27569` (`№ 15, 1906`) as an unchanged eight-page PDF of 8,466,638 bytes,
recording SHA-256 `24b2ab8292b4ff31150d1d93ee28e9033870f4e5eedc1b02188967c503256bfd`
and MD5 `ff0560df9b939d12abf599a638f998ec`. Fourteen files remain pending.
An isolated repeat using the completed record reused its verified local original
with zero HTTP requests. Compilation and diff checks passed; no automated tests
were added.

### KFU «Шура» journal

`kfu_shura` selects <https://repo.kpfu.ru/jspui/handle/net/25046> and keeps an
independent manifest under `__artifacts/ingestion/kfu_shura/`. Add its source entry
from `ingestion.example.yaml` to the selected operational YAML.

```bash
python cli.py --config ingestion.yaml discover --source kfu_shura --max-pages 2
python cli.py --config ingestion.yaml download --source kfu_shura --limit 1
python cli.py --config ingestion.yaml run --source kfu_shura --max-pages 2 --limit 1
python cli.py --config ingestion.yaml status --source kfu_shura
```

Shura uses the same explicit Tatar language policy as Il: recognized Tatar labels
admit a record, known other-language-only labels are `language_excluded`, and missing
or unrecognized labels are `language_unknown`. Raw metadata and file references
remain available for review. Collection membership and a Tatar issue title do not
replace a language label. The shared periodical metadata identifies the publication
as `Шура`, kind `journal`, preserving issue titles, dates, and series as supplied.
Existing KFU books/manuscripts and Il retain their current admission policies.

The collection advertised eight records on 2026-10-27. Seven 1917 issues identify
`DC.language: tt` and expose public direct PDFs of roughly 13–18 MB each. The eighth
record, `net/492`, describes the 1910 volume containing №1–24 and exposes a public
PDF displayed as 373.86 MB, but provides no `DC.language`. It is deliberately held
as `language_unknown`; discovery retains its metadata and file URL without fetching
the volume. The current 100 MiB per-file cap would also need explicit adjustment
before a later approved acquisition of that volume. No language override or size-cap
increase is made for it.

Native listing-range and count checks, restriction handling, stable handle identities,
hashes, atomic publication, and resumable downloads reuse the existing KFU adapter.
For the current eight-record collection, one listing response plus its final root
count recheck consumes two discovery pages. `--limit` counts direct files or whole
image-based issues; supported readers inherit the existing 200 DPI colour policy.
Public direct PDFs take priority and are retained without conversion. No account,
copy-request submission, archive expansion, or new image format support is introduced.

Manual CLI verification on 2026-10-27 completed discovery of all eight records
and verified the advertised count. Seven PDFs were eligible; the 1910 volume
remained `language_unknown` with no acquired bytes. One bounded download acquired
`net/25077`'s `№ 7.pdf` (18,427,602 bytes) in one request without retries. Local
inspection confirmed 28 readable PDF pages, matching recorded SHA-256/MD5, and the
acquisition-observation link. An isolated repeat skipped the completed issue and
held volume with zero requests. The main queue retains six pending PDFs, one
downloaded issue, and the held volume. Existing Il publication/admission metadata
and the all-language books/manuscripts policy were manually checked. Verification
used code inspection, compilation, and CLI runs; no automated tests were added.

### KFU «Вакыт» newspaper

`kfu_vakyt` uses the exact `is_part_of_series = Вакыт` search within newspaper
collection `net/86`. Its YAML `archive_url` is
`https://repo.kpfu.ru/jspui/handle/net/86/simple-search` (without query parameters).
The adapter supplies the fixed filter and native ten-record pagination itself;
it does not enumerate the other newspapers in that collection.

```bash
python cli.py --config ingestion.yaml discover --source kfu_vakyt --max-pages 25
python cli.py --config ingestion.yaml download --source kfu_vakyt --limit 1
python cli.py --config ingestion.yaml run --source kfu_vakyt --max-pages 25 --limit 1
python cli.py --config ingestion.yaml status --source kfu_vakyt
```

Repeated discovery resumes the saved frontier and pending records. The advertised
count (2,233 during inspection), displayed ranges, native next link, unique record
identities, exact series metadata, and final count verification are checked.
A changed count or repeated identity requires a fresh scan. A bounded invocation
is reported as incomplete until all listing pages and records have been checked.

As for Il/Shura, only explicit recognized Tatar item-language labels admit files.
Missing/unknown labels remain `language_unknown`; recognized other languages are
excluded. Titles, script and collection membership do not override this policy.
Metadata and restricted-file inventory are retained; restricted files are not
requested and access follow-up remains deferred.

Readers support numbered JPEG and JPEG2000 ranges, including matching date/issue
prefixes. Native filenames, bitstream sequences, counts and IIIF order must agree.
Originals are retained with hashes, validated by the matching codec and decoded
before publication. Each page must be a single image of at most 150 megapixels;
Pillow's own safety limits remain enabled. Large accepted pages can require
substantial memory, but pages are processed sequentially. Corrupt, oversized or
unsupported pages leave the issue incomplete rather than publishing a partial PDF.

Complete issues use 200 DPI RGB JPEG quality 85, preserving physical page size and
RGB colour profiles. Source DPI must be at least 200 on both axes; no upscaling
or lower-resolution fallback is used. File, transfer, item, disk, deadline and
separate derived-PDF limits apply. One issue consumes one image-download item;
interrupted issues resume from verified originals. Repeat runs verify local hashes
and reuse complete PDFs without network requests; `--recheck` revalidates originals.
Public direct PDFs are preferred when available. Artifacts are stored under
`__artifacts/ingestion/kfu_vakyt/`. See the [earlier pilot](kfu-vakyt-pilot.md)
for the original investigation; the source is now registered for production use.

Implementation verification inspected 30 native results across three listing pages,
including resumption in a separate invocation without duplicate identities or errors.
A separately selected, explicitly `tt`-labelled `net/26933` issue was observed and
then downloaded through the normal CLI: four originals (15,611,732 bytes) and a
four-page 10,891,710-byte PDF. Every output page measured at least 200 DPI on both
axes. Repeat download reused all four originals and the PDF with zero requests.
The native six-page `net/7229` JPEG2000 reader enumerated correctly; its existing
121.9-megapixel research original passed full codec validation. That unlabelled
issue remained held. The full 2,233-record scan and a complete eligible JPEG2000
issue download were not performed. Compilation, diff checks, and manual CLI
verification passed; no automated tests were added.

### Tatar Galyame educational catalog

`tatargalyame` is separate from the `repo.kpfu.ru` sources. Select the operational
YAML entry from `ingestion.example.yaml`, using exactly
`https://tatargalyame.kpfu.ru/catalogue`. The older `/en/catalogue` inventory link
returned HTTP 404 during inspection; `/catalogue` and the public JSON API returned
HTTP 200 through direct HTTP, even when the browsing tool could not open the site.

```bash
python cli.py --config ingestion.yaml discover --source tatargalyame --max-pages 15
python cli.py --config ingestion.yaml download --source tatargalyame --limit 1
python cli.py --config ingestion.yaml run --source tatargalyame --max-pages 15 --limit 1
python cli.py --config ingestion.yaml status --source tatargalyame
```

The owner selected **all hosted documents**. The API does not supply a per-document
language field. `catalog_locale: tt` describes the interface, and
`language_selection: unverified` records that document language has not been
established. Tatar descriptions and titles do not establish the language of a
Russian, bilingual, or multilingual attachment. No content-language inference,
OCR, or translation is performed.

Discovery uses the public GET endpoints called by the catalog's own JavaScript:
`/api/struct[/{category-path}]?lang=tt&q=` and `/api/sid/{uuid}?lang=tt`.
Categories form a linked tree with returned ancestry rather than numbered result
pages. The adapter validates that ancestry and each child/resource identity,
follows all linked categories without a search filter, and inspects each visible
resource. Repeated resource UUIDs retain multiple category contexts without
creating duplicate source records. The API's `QA` and `HIDDEN` resource types are
skipped in accordance with the public listing's visibility rule; `DUMMY___`
category placeholders do not become resources. Empty leaf categories are allowed,
while an empty root, malformed response, cycle, or invalid identity prevents scan
completion. Category paths are bounded to 12 levels. The ordinary 2 MiB text
response cap, request pacing, retries, deadline, and discovery page cap apply.

Each category API response consumes one discovery page; individual resource API
requests consume the shared deadline and are counted separately. Repeating `discover`
resumes saved categories and pending resources. The source supplies no global
record count or pagination total, so completion means traversal of the observed
linked tree with no unresolved resource requests. It does not establish a
transactional snapshot or completeness of unlinked files on the server.

Resource identity is its UUID, with both the public `/catalogue/{uuid}` URL and
the API URL retained. Raw API fields preserve authors, coordinators, performers,
description, keywords, year, modification timestamp, files, and external URLs.
Category ancestry and listing evidence remain separate provenance. A changed
resource timestamp acts as a source-version hint: after discovery observes it,
the next download revalidates unchanged filenames without reusing old conditional
response validators. Explicit `--recheck` is available when that hint is absent
or does not change.

The site's `file` array builds native links as `/files/{uuid}/{filename}`. Those
explicit filenames, including Unicode and spaces, are encoded as individual URL
path segments. Filename traversal, control characters, ambiguous encoded names,
unexpected API routes, authentication redirects, and origin changes are rejected.
Only explicitly listed, same-origin `/files/` documents in the shared supported
formats are acquired. Direct hosted `/files/` links in the `url` array are also
eligible. HTML, ZIP packages, images, audio/video, and other unsupported attachments
remain listed with `unsupported_format`; catalog cover thumbnails are not collected.

External URLs are retained as references without being followed. Direct external
document references additionally appear as held `external_origin` assets; same-origin
document links outside the approved hosted-file route are held as `unsupported_route`.
This includes references to other KFU hosts: their file provider and catalog discovery
provenance remain distinct. The adapter does not crawl external sites, expand
archives, assemble readers, authenticate, or call catalog management/upload routes.

Original files are stored unchanged under
`__artifacts/ingestion/tatargalyame/files/<sha256>.<extension>`. The source has an
independent manifest and summaries. The existing downloader provides bounded
transfers, SHA-256/MD5, format checks, atomic publication, local integrity checks,
retry/resume behavior, and reuse of completed originals. `--limit` counts files,
including distinct textbook, workbook, and methodological attachments belonging
to the same resource.

Manual verification on 2026-10-27 traversed all 34 observed category responses
through the implemented parser: 279 distinct visible resource UUIDs, with 127
listed hosted PDFs, one PPTX, and one PNG attachment. Five `HIDDEN` rows were
skipped. These are API listing counts, not successful-download or confirmed-language
counts. A separate bounded CLI pilot committed 62 resource records and queued
19 PDFs plus one PPTX, then saved the remaining 19 category requests at its soft
deadline with no unresolved discovery errors. The first downloaded file,
`Яңа ел 1.pdf`, contains one readable PDF page and is 152,702 bytes. Its SHA-256,
MD5, source-version marker, and acquisition-observation link were verified. A
repeat CLI download on an isolated copy reused it with zero network requests.
The main queue retains 19 pending files. Verification used code inspection,
compilation, and manual CLI runs; no automated tests were added.

### Shared configuration and operation

Use the repository virtual environment and its existing `requirements.txt`.
Copy `ingestion.example.yaml` to `ingestion.yaml`, review its paths and limits,
then select that operational file explicitly:

```bash
python cli.py sources
python cli.py --config ingestion.yaml discover --source magarif
python cli.py --config ingestion.yaml status --source magarif
python cli.py --config ingestion.yaml download --source magarif --limit 1
python cli.py --config ingestion.yaml run --source magarif
python cli.py --config ingestion.yaml download --source magarif --recheck
python cli.py --config ingestion.yaml discover --source tatarica --max-pages 2
python cli.py --config ingestion.yaml status --source tatarica
python cli.py --config ingestion.yaml download --source tatarica --limit 1
python cli.py --config ingestion.yaml discover --source darul_kutub --max-pages 2
python cli.py --config ingestion.yaml status --source darul_kutub
python cli.py --config ingestion.yaml download --source darul_kutub --limit 1
python cli.py --config ingestion.yaml discover --source kazanutlary --max-pages 2
python cli.py --config ingestion.yaml download --source kazanutlary --limit 1
python cli.py --config ingestion.yaml status --source kazanutlary
python cli.py --config ingestion.yaml discover --source tatkniga --max-pages 2
python cli.py --config ingestion.yaml download --source tatkniga --limit 1
python cli.py --config ingestion.yaml status --source tatkniga
python cli.py --config ingestion.yaml discover --source miras --max-pages 2 --session-file PATH
python cli.py --config ingestion.yaml download --source miras --limit 2 --session-file PATH
python cli.py --config ingestion.yaml status --source miras
```

`sources` and command help do not need configuration. Other commands require
`--config` before the command name. Relative artifact paths resolve against the
YAML file's directory. Environment variables do not override YAML settings, and
example files are never selected automatically. Miras network commands require
`--session-file` from an ordinary verified browser, shared with `miras_periodicals`;
the other adapters require no credentials. `--session-file` is rejected for other sources. `status` does not read
a session file or make network requests.

Only the selected source needs a `sources.<source>.archive_url` configuration
entry. Existing Magarif-only YAML files remain valid. To enable Tatarica in an
existing file, add the `sources.tatarica` entry from the example; keep your chosen
paths, budgets, and network settings. Enable Darul-Kutub the same way with the
`sources.darul_kutub` entry.

`discover` follows source-specific catalog pagination and stores record metadata
plus file descriptors without downloading originals. It checkpoints listing
requests and outstanding record URLs. Each invocation resumes an incomplete scan;
after completion, the next invocation starts a fresh scan. A failed record stays
queued for another invocation while independent records can proceed. Successfully
inspected records are not refetched merely because a bounded run resumes.
Records without attachments remain visible. A partial or failed scan never marks
unvisited records absent.
If an attachment disappears from a successfully inspected record, its history
remains retained and it leaves the current download queue.

The parser uses record content and its attachment list. Shared banners and footer
documents are excluded. Supported originals include PDF, DjVu, EPUB, text/HTML,
RTF, and common office formats. Recognized document links outside the source
origin remain listed as `unsupported`; Magarif also retains unsupported entries
from its explicit attachment list. Metadata and archive context are
source claims; downloading does not confirm language, quality, or completeness.

Tatarica's initial page shows only a small catalog window. Its adapter follows
the same read-only form POST pagination as the site's “Тагын” control, using the
current chapter ID and advertised count from the page rather than hardcoded
values. Both observed library URL variants are supported. It extracts document
links only from record content, including extensionless
`/download_file/view/<id>` routes. The shared downloader resolves those routes
to the actual files and determines their document extension.

All linked Tatarica editions are eligible, including Russian and bilingual
editions. No language filter or placeholder language field is added. The adapter
retains bibliographic paragraphs, edition labels, and surrounding source text;
it does not turn them into inferred authors, publication dates, or language facts.
HTML-only records retain their available metadata without generating an HTML or
text artifact. Unrelated encyclopedia navigation and recommendations are excluded.

Darul-Kutub follows the search catalog's native next-page links. Article results
map to their parent book or journal issue; reader page hints do not create new
publications. Coverage counts raw search rows separately from unique publications.
Adjacent pages can contain different articles from the same issue, so repeated
pages are detected using row titles, links, and source text together.

Publication metadata preserves titles, authors, publisher, description, and raw
bibliographic details when supplied. Language labels remain in the source text;
no inferred language field is added. All exposed original file parts are queued,
including parts in hidden volume tabs. Direct reader originals are preferred over
download buttons of the same format; button URLs remain metadata evidence, and
other offered formats remain eligible. Button-route IDs are not publication IDs.
The adapter does not assume that reader and button responses contain identical
bytes. Unsupported originals remain visible in the backlog.

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
are used. See [the historical-data notes](../tatkniga/README.md).

Kazan Utları follows every linked year listing across Казан утлары, Яңалиф,
Совет әдәбияты, Атака, and Безнең юл. Native year URLs are preserved even when
their slugs differ from their visible labels. Duplicate navigation links are
collapsed. Issue article-index pages and unrelated footer PDFs are excluded.
Issue metadata retains headings, descriptions when supplied, journal/year listing
context, and the literal reader configuration. Listing context is checkpointed
and appended as source evidence when an issue appears in another listing.

The reader's `count` is interpreted as the total image count: indices `000`
through `count - 1`, including the first reader image. Four inspected issues exposed this many
images while their reader's inclusive loop requested an additional nonexistent
image. This indexing discrepancy is preserved in metadata. Unrecognized reader
structures fail discovery instead of producing guessed image sequences. Catalog
completion means traversal of linked listings; no site-wide total is advertised.

For `kazanutlary`, `--limit` and `max_items` count **issues**, including their image
downloads and assembly. Tatkniga uses the mixed file/book units described above;
remaining sources count individual files. Byte, file-size, deadline, pacing,
and disk-reserve controls still apply. Interrupted
issues resume from verified image files on the next invocation. A failed page
does not discard the other pages, and an issue remains incomplete until every
expected page is available. No partial PDF is published.

JPEGs are retained as upstream originals in `files/`. PyMuPDF embeds them in
numeric order, preserving image quality, proportions, and orientation. Generated
PDFs live in `__artifacts/ingestion/kazanutlary/derived/<sha256>.pdf`; they are
derived artifacts, not upstream PDFs. The manifest records PDF hashes, size,
page count, assembler version, source observation, input fingerprint, and ordered
image asset/result IDs and hashes. Assembly enforces the configured file-size cap
and publishes atomically after reopening and checking the page count. There is
no OCR or text extraction.

`download` verifies local images and PDFs, reuses unchanged complete issues, and
rebuilds missing, damaged, or outdated PDFs. `--recheck` revalidates image URLs;
changed inputs create another retained PDF result. Failed rechecks leave the
issue unresolved while preserving historical files. Status includes recorded
image progress and complete/incomplete/failed PDF issue counts; it remains a
read-only manifest view rather than an integrity audit.

With the example configuration, artifacts live under:

```text
__artifacts/ingestion/magarif/
  manifest.json             # schema_version: 1; records, observations, assets, results
  files/<sha256>.<extension> # acquired originals; upstream filenames are metadata
  summaries/<run-id>.json   # structured command summaries
  .tmp/run-*/               # temporary bytes owned by individual runs
  .lock                     # operating-system lock; released when the process exits
```

Tatarica uses the same layout under `__artifacts/ingestion/tatarica/`. Its records
use supplied CMS page IDs when available, and file assets use supplied download
IDs. URLs are the fallback when native IDs are absent. URL aliases and renamed
records retain their provenance without creating another native-ID identity.
Magarif's existing URL identities and saved files require no migration.
Darul-Kutub uses `__artifacts/ingestion/darul_kutub/`, publication IDs from
`/books/<id>/`, and original URLs for file identity within each publication.

Each source uses an exclusive writer lock. `status` only reads the manifest and
does not issue network requests or create artifact files. It reports recorded
counts, not a new filesystem/integrity audit. The manifest is saved atomically
after individual records and completed downloads. Metadata changes append
observations; unchanged consecutive observations are not duplicated. Original
download results retain their captured observation IDs.

<a id="miras-cookie-based-access-pilot"></a>

## Wikimedia Commons original documents

Add `sources.commons` from the example to the selected operational YAML:

```bash
python cli.py --config ingestion.yaml discover --source commons --max-pages 2
python cli.py --config ingestion.yaml download --source commons --limit 1
python cli.py --config ingestion.yaml run --source commons --max-pages 5 --limit 1
python cli.py --config ingestion.yaml status --source commons
```

The seed is native category ID `70354556` (Tatar-language books). Discovery follows
its subcategories by native ID and API continuation tokens, with ten members per
batch. `--max-pages` counts category-member API batches; file-metadata lookups use
the same pacing, retry, deadline, and 2 MiB inspection limits as other adapters.
Shared categories and files are deduplicated; category cycles do not recurse.
Valid empty batches may advance, while missing categories, API errors, repeated
batches, and invalid cursors leave work incomplete. Expired/cyclic cursors restart
the next scan without discarding prior observations.

Only the existing document formats, excluding HTML/HTM, become candidates. Image
filenames are filtered before file-metadata lookups, and their IDs, titles, and
metadata are not retained as records or descriptors. Returned MIME must agree
with the document format. Category membership is admission evidence, not verified
language or book completeness. Discovery does not request original bytes or previews.

File-page IDs supply stable record identities (`file:<id>`), and each record has
one current-original representation. Retained metadata includes the native title,
reported MIME, size, page count, upload timestamp, source SHA-1, description URLs,
and multilingual extended metadata with credits and licensing claims. Unknown
metadata fields remain intact. Source page counts are upstream claims; reported
size and SHA-1 are verified when an original is acquired. Tracking parameters are removed from file locators;
continuation tokens remain in checkpoints rather than metadata observations.

Missing or unavailable originals remain metadata-only records. Partial scans do
not establish disappearance. Unchanged scans update last-seen time without new
observations; changed metadata or upload versions retain their history. Files
reached through multiple categories share one record, with API-reported category
membership and the seed scope retained as evidence.

`discover`, `download`, `run`, and `status` are supported. State, original files,
and summaries live under `__artifacts/ingestion/commons/`. A source-specific request
guard permits read-only GET requests to the Commons metadata endpoint and native
original paths on `https://upload.wikimedia.org/wikipedia/commons/`. Thumbnail,
preview, archive-version, foreign-origin, and changed-file redirects are rejected.
Requests identify the crawler with its repository contact URL; no session export
is needed. No database or storage migration is involved.

Each file requires a supported extension, matching MIME, positive reported size,
and a 40-character hexadecimal source SHA-1. The shared downloader streams to a
temporary file, verifies response length and format signatures, computes local
SHA-256/MD5, and then computes SHA-1. Its integrity callback receives the measured
SHA-1 alongside the normal digests and rejects size/hash mismatches before atomic
publication. A mismatch remains a retryable failure requiring refreshed discovery;
the mismatched bytes do not become a successful local original. Acquisition results
retain `sha1` and `source_integrity_checks: [size, sha1]` as verification evidence.

The source SHA-1 and reported size form the source-version hint. Rediscovery of
changed bytes makes the next download reacquire the original, even with an intact
older local file. Unchanged completed files are verified locally and skipped;
`--recheck` revalidates them through normal HTTP conditional requests. Completed
originals survive interrupted runs. Existing discovery-only manifests can download
without rebuilding their inventory: version hints are derived from their retained
size and SHA-1 fields. Parser version 3 refreshes observations on the next discovery.

`--limit` counts individual original files. Reported file sizes are checked against
the configured per-file and remaining download-byte caps before opening a transfer.
Oversized files remain failed/retryable without being truncated or silently
recompressed. Raising the selected YAML cap permits retrying them. The existing
disk reserve, deadline, retries, and atomic publication rules continue to apply.
The 35-file inventory inspected on 2026-10-27 contained 34 PDFs and one DjVu,
totalling about 1.44 GB in reported original bytes. Thirty-two fit the current
100 MiB per-file cap; three require an explicit cap increase. These inventory
sizes do not establish successful acquisition, language, or document completeness.

Manual verification on 2026-10-27 completed a fresh five-batch discovery with 35
document records and no errors. One bounded download acquired the 11-page
`'Ильм халь.Алтынчы кысым. علم حال. آلتنجي قسم.pdf` (14,412,954 bytes) with SHA-1
`3808410ab3db9832e28f0380f14555fbd81a07b4`, matching Commons metadata. An isolated
download acquired `Татарча-урысча сүзлек (1927).djvu` (12,739,699 bytes), also
matching its source SHA-1. Local SHA-256/MD5, source-version hints, and
acquisition-observation links were verified. Repeating the isolated two-file
download skipped both originals with zero requests. A real oversized candidate
was rejected before any request or transferred bytes. The main queue retains
one downloaded PDF and 34 pending originals. Verification used compilation,
code inspection, and manual CLI runs; no automated tests were added.

## Miras periodicals

The separate `miras_periodicals` source uses the existing Miras session export and
PDF downloader with its own manifest under `<artifacts_root>/miras_periodicals/`.
Add this entry under `sources` in your operational YAML:

```yaml
miras_periodicals:
  archive_url: https://miras.info/projects/mirasxane/periodicals/
```

```bash
python cli.py --config ingestion.yaml discover --source miras_periodicals --max-pages 1 \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
python cli.py --config ingestion.yaml download --source miras_periodicals --limit 1 \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
python cli.py --config ingestion.yaml status --source miras_periodicals
```

Records represent periodical series, identified by native numeric IDs as
`periodical:<id>`. Catalog pagination and record checkpoints are independent of
the books source. Description, series-level language evidence, catalog context,
reader links, and selector labels/values are retained. Source-described historical
issue totals are not downloadable-holdings counts. No existing books or pilot
manifest is imported or rewritten.

Only explicitly exposed same-origin original PDFs are supported: direct links,
`viewer.html?file=...` references, and selectors whose values are actual PDF or
viewer URLs. The adapter does not construct file paths from year/issue numbers or
execute website scripts. Unresolved selector options are retained as metadata and
hold the series' otherwise eligible PDFs with `reader_unresolved`, avoiding a
partial default-issue acquisition presented as complete coverage. Other formats
and external files remain unsupported. An explicit Tatar language claim in series
metadata or description is required; unlabelled series are held with
`language_unknown`. This is upstream evidence, not verified document language.

**Verification pending (2026-10-28):** the bounded CLI run with the saved browser
session stopped after one access rejection, before catalog inspection. It exited
nonzero and preserved an incomplete scan with one pending listing request and zero
records, assets, or acquired bytes. CLI registration, configuration loading,
read-only status, compilation, and whitespace checks passed. Diagnostics are under
`/tmp/miras-periodicals-verification/miras_periodicals/`.
A refreshed session is required to verify live
pagination and issue-selector behavior and acquire a complete issue PDF. Dynamic
selector resolution remains unfinished; no complete periodical acquisition or
catalog coverage has been verified. Existing PDF validation, hashes, budgets,
access rejection handling, and session format are reused from `miras`.

## Miras books and browser-session access

Miras is a full shared-CLI adapter for the unfiltered **books** catalog. All
languages are eligible, including editions with missing or unrecognized language
labels. Manuscripts, periodicals, other project categories, alphabetical filters,
and search forms are not traversed. Add `sources.miras.archive_url` from the
example to your operational YAML. Both trailing-slash variants are accepted.

Supply a Miras-only session export from your ordinary, manually verified browser
to each network command:

```bash
python cli.py --config ingestion.yaml discover --source miras --max-pages 2 \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
python cli.py --config ingestion.yaml download --source miras --limit 2 \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
python cli.py --config ingestion.yaml run --source miras --max-pages 2 --limit 2 \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
python cli.py --config ingestion.yaml status --source miras

# Retained diagnostic: inspect the catalog and download one fixed sample.
python cli.py --config ingestion.yaml probe --source miras \
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

### Remembered fallback: ordinary-browser extension

If cookie-based HTTP access becomes insufficient, reconsider a small extension
that reads Miras pages and downloads PDFs inside a normal verified browser,
without a debugging connection. The experiment on 2026-10-27 downloaded a PDF
with the same SHA-256 as the HTTP copy. Its implementation and sample-import CLI
have been removed; this is a fallback idea only. The earlier Playwright approach
was rejected by SafeLine WAF with “Debugging Detected” and has also been removed.

`download` processes pending/failed current assets, verifies existing local bytes
before skipping successes, and reacquires missing or damaged local copies.
`--recheck` additionally checks completed assets with ETag/Last-Modified
conditions when available, or downloads again when no validator exists. Use it
explicitly to detect replacements at an unchanged URL. New bytes get a new
content-addressed file and retained result; old versions remain on disk. Exact
byte duplicates share a file while retaining their source relationships.
Changes to an attachment URL produce separate identities for URL-identified
assets. A Tatarica download-route alias with the same supplied file ID retains
its asset identity.

Transfers stream to a temporary file, compute SHA-256/MD5 and actual size, check
applicable response lengths and basic format signatures, and publish the file
before committing success. HTML error/login responses in place of documents,
empty bodies, and known size mismatches do not become successful downloads.
These checks do not perform structural document validation or OCR.

The local-pilot example caps discovery at 25 pages, acquisition at 25 started
items, attempted download body bytes at 1 GiB, and individual files at 100 MiB.
Assembled PDFs have a separate optional `limits.max_derived_pdf_bytes` cap,
defaulting to 512 MiB; individual downloaded originals retain the file-size cap.
It reserves 512 MiB of disk and uses a 15-minute soft deadline. Requests are
sequential, paced one second apart, and use 10-second connection/60-second read
timeouts with at most three attempts for retryable transport/server failures.
An in-flight read may take up to its configured timeout before a soft deadline
can be observed. Retry bytes count against the same acquisition cap; discovery
HTML requests are counted separately and limited to 2 MiB per response.

`--limit` on `download`/`run` and `--max-pages` on `discover`/`run` can lower YAML
caps; edit YAML explicitly to raise them. Reaching a budget boundary leaves
remaining work eligible and returns zero when no run errors occurred. Unknown
length transfers that exhaust the byte budget before EOF remain unresolved.
An item failure is saved and independent items can continue; authentication or
availability errors are reported, and disk/storage failures stop acquisition.
Failed downloads are retried on the next download command; unsupported backlog
is reported separately. Commands return nonzero for newly encountered failures.

Discovery summaries and `status` include coverage: catalog entries enumerated,
unique URLs and native records inspected, remaining listing/record work, and
the provider's advertised count when available. Listing requests, including a final count check,
consume the page cap; record-detail requests are bounded by the shared deadline
and network controls. A page cap or deadline keeps discovery incomplete and
preserves the pending frontier for the next invocation.

Tatarica and Darul-Kutub advertise substantially more catalog entries than the default
page cap can enumerate in one run. Repeat `discover` to continue. The count is
catalog entries, not available PDFs or confirmed Tatar documents. Empty or short
responses before the expected end, repeated batches, missing structure, and
failed records prevent completion. A final root-page check compares the current
advertised count with enumeration; a mismatch reports an error and makes the
next invocation start a fresh scan, retaining committed records and files.
Completion means the selected catalog traversal finished, not that every file
anywhere on the provider's website has been found. Count verification also does
not establish a transactional snapshot of a changing remote catalog.

Every mutating command prints progress and a structured summary including errors,
budget stops, request/retry counts, downloaded/skipped/reused files, attempted
download bytes, backlog counts, and the summary file path. Ordinary failures
remove only that run's partial bytes. A forcibly terminated process may leave
its own `.tmp/run-*` directory; a later run does not need or automatically delete
it. A published file whose manifest commit was interrupted may be downloaded
again and deduplicated. The local manifest is the progress authority.

This delivery stores originals and supported reader-derived PDFs locally. It does not
upload, import catalog data, classify language, expand archives, or run scheduled jobs.

### Deferred source: Belem.ru

2026-10-28: the owner deferred [Belem.ru](https://belem.ru/resources) for a later
retry because it is only partially reachable from this environment. Catalog and
[resource pages](https://belem.ru/node/8069), plus linked DOCX/PPTX endpoints,
returned HTTP 200, and bounded range requests returned HTTP 206. Complete page
and document transfers repeatedly stalled or timed out, commonly after roughly
15–19 KiB. A complete original was not validated. Partial bytes and valid file
signatures are not successful acquisition. No Belem adapter was implemented.

Retain the educational-resource catalog and the original literary/biographical
leads in the candidate inventory. Revisit once complete page and file retrieval
works; verify attachment language and distinguish direct documents from ZIP-only
and HTML-only resources before acquisition. This is an environment-specific access
observation, not a claim that the site is permanently unavailable.
