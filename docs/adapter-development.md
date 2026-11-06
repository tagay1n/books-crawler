# Adapter development map

Follow `AGENTS.md`: no automated tests; use code inspection and bounded manual CLI
verification with `.venv/bin/python`. Read only the files relevant to the task.

## Start with bounded state

```bash
.venv/bin/python cli.py sources --details --source magarif
.venv/bin/python scripts/ingestion_overview.py --database --source magarif
.venv/bin/python cli.py database records --source magarif --limit 10
.venv/bin/python cli.py database record --source magarif --key RECORD_KEY --assets 3
.venv/bin/python cli.py database errors --source magarif --limit 10
.venv/bin/python cli.py database last-run --source magarif
```

PostgreSQL is authoritative. These database views are read-only, need no operational
YAML, and bound their previews. Use `--field title --field url` to select metadata;
use `next_after` with `--after` to page records. Read individual evidence only when
summaries identify a concrete question. Never dump private configs or full manifests.
File arguments to the overview inspect archived snapshots only. Database overviews
use SQL counts, projected scan state and streamed errors rather than loading record
or asset histories. Detailed error groups are lists of `{message, count}` ordered
by frequency and message; previews bound both text and group counts and report
omissions with `_truncation`.

## Find the code

`cli.py sources --details --source NAME` includes repository paths for the adapter,
provider helpers, source guide and configuration without importing providers.

| Task | Open first |
| --- | --- |
| Adapter hooks and signatures | [Adapter interface](adapter-interface.md) |
| Source-specific behavior | [Source index](local-ingestion.md), then its guide and adapter |
| Registry/capabilities | `ingestion/registry.py`, `commands.py`; keep registry imports lazy |
| CLI and compact output | `ingestion/cli.py`, `output.py` |
| Discovery/resume | `ingestion/discovery.py`, `paging.py` |
| Active/historical errors | `ingestion/diagnostics.py` |
| Acquisition and recovery | `ingestion/core.py`, `network.py`, `state.py`, `paths.py` |
| Transactions/checkpoints | `ingestion/checkpoints.py`; see [contracts](ingestion-architecture.md) |
| Publication | `ingestion/publication.py`; see [S3 behavior](ingestion/operations.md#s3-publication) |
| Config inheritance | `ingestion/config.py`, `runtime_config.py`; [operations](ingestion/operations.md#per-source-configuration) |
| Language admission | `ingestion/languages.py`, `language_reviews.py`, then provider policy |
| Candidate qualification | `ingestion/inspection.py`; [bounded inspection](source-inspection.md) |
| Common Crawl | `ingestion/common_crawl.py`, `common_crawl_*.py`; [guide](ingestion/common-crawl.md) |
| Native pipeline reference | `ingestion/litres.py`, `litres_*.py`; [contracts](ingestion-architecture.md) |
| Periodic discovery audit | [Review register and checklist](source-discovery-reviews.md) |
| Actions/runtime budgets | [Scheduled operations](scheduled-ingestion.md) |

Reuse shared streaming, signatures, retries, hashes, atomic output, locks and
repeat-run skipping. `network.install_native_get_guard` shares native URL and
redirect checks while providers retain their allowlists. Reuse SHA-256-pinned
language reviews when item-language claims are absent; subject/interface language
is insufficient. Tatkniga and Internet Archive retain provider-specific admission.

## Verify changes

Use a dedicated ignored artifact root and explicit `config/sources/<source>.yaml`.
For acquisition changes: discover, acquire a bounded original, inspect format and
language, then repeat to verify skipping. Check resume/failure behavior when those
paths change. Serialize writers for the same source. Do not run bulk acquisition
or remote publication just to verify a code change.

Compile changed modules and run `git diff --check`. Report scope, compact results,
evidence paths and remaining limitations. Keep originals and credentials out of Git.
For stage/routing/configuration changes, read the [implementation contracts](ingestion-architecture.md).
