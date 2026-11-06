# DUM RT contemporary Tatar publications

`dumrt` covers two native publisher archives: «Дин вә мәгыйшәт» newspaper and
the contemporary «Шура» almanac. The latter is distinct from `kfu_shura`'s historical
collection. Configure the primary archive; discovery also follows the explicitly
selected almanac archive on the same publisher website:

```yaml
sources:
  dumrt:
    archive_url: https://dumrt.ru/media/din-va-magishet/
```

```bash
.venv/bin/python cli.py --config config/sources/dumrt.yaml discover --source dumrt --max-pages 40
.venv/bin/python cli.py --config config/sources/dumrt.yaml download --source dumrt --limit 1
.venv/bin/python cli.py --config config/sources/dumrt.yaml status --source dumrt
```

Use a YAML page cap of at least 40 for that discovery command, or use smaller
batches and resume. Native `curPos`/`cur_cc` pagination, issue cards and record
identifiers are retained. Only PDF links/objects in each record's attachment area
are acquired; related publications, covers and footer links are excluded. Older
launch announcements with no PDF remain metadata. Posting dates remain source
text and are not treated as printed issue dates: for example, almanac №51 was
posted in December 2025 but its PDF identifies January–March 2026.

The publisher's [activity report](https://dumrt.ru/netcat_files/multifile/2627/otchet_DUM_2018.pdf)
identifies both publication series as Tatar-language media. This series-level
claim and content samples establish admission; individual file composition is
not verified by the website's Tatar interface or a filename. Arabic quotations
and other languages can occur. Language evidence and raw source links remain in
metadata. The inspected originals download anonymously without registration or payment.

Requests stay on native HTTPS archive/record routes and original PDF storage.
Canonical record URL claims are checked when provided; legacy pages can omit
them. PDFs use `/netcat_files/`, `/files/pdf/` or the advertised legacy `/pdf/`
paths. A narrowly scoped repair removes one dangling quote after `.pdf` in legacy
`/files/pdf/` links, retaining the literal URL and `source_url_repair` evidence.
The inspected malformed target returned 403; its quote-free original returned a
complete Tatar newspaper PDF. Missing issue numbers and filenames are not guessed.

Final manual CLI discovery on 2026-10-28 completed 37 archive pages and 235 records,
exposing 227 PDF asset candidates with no remaining frontier or discovery errors.
Three isolated CLI acquisitions verified:

- Newspaper №12 (353), December 2024: 4,533,125 bytes / 16 pages, SHA-256
  `2b4f0dcec0bc1391c9797513bbc9cfd46813496e9f2d255a6cd16aba6fde253c`.
- Almanac №54: 6,259,590 bytes / 130 pages, SHA-256
  `d2aaefdc1f7e5a59ef3daf6f61a0cb1b16a31d32c926bad84894a2e7830c0c4e`.
- Repaired 2013 newspaper №7 (202): 8,375,447 bytes / four pages, SHA-256
  `6b2b92c710bf318fcc9065e87a4788178dd65e316ddc1967a8e3917c5772f0a0`.

Rendered samples contain Tatar text; old files can have legacy-font extraction
errors. A repeat skipped all three originals with zero requests. Separate manual
samples also verified the 2011 legacy storage path and almanac №51. Evidence is
under `__artifacts/session-20261028/`, with CLI samples under `dumrt-samples/`.
The full discovery manifest's files remain pending; sample acquisitions use an
isolated manifest. Full-file availability, language composition of remaining
files and printed-edition completeness are unverified. No bulk acquisition,
archive expansion, PDF assembly or original-file modification is introduced.

## Metadata and execution

Parser version 3 additionally preserves the issue description HTML, relevant
HTML meta tags, raw title, attachment size labels and listing cover URLs. The
original links, link labels, quote-repair evidence and series-language claim are
retained in observations. Size labels such as `6 МБ` remain source text rather
than exact byte counts. Missing-PDF issues have an explicit `acquisition_note`;
they are not treated as downloaded editions. Raw HTML is evidence, not trusted
renderable content. Cover images remain metadata and are never downloaded as PDFs.
Native series/issue identities and file-selection rules remain unchanged.

