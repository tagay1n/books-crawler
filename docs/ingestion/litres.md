# Litres unified pipeline

Use `.venv/bin/python cli.py --config ingestion.yaml COMMAND --source litres`.
Copy the Litres source section from `ingestion.example.yaml` into your selected
operational YAML. Set `sources.litres.sid` to your Litres SID cookie. Source
settings are never loaded from `litres/config.yaml`. Relative artifact roots
resolve against the operational YAML; all Litres state lives beneath its
`litres/` directory. Never commit credentials.

The old `litres/cli.py` entry point has been removed. Command replacements:

| Previous command | Root command |
| --- | --- |
| index | discover --source litres |
| discover | discover --source litres --mode candidates |
| export-candidates-review | review --source litres --action export |
| sync-candidates-review | review --source litres --action sync |
| import-candidates | review --source litres --action import |
| pdf | download --source litres --format pdf; then finalize --source litres |
| text | download --source litres --format text; then finalize --source litres |
| metadata | metadata --source litres |
| upload | publish --source litres --target yandex |
| hf | publish --source litres --target hf |
| s3-media | publish --source litres --target s3-media |

`run --source litres --limit 1 --max-pages 1` discovers, acquires, and finalizes
local outputs. `download` saves images or decoded text fragments and media;
`finalize` verifies input hashes and creates PDFs or Markdown without network or
a browser. Repeated finalization skips unchanged verified output. A missing or
changed input must be downloaded again. `--recheck` refreshes acquisition inputs.
Review and publishing are explicit and never run automatically.

Use `import-state --source litres --from __artifacts/litres` before acquisition
to import the old book/candidate indexes and review TSV. Originals remain
untouched. Valid referenced PDFs/Markdown are copied and hashed; missing files
remain eligible for acquisition. Imported outputs do not establish complete
source-image/text inventories. Repeating import preserves existing records and
review decisions. Inspect `status --source litres` for stage counts and review
status. It performs no writes or network requests and requires no SID.

Review statuses remain `candidate`, `accepted`, `rejected`, and `maybe`.
Broad discovery (`--mode candidates` or `all`) preserves the existing language
filters and scoring. Only accepted candidates are admitted by review import.
The manifest is authoritative; books-index.json is a compatibility projection
for reused provider components. Review candidates and TSV are separate local
artifacts in the same source directory.

Publishing retains existing destination behavior: Yandex Disk plus monocorpus,
the `yasalma/tt-litres-books` Hugging Face dataset, and S3 media exports.
Set `sources.litres.yandex.oauth_token` or the `sources.litres.s3` mapping as
needed; HF uses its normal SDK credentials. Publishing requires verified local
outputs and never runs during normal verification. Remote operations can have
partial effects; inspect the destination before retrying an interrupted publish.

## Verification and current limits

Use global `--summary-only` for compact JSON. Run summaries retain detailed
errors. Missing SID fails before acquisition writes. Downloads use shared byte,
file, item, disk, retry and deadline limits. Browser navigation has page-load
timeouts and deadline checks, but browser-internal traffic is not byte-accounted.
Browser fallback and authenticated endpoints require live verification with a
valid SID. Catalog completion relies on native pagination links; missing cards
or repeated batches are errors. Candidate search checkpoints completed pages; a completed campaign restarts on
the next invocation. Publishing checkpoints destination-level
completion, not individual remote objects.

Manual verification covered local legacy import, review export/sync/import,
missing-token errors, and offline PDF creation/reuse using synthetic input.
Authenticated acquisition and remote publishing were not exercised.

Manual checks used `/tmp/litres-verification.yaml` and the isolated artifact root
`/tmp/litres-cli-verification`. Repeated import retained the 527 original books
and 127 candidate decisions. Synthetic PDF and text inputs each finalized with
zero requests; the second invocation skipped both outputs. Compilation and
`git diff --check` passed. No automated tests were added.
