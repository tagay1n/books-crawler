# Wikimedia Commons original documents

Add `sources.commons` from the example to the selected operational YAML:

```bash
.venv/bin/python cli.py --config config/sources/commons.yaml discover --source commons --max-pages 2
.venv/bin/python cli.py --config config/sources/commons.yaml download --source commons --limit 1
.venv/bin/python cli.py --config config/sources/commons.yaml run --source commons --max-pages 5 --limit 1
.venv/bin/python cli.py --config config/sources/commons.yaml status --source commons
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

`discover`, `download`, `run`, `publish`, and `status` are supported. PostgreSQL
stores observations, processing state, checkpoints, errors and S3 receipts;
local originals live under `__artifacts/ingestion/commons/`. A source-specific request
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
older local file. Unchanged completed files are skipped from recorded results;
`--recheck` verifies the local file and revalidates through normal HTTP conditional requests. Completed
originals survive interrupted runs. Existing discovery-only manifests can download
without rebuilding their inventory: version hints are derived from their retained
size and SHA-1 fields. Parser version 4 refreshes observations on the next discovery
and fixes canonical record URLs that previously contained literal configuration
code. Native `file:<id>` identities and download history remain unchanged.

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

## PostgreSQL, S3 and manual GitHub runs

Set `DATABASE_URL` and initialize the schema once with
`.venv/bin/python cli.py database init` before processing. There is no JSON-state
fallback. All returned file metadata, including unknown extended metadata fields,
credits, licenses and publisher/source descriptions, remains in PostgreSQL
observations under `upstream`; it is not replaced by an inferred bibliography.
See [database operations](../postgres-migration.md).

Set `S3_BUCKET` and standard AWS credentials for publication. `download` is local;
`run` downloads and uploads finished originals after committed checkpoints, while
retaining local files. Standalone `publish` retries from those files:

```bash
.venv/bin/python cli.py --summary-only --config config/sources/commons.yaml run --source commons --max-pages 2 --limit 1
.venv/bin/python cli.py --summary-only --config config/sources/commons.yaml publish --source commons --target s3 --limit 1
```

Shared publication uses deterministic keys and SHA-256 metadata, with receipts
in PostgreSQL. A fresh runner can skip published originals and reacquire missing
unpublished files. Missing files remain errors for standalone publication.

The **Ingest commons** GitHub workflow already supports manual dispatch using the
shared runner and `config/scheduled.yaml` limits. It has no scheduled trigger.
Required repository secrets are `DATABASE_URL`, `S3_BUCKET`, `AWS_ACCESS_KEY_ID`
and `AWS_SECRET_ACCESS_KEY`; `AWS_SESSION_TOKEN` is optional. Optional repository
variables are `S3_ENDPOINT_URL` and `AWS_DEFAULT_REGION`. Runner-local files are
temporary; PostgreSQL and S3 retain durable state and published originals.
See [runner operations](../scheduled-ingestion.md). No workflow dispatch or
production upload is required for verification of adapter changes.

## Bounded review, 2026-11-07 (Europe/Moscow)

Live API traversal completed five listing batches, 40 requests and 35 document
records (34 PDFs, one DjVu), with zero retries and no remaining frontier. The root
category exposed two image files, which were excluded; the Novels in Tatar
subcategory contained one image and no document candidates. This verifies the
configured category tree, not all Tatar books on Commons. The native category
page was also inspected independently of the API routes. All 35 API metadata
responses retained `extmetadata`; three originals exceed the local 100 MiB cap.
Reported original bytes total 1,443,157,280; these are not acquired-byte counts.

Fixed canonical record URL construction, which previously emitted literal
configuration code. Parser version 4 produced real `?curid=<id>` URLs on live
metadata without changing native identities. Original-source metadata and unknown
fields remain intact. Existing S3 publication, PostgreSQL checkpoint and manual
workflow integration were inspected rather than reimplemented.

One public original, «Ислам тарихы (Бикбулат)», was downloaded locally using the
shared HTTP transport and adapter MIME/size/SHA-1 validators: 247,549 bytes,
80 PDF pages, SHA-1 `9a4e29b6aa8512b8207eed58655d0b5ced409bd1`, SHA-256
`516173196319b27a3c748415eb21500a01e2a3be96e67db77254b7189a2a8dce`.
The rendered imprint page is Tatar; text extraction has legacy-font encoding
errors. This sample does not individually establish every candidate's language.
Manual inspection data and the original remain ignored under
`__artifacts/commons-review-20261107/` (`summary.json`, `records.json`, five
listing responses, `sample-verification.json`, and sample PDF/render).
These are review evidence, not operational state.

Compilation, configured API parsing, source capability listing, scheduled profile
loading and equality of the manual workflow to its generator output passed.
`git diff --check` passed. No automated tests were added. Live PostgreSQL
observations, checkpoint/resume, repeat-run skipping and S3 receipts could not be
verified because this shell has no database/storage credentials. No production
state, S3 objects or GitHub runs were changed. The download sample verifies
transport and integrity callbacks, not the full database-backed acquisition stage.
