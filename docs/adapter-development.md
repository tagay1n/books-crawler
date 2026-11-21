# Adapter development map

Follow `AGENTS.md`: no automated tests; use code inspection and bounded manual CLI
verification with `.venv/bin/python`. Read only the files relevant to the task.

## Start with bounded state

```bash
.venv/bin/python scripts/ingestion_overview.py --database --source magarif
.venv/bin/python cli.py database records --source magarif --limit 10
.venv/bin/python cli.py database record --source magarif --key RECORD_KEY --assets 3
.venv/bin/python cli.py database errors --source magarif --limit 10
.venv/bin/python cli.py database last-run --source magarif
```

PostgreSQL is authoritative. Start with the overview, then select a view for the
specific question. These commands use the [same database selection rules](ingestion/operations.md#per-source-configuration).
Use `--field title --field url` to select metadata and `next_after` with `--after`
to page records. File arguments to the overview inspect archived snapshots.
Read individual evidence only when a summary calls for it. Never dump private
configs or full manifests. See [implementation contracts](ingestion-architecture.md#bounded-inspection-routing-and-checkpoints)
for preview limits and SQL projections.

## Find the code

Select one source to find its adapter, helper, guide and configuration paths.
Narrow provider definition lookups with `--module` and `--symbol` before opening
the matched lines. Use `rg -n` in the shared module or other adapter when the
implementation lives outside the provider's filename prefix.

```bash
.venv/bin/python cli.py sources --details --source litres
.venv/bin/python cli.py sources --source litres --module litres_text --symbol _markdown_output_name
rg -n '^def select_tatar\(' ingestion/kfu.py
git grep -n -e 'catalog_registered' -- ingestion/ scripts/ docs/ingestion/milli-kitaphana.md
```

| Task | Open first |
| --- | --- |
| Adapter hooks and signatures | [Adapter interface](adapter-interface.md) |
| Source-specific behavior | [Source index](local-ingestion.md), then its guide and adapter |
| Registry/capabilities | `ingestion/registry.py`, `commands.py`; keep registry imports lazy |
| CLI and compact output | `ingestion/cli.py`, `output.py` |
| Discovery/resume | `ingestion/discovery.py`, `paging.py` |
| Active/historical errors | `ingestion/diagnostics.py` |
| Acquisition and recovery | `ingestion/core.py`, `network.py`, `state.py`, `paths.py` |
| Local-file integrity, space and signatures | `ingestion/files.py` |
| Transactions/checkpoints | `ingestion/checkpoints.py`; see [contracts](ingestion-architecture.md) |
| Read-only JSONB projections | `ingestion/sql_views.py`, `state_inspection.py`, `overview.py` |
| Native metadata projections and updates | `ingestion/native_records.py` |
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

Use a dedicated ignored configuration and artifact root. For example, prepare
`config/local/magarif.verify.yaml` with a scratch `database.url` and set
`artifacts_root: ../../__artifacts/verify-magarif` in that file.

```bash
.venv/bin/python cli.py magarif --config config/local/magarif.verify.yaml --summary-only discover --max-pages 1
.venv/bin/python cli.py magarif --config config/local/magarif.verify.yaml --summary-only download --limit 1
```

For acquisition changes: discover, acquire a bounded original, inspect format and
language, then repeat to verify skipping. Check resume/failure behavior when those
paths change. Serialize writers for the same source. Do not run bulk acquisition
or remote publication just to verify a code change.

Compile changed modules and run `git diff --check`. Report scope, compact results,
evidence paths and remaining limitations. Keep originals and credentials out of Git.
For stage/routing/configuration changes, read the [implementation contracts](ingestion-architecture.md).
