# Fänni Tatarstan issue PDFs

`ftatarstan` uses the journal's new official OJS website, separately from the
IYALI electronic-library catalog. The previous `ft.antat.ru` domain published a
migration notice; its sampled live routes currently return 502. Configure:

```yaml
sources:
  ftatarstan:
    archive_url: https://ftatarstan.ru/index.php/ftat/ru/issue/archive
```

```bash
.venv/bin/python cli.py --config config/sources/ftatarstan.yaml discover --source ftatarstan --max-pages 3
.venv/bin/python cli.py --config config/sources/ftatarstan.yaml download --source ftatarstan --limit 1
.venv/bin/python cli.py --config config/sources/ftatarstan.yaml status --source ftatarstan
```

Discovery follows the native archive pager and issue title links, then resolves
advertised full-issue PDF viewers to their explicit original download links.
Native issue and galley identifiers are retained; redirects must preserve the
selected identity and remain on the configured HTTPS journal routes. No download
URL is guessed. Source title/date/DOI, raw galley language labels and catalog
context remain separate from actual file size, hashes and final download URL.

Only whole-issue galleys labelled `PDF (татарский)` are acquired, case-insensitively.
The website's Russian interface and Russian article titles do not determine PDF
language. Issues can contain Russian/English abstracts and references alongside
Tatar scientific text. Article PDFs and covers are excluded; missing full-issue
files remain metadata, and an unlabelled `PDF` galley remains unsupported. No
author registration or login is used; account navigation does not imply that
the anonymously downloadable originals require registration.

Manual CLI discovery on 2026-10-28 completed three archive pages and 51 issue
records, spanning source titles from 2014 through 2026: 49 full-issue PDF galleys,
48 explicitly Tatar-labelled and one unlabelled/held. Two issues have no full-issue
PDF in the inspected native contents (№ 4 of 2023 and № 2 of 2020).
CLI acquisition verified № 3 (2026): 8,714,023 bytes / 196 PDF pages, SHA-256
`d0db9116e265154bf764e61ed027837fb75364e8db513fed3937b97cf1a45a09`.
Extracted and rendered page 6 contains Tatar, Russian and English text. Its hash
matches the separate prior anonymous download. An isolated replay skipped the
verified original with zero requests. Evidence: ignored
`__artifacts/session-20261028/ftatarstan/` and session logs. Remaining PDFs and
printed-edition completeness remain unverified; no bulk acquisition was performed.

## Metadata and execution

Parser version 2 retains the issue contents as metadata: article titles, native
IDs/links, authors, page ranges, section labels and advertised article galley
labels/URLs. These article URLs are evidence only; the adapter never follows or
downloads them. It also retains listing/issue cover URLs, descriptions, raw issue
titles and full-issue attachment descriptors. Descriptions preserve HTML as source
evidence, not trusted renderable content. Covers remain metadata, not downloads.
After viewer resolution, attachment evidence includes the explicitly exposed
download URL and raw link. Native issue/galley identities and language selection
remain unchanged. Metadata-only issues have an explicit acquisition note;
unlabelled galleys remain unsupported even if their issue contents are retained.

PostgreSQL stores observations, frontier checkpoints, processing results, errors
and S3 receipts. Set `DATABASE_URL` and initialize the schema once using
`.venv/bin/python cli.py database init` before processing. Normal ingestion does
not initialize it or fall back to JSON. Originals remain under the configured
artifact root (`__artifacts/ingestion/ftatarstan/` by default). See
[database operations](../postgres-migration.md).

`download` retains originals locally. `run` downloads finished originals and
publishes to S3 after committed checkpoints, retaining local files. Standalone
`publish` retries from local files and reports missing originals:

```bash
.venv/bin/python cli.py --summary-only --config config/sources/ftatarstan.yaml run --source ftatarstan --max-pages 2 --limit 1
.venv/bin/python cli.py --summary-only --config config/sources/ftatarstan.yaml publish --source ftatarstan --target s3 --limit 1
```

Set `S3_BUCKET` and standard AWS credentials for publication. Shared publication
uses deterministic keys, SHA-256 metadata and PostgreSQL receipts. Fresh runners
reacquire missing unpublished files while receipts allow published originals to
be skipped. Unsupported galleys, article links and metadata-only issues are never
published as complete issue files.

The existing **Ingest ftatarstan** GitHub workflow supports manual dispatch using
the shared runner and `config/scheduled.yaml` limits. No scheduled trigger is
added. Initialize PostgreSQL before dispatch. Required repository secrets:
`DATABASE_URL`, `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. Optional:
`AWS_SESSION_TOKEN`; repository variables `S3_ENDPOINT_URL` and
`AWS_DEFAULT_REGION`. Runner-local files are temporary; PostgreSQL and S3 retain
durable state and published originals. See
[runner operations](../scheduled-ingestion.md) for budgets and recovery.

## Bounded review, 2026-11-07 (Europe/Moscow)

Independent homepage navigation links the configured archive. Live metadata
traversal completed three archive pages and 51 issue pages, with 55 HTTP requests
(one retry) and no remaining frontier. The pages expose 49 full-issue galleys:
48 explicitly Tatar-labelled and one held, unlabelled `PDF` for №3 (2018).
№4 (2023) and №2 (2020) still expose no full-issue galley. These cases remain
unsupported/metadata-only rather than being filled from article PDFs.

Parser version 2 was verified against all retained issue pages: 111 exposed
article cards retain title/link, author text when supplied, page ranges, section
and article-galley claims. Every retained contents count matches its corresponding
source article-card count. Many historical issues expose no article cards, so
this does not establish complete printed tables of contents. Empty source author
fields remain empty; authors are not inferred from PDF contents. Listing cover
URLs and issue attachment evidence are retained without cover acquisition.

One admitted viewer was resolved to its explicitly advertised original
`issue/download/51/50`; metadata retains both viewer and download evidence. The
bounded transfer acquired №3 (2026): 8,714,023 bytes, 196 PDF pages, SHA-256
`d0db9116e265154bf764e61ed027837fb75364e8db513fed3937b97cf1a45a09`,
matching the prior sample. Declared response length and PDF signature passed.
Rendered page 6 contains Tatar, Russian and English text; no per-page language
proportion or printed-completeness claim is inferred. Remaining viewer downloads
were not resolved or acquired in this audit; no bulk original acquisition occurred.

Evidence is ignored under `__artifacts/ftatarstan-review-20261107/`: three archive
bodies, 51 issue bodies, catalog/record/metadata summaries, resolved sample
metadata, and sample PDF/render/hash report. Individual inspection responses are
under `__artifacts/inspections/2026-11-06T21-48-*` (UTC). These review exports are
not operational state.

Compilation, capability listing, configured metadata parsing, archive traversal,
viewer resolution, scheduled profile loading, manual workflow generator equality
and `git diff --check` passed. No automated tests were added. The sample used
shared HTTP transport, native identity guards and format validation, not the full
database-backed acquisition stage. Database/storage credentials were unset, so
live PostgreSQL checkpoint/resume, repeat-run skipping and S3 upload/receipt
checks remain unverified. No production database writes, S3 objects or GitHub
workflow dispatch occurred.
