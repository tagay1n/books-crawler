# KFU «Азад халык» newspaper

`kfu_azad_halyk` selects <https://repo.kpfu.ru/jspui/handle/net/27528> and keeps
its own PostgreSQL state and local originals under
`__artifacts/ingestion/kfu_azad_halyk/`. Use the checked-in operational YAML.

```bash
.venv/bin/python cli.py --config config/sources/kfu_azad_halyk.yaml discover --source kfu_azad_halyk --max-pages 2
.venv/bin/python cli.py --config config/sources/kfu_azad_halyk.yaml download --source kfu_azad_halyk --limit 1
.venv/bin/python cli.py --config config/sources/kfu_azad_halyk.yaml run --source kfu_azad_halyk --max-pages 2 --limit 1
.venv/bin/python cli.py --config config/sources/kfu_azad_halyk.yaml status --source kfu_azad_halyk
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
those files. The selected YAML sets `direct_files_only: true`: image-reader
enumeration and PDF assembly are disabled for this source, including when a
future issue exposes only page images. Such readers remain unsupported metadata.
The other KFU collection configurations keep their existing reader behavior.

Manual CLI verification completed discovery of all 15 records, with the final
advertised count verified and no discovery errors. All 15 had `tt` labels and one
eligible public PDF each. A bounded `run --max-pages 2 --limit 1` downloaded
`net/27569` (`№ 15, 1906`) as an unchanged eight-page PDF of 8,466,638 bytes,
recording SHA-256 `24b2ab8292b4ff31150d1d93ee28e9033870f4e5eedc1b02188967c503256bfd`
and MD5 `ff0560df9b939d12abf599a638f998ec`. Fourteen files remain pending.
An isolated repeat using the completed record reused its verified local original
with zero HTTP requests. Compilation and diff checks passed; no automated tests
were added.

## File-only policy, metadata and execution

For custom operational YAML, add `sources.kfu_azad_halyk.direct_files_only: true`
alongside `collection_id: '27528'` and `tatar_only: true`. The optional collection
setting accepts a boolean only; omission preserves legacy KFU reader behavior.
Direct-only observations use parser version 4 and record `acquisition_policy`
plus eligible-document/held-entry counts. DC metadata, raw bibliography, source
dates/series, file inventories and restrictions remain preserved. Native handles
and bitstream identities are unchanged; unchanged originals remain reusable.

Direct-only resolution never enumerates readers, and download never invokes image
assembly. S3 inventory also filters previously assembled record outputs when the
setting is enabled, including before metadata has been refreshed. Direct document
assets remain eligible. No HTML text extraction or document conversion occurs.

PostgreSQL stores observations, frontier checkpoints, processing results, errors
and S3 receipts. Set `DATABASE_URL` and initialize the schema once with
`.venv/bin/python cli.py database init`; processing does not initialize it or fall
back to JSON. See [database operations](../postgres-migration.md).

`download` is local. `run` downloads and uploads finished original documents to S3
after committed checkpoints while retaining local files. Standalone `publish`
retries from local files and reports missing originals:

```bash
.venv/bin/python cli.py --summary-only --config config/sources/kfu_azad_halyk.yaml run --source kfu_azad_halyk --max-pages 2 --limit 1
.venv/bin/python cli.py --summary-only --config config/sources/kfu_azad_halyk.yaml publish --source kfu_azad_halyk --target s3 --limit 1
```

Set `S3_BUCKET` and standard AWS credentials for publication. Shared S3 transfer
uses deterministic keys, SHA-256 metadata and PostgreSQL receipts. Fresh runners
reacquire missing unpublished files; receipts allow published originals to be
skipped. Restricted files are never requested and metadata-only entries are not
published as documents.

The existing **Ingest kfu_azad_halyk** workflow supports manual dispatch through
the shared runner and `config/scheduled.yaml` limits. No schedule is added.
Initialize PostgreSQL before dispatch. Required repository secrets:
`DATABASE_URL`, `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`. Optional:
`AWS_SESSION_TOKEN`; repository variables `S3_ENDPOINT_URL` and
`AWS_DEFAULT_REGION`. Runner-local files are temporary; PostgreSQL and S3 retain
durable state and published originals. See
[runner operations](../scheduled-ingestion.md).

## Bounded review, 2026-11-07 (Europe/Moscow)

Live traversal inspected the collection listing, all 15 item pages and a final
count-verification response: 17 requests, no retries, no remaining frontier, and
15 records matching the advertised count. All 15 have explicit `tt` labels and
one eligible public direct PDF. Fifteen restricted ZIP blocks remain inventory
evidence and were never requested. Source DC tags, raw bibliography and file
descriptions remain in the saved observations; no filename or URL was guessed.

One bounded original download reverified `net/27569`, №15 (1906): 8,466,638 bytes,
eight PDF pages, SHA-256
`24b2ab8292b4ff31150d1d93ee28e9033870f4e5eedc1b02188967c503256bfd`,
MD5 `ff0560df9b939d12abf599a638f998ec`, matching the prior sample. Native bitstream
identity, declared length and PDF signature passed; rendered page 3 is a
historical Arabic-script scan. No language-composition or printed-completeness
claim was inferred from the render. These are local hashes, not repository
checksum matches. The other 14 PDFs were not freshly acquired.

A read-only helper check using the existing public manuscript `net/27026`
confirmed that direct-only resolution holds its reader as `reader_policy_excluded`
without reader/manifest requests or image enumeration. This was helper-policy
verification, not admission of that manuscript to the Азад халык collection.
A manual in-memory publication projection with a prior assembled-result scenario
retained the real original and excluded the assembled output in direct-only mode.
No such scenario was written to production state. Configuration inspection
confirmed the other four KFU collection configurations retain parser version 3
and their reader behavior; non-boolean policy values are rejected.

Evidence is ignored under `__artifacts/kfu-azad-halyk-review-20261107/`: listing,
15 item responses, count verification, records/summary exports, reader-policy and
publication-projection reports, and sample PDF/render/hash report. These are review
exports, not operational state. Compilation, capability/configuration checks,
scheduled profile loading, manual workflow generator equality and `git diff --check`
passed. No automated tests were added. The sample used shared HTTP guards and
format validation, not the full database-backed acquisition stage. Credentials
were unset, so live PostgreSQL resume, repeat-run skipping and S3 receipts remain
unverified. No production state writes, uploads or workflow dispatch occurred.
