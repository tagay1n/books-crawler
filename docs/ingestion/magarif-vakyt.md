# Мәгариф–Вакыт textbook packages

The publisher's electronic-format catalog is separate from the `magarif`
magazine archive. Add this entry under `sources` in your operational YAML:

```yaml
magarif_vakyt:
  archive_url: https://magarif-vakyt.ru/online2
```

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source magarif_vakyt --max-pages 1
.venv/bin/python cli.py --config ingestion.yaml download --source magarif_vakyt --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source magarif_vakyt
```

Discovery selects public Yandex Disk shares attached to publisher-labelled
«Әдәби уку», «Татар Теле», «Татар әдәбияты», «Туган телдәге әдәбият» and
«Әдәби ярдәмлек» cards. It follows both the electronic-format root and the
native `/reading` catalog. Use `--max-pages 2` to traverse both listings in one
invocation, or resume discovery afterward. Arabic textbooks, Google Drive links,
Bonboni readers and the publisher's other catalogs remain outside acquisition.
The titles establish admission context, not verified language of every file.
Each share is one source record, with its publisher title/link and Yandex name,
size, resource ID, timestamps, and checksums retained. `yadi.sk` aliases normalize
to `disk.yandex.ru`. No login, OAuth token, session export, or new dependency is
required. Both `/d/` and `/i/` public shares are supported. Metadata-only discovery
does not download original bytes. Per-record catalog context retains the actual
listing and raw title/link, independently of the API filename.

Downloads resolve a fresh temporary delivery URL through Yandex's public API,
verify source size/MD5/SHA-256, and retain unchanged PDF or ZIP originals under
`<artifacts_root>/magarif_vakyt/files/`. Signed URLs are excluded from persisted
metadata, transfer errors, and acquisition results. A changed upstream identity
requires rediscovery. `--limit` counts started publications, including retries or
local PDF reconstruction; already verified complete originals are skipped.
Direct PDFs bypass package processing and retain their supplied original bytes.

**2026-10-28 discovery expansion:** manual CLI traversal completed two catalogs
and 33 distinct resources: the previous 14 ZIPs plus 19 original literature and
methodology PDFs. The fifth-grade methodology PDF downloaded completely through
the CLI: 1,190,772 bytes / 70 pages, SHA-256
`249a2ddc3e1d8850fe36334fd81f41c6cf97c02749cef0868e43aa0a00c3934e`;
Yandex size, MD5 and SHA-256 matched, and sampled page 5 contains readable Tatar.
An isolated repeat skipped the PDF with zero requests. An existing verified ZIP
and derived PDF also replayed with zero requests; forcing its local assembly
checkpoint incomplete reused its existing derived result. Removing only the
isolated verification copy of the derived PDF then rebuilt it from the retained
ZIP, again without network access. A 1,000,000-byte per-file cap rejected the methodology PDF
before any requests. Evidence is under `__artifacts/session-20261028/`; remaining
PDF language/completeness and full acquisition remain unverified. Parser version
2 starts a fresh discovery scan while retaining historical observations and
the existing ZIP asset identities.

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