PostgreSQL stores upstream metadata observations, discovery frontier/checkpoints,
processing results, errors and S3 receipts. Set `DATABASE_URL` and initialize the
schema once with `.venv/bin/python cli.py database init`; processing does not
initialize it or fall back to JSON. Originals remain under the configured local
artifact root (`__artifacts/ingestion/dumrt/` by default). See
[database operations](../postgres-migration.md).

`download` keeps originals locally. `run` uses shared committed checkpoints to
download and upload finished originals to S3, retaining local files. Standalone
`publish` retries from local files and reports missing originals:

```bash
.venv/bin/python cli.py --summary-only --config config/sources/dumrt.yaml run --source dumrt --max-pages 2 --limit 1
.venv/bin/python cli.py --summary-only --config config/sources/dumrt.yaml publish --source dumrt --target s3 --limit 1
```

Set `S3_BUCKET` and standard AWS credentials for publication. Deterministic object
keys, SHA-256 metadata and PostgreSQL receipts support retrying publication;
fresh runners reacquire missing unpublished files while completed receipts allow
published originals to be skipped. No metadata-only issue or cover is published
as a document.

The existing **Ingest dumrt** GitHub workflow supports manual dispatch using the
shared runner and `config/scheduled.yaml` limits. No scheduled trigger is added.
Initialize the database before dispatch. Required repository secrets:
`DATABASE_URL`, `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. Optional:
`AWS_SESSION_TOKEN`; repository variables `S3_ENDPOINT_URL` and
`AWS_DEFAULT_REGION`. Runner-local files are temporary; PostgreSQL and S3 retain
durable progress and published originals. See
[runner operations](../scheduled-ingestion.md) for budgets and recovery.

## Bounded review, 2026-11-07 (Europe/Moscow)

Native homepage navigation independently advertises both selected archives. A
bounded live listing traversal completed 37 pages/37 requests, no retries and no
remaining frontier, discovering 235 unique issue URLs: 187 newspaper records and
48 almanac records. This was listing enumeration, not a fresh verification of
every issue or attachment; the historical 227-asset count above was not refreshed.
Four sampled records covered current newspaper/almanac pages, the 2011 newspaper
and a metadata-only almanac launch announcement. Three exposed PDFs; the launch
announcement correctly exposed none. Current almanac metadata preserves its
publisher `6 МБ` size claim and seven Open Graph properties. Native pagination
and cross-series traversal remain unchanged.

A bounded original transfer of newspaper №12 (353), December 2024, acquired
4,533,125 bytes with complete declared length and a valid PDF signature. SHA-256
`2b4f0dcec0bc1391c9797513bbc9cfd46813496e9f2d255a6cd16aba6fde253c`
matches the earlier sample; `pdfinfo` reports 16 pages and rendered page 2 contains
Tatar text. Other files' composition and printed-edition completeness remain
unverified. No bulk original acquisition was performed.

Evidence is ignored under `__artifacts/dumrt-review-20261107/`: 37 listing bodies,
`catalog.json`, `summary.json`, four parsed `records.json` entries, and the sample
PDF/render/hash report. Individual HTTP inspection responses are under
`__artifacts/inspections/2026-11-06T21-36-*`, `2026-11-06T21-39-*` and
`2026-11-06T21-40-*` (UTC). Review exports are not operational state.

Manual metadata/file selection and listing traversal checks passed, along with
compilation, capability listing, scheduled profile loading, manual workflow
generator equality and `git diff --check`. No automated tests were added. The
sample download used shared HTTP transport, native guards and format validation,
not the full database-backed acquisition stage. Live PostgreSQL resume,
repeat-run skipping and S3 upload/receipt verification remain unavailable because
database/storage credentials are unset. No production state writes, S3 uploads
or GitHub workflow dispatch occurred.
