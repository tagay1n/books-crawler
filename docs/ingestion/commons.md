# Wikimedia Commons original documents

Add `sources.commons` from the example to the selected operational YAML:

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source commons --max-pages 2
.venv/bin/python cli.py --config ingestion.yaml download --source commons --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source commons --max-pages 5 --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source commons
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
