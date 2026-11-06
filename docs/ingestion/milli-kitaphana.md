# Milli Kitaphana unified pipeline

Use `.venv/bin/python cli.py --config ingestion.yaml COMMAND --source milli_kitaphana`.
Provider helpers live in `ingestion/milli_kitaphana_*.py`; the old source directory
and standalone entry point have been removed.

Configuration belongs under `sources.milli_kitaphana` in the selected operational
YAML. Copy the placeholder section from `ingestion.example.yaml`. Existing key
names (`priv_key`, `sig_prefix`, `aes`, `yandex.disk`, `database_url`) are retained.
Configuration values are never loaded from a source-local file. Never commit real
credentials. The optional `limited_database_url` is the read connection for the
`mark-existing-limited` maintenance command; `database_url` remains the upstream
metadata insert connection.

`artifact_dir` overrides this source's artifact directory, relative to the YAML.
Without it, artifacts live under `<artifacts_root>/milli_kitaphana`. This workspace
uses `__artifacts/milli.kitaphana`, preserving all downloads, backups, subindexes
and recovery journals in place. To initialize the shared manifest, run:

```bash
.venv/bin/python cli.py --config ingestion.yaml import-state --source milli_kitaphana --from __artifacts/milli.kitaphana
```

The import requires `artifact_dir` to resolve to `--from`; it does not copy or move
originals. It imports the legacy index into the manifest and refreshes the index
as a compatibility projection. Repeating import preserves newer shared records.
Legacy `decrypted` remains historical completion state. A unique local PDF is
opened and hashed before being admitted as a finalized legacy output.

| Previous command | Root replacement |
| --- | --- |
| index | discover --source milli_kitaphana |
| download | download --source milli_kitaphana |
| decrypt | finalize --source milli_kitaphana, then publish --source milli_kitaphana --target yandex |
| split | split --source milli_kitaphana --parts N |
| merge-index PATH | merge-index PATH --source milli_kitaphana |
| recover.py | recover --source milli_kitaphana |
| mark_existing_limited.py | mark-existing-limited --source milli_kitaphana |

`discover` retains the Tatar, Arabic and collection queries, checkpoints pages,
and obeys `--max-pages`. `download` retains `--limited` and `--index-name`, and
acquires encrypted parts and metadata. `finalize` decrypts local inputs, assembles
PDFs atomically, and skips unchanged hashed inputs/outputs without network access.
Missing metadata requires another download. `run` composes discovery, download
and local finalization; it never publishes.

`publish --target yandex` uploads verified PDFs and inserts upstream metadata into
PostgreSQL using the existing clients. Each destination step is checkpointed per
record. A process failure after a remote operation but before its checkpoint can
require destination inspection before retrying, especially for insert-only SQL.

`split` retains `--parts`, `--dest`, `--prefix` and the repository-root `filter.json`.
`recover` retains `--report`, `--workers`, `--download`, `--retry-failed` and
`--download-workers`; its default journal is `_recovery/report.json`. Recovery
keeps its combined download/local assembly behavior and never publishes.
Source writers share a lock. Network operations use shared time/byte/retry limits;
provider transfers are serialized for consistent accounting. Recovery candidates
are capped by the configured item limit. `status` is read-only and needs no keys.
Use global `--summary-only` for compact results; detailed errors remain in the
reported summary JSON.

Manual verification used isolated `/tmp/milli-cli-check` artifacts: repeated
import, split, local encrypted PDF assembly with zero requests, and a second
finalization that skipped the verified output. Placeholder publishing credentials
were rejected. Original local settings were compared without printing values.
No automated tests were added. Live provider downloads and remote publication
require separate operational verification.

The bounded live catalog check reached the configured retry limit because the
provider certificate could not be verified in this environment. TLS verification
remains enabled. Live discovery/resume and acquisition remain unverified.
