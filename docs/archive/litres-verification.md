# Historical Litres migration evidence

These notes were moved from the current source guide. Counts and temporary paths
are historical evidence, not current state or operating instructions. See the
[current Litres guide](../ingestion/litres.md) for supported behavior.

## Retired command names

The former `litres/cli.py` entry point has been removed.

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

## Previously recorded verification

Manual verification covered local legacy import, review export/sync/import,
missing-token errors, and offline PDF creation/reuse using synthetic input.
Authenticated acquisition and remote publishing were not exercised.

Manual checks used `/tmp/litres-verification.yaml` and the isolated artifact root
`/tmp/litres-cli-verification`. Repeated import retained the 527 original books
and 127 candidate decisions. Synthetic PDF and text inputs each finalized with
zero requests; the second invocation skipped both outputs. Compilation and
`git diff --check` passed. No automated tests were added.

After relocating helpers to `ingestion/`, manual CLI checks again covered source
listing, status, review export/sync, repeated import, and fresh offline PDF and
Markdown rebuilds followed by hash-based skipping. All ran against the isolated
verification root; no authenticated acquisition or publishing was attempted.
The unused legacy `litres/` code/configuration directory has been removed.
Credentials must be set in the selected operational YAML under `sources.litres`.
