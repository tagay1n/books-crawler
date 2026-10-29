# Tatar Galyame educational catalog

Autonomous CLI coverage on 2026-10-29 completed all 34 category responses and
279 visible resources with no unresolved errors: 128 eligible hosted documents
under the existing all-language policy, plus unsupported attachments/references.
A newly verified `Туган_тел_буларак_татар_теле.pptx` original is 150,316 bytes,
SHA-256 `d74d592b6b872a8b63eaedb39192759ae71f6daea17460ff7d7b4ae47e9c36ed`.
Its container has 13 slide XML parts, with readable Tatar on inspected slides
1–3. This is a text/container inspection, not rendered-slide verification.
An isolated repeat skipped the verified original with zero requests. Evidence:
`__artifacts/session-20261028/galyame-pptx/`. The remaining documents' languages
are unverified; catalog counts do not establish 128 Tatar originals.

`tatargalyame` is separate from the `repo.kpfu.ru` sources. Select the operational
YAML entry from `ingestion.example.yaml`, using exactly
`https://tatargalyame.kpfu.ru/catalogue`. The older `/en/catalogue` inventory link
returned HTTP 404 during inspection; `/catalogue` and the public JSON API returned
HTTP 200 through direct HTTP, even when the browsing tool could not open the site.

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source tatargalyame --max-pages 15
.venv/bin/python cli.py --config ingestion.yaml download --source tatargalyame --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source tatargalyame --max-pages 15 --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source tatargalyame
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
