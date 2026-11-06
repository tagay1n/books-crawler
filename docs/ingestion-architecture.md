# Ingestion implementation contracts

Read the [adapter map](adapter-development.md) first; open this for stage,
checkpoint, routing or configuration changes. For operators, use
[shared operations](ingestion/operations.md).

## Unified stage contract

New adapters and future migrations should expose source-neutral root commands:
`discover`, `download`, `finalize`, `run`, `status`, with optional `metadata`,
`review`, `publish`, and `import-state` capabilities. Litres is the first full
pipeline reference; see [its guide](ingestion/litres.md) and `ingestion/litres.py`.
Provider helpers live alongside the adapter in `ingestion/litres_*.py`; processing
state uses the active Postgres-backed runtime. Reserve `state.atomic_json` for
document content and explicitly requested exports. The registry stays lazy. Source-specific operational options belong under
`sources.<source>`; command routing must reject unsupported capabilities.

Discovery stores resumable source evidence and admission decisions. Download
acquires original inputs and required media within shared budgets. Finalization
uses verified local inputs without credentials/network, records recipe/input
provenance, and atomically publishes derived outputs. Run composes the local
stages and automatic S3 publication at committed checkpoints. Review and legacy
publication targets remain explicit. Status is read-only.
The manifest owns record state; any compatibility index is a projection.

Other providers currently combining acquisition and assembly retain their
behavior. Migrate them toward these separate stages incrementally; do not change
their run semantics incidentally while implementing a new adapter. Source
writers must share a lock, checkpoint progress, and produce structured summaries.
Keep verification manual/CLI-based; do not add automated tests.

## Bounded inspection, routing and checkpoints

```bash
.venv/bin/python cli.py sources --details --source magarif
.venv/bin/python cli.py database records --source magarif --limit 10
.venv/bin/python cli.py database record --source magarif --key RECORD_KEY --assets 3
.venv/bin/python cli.py database errors --source magarif --limit 10
.venv/bin/python cli.py database last-run --source magarif
.venv/bin/python scripts/ingestion_overview.py --database --source magarif
```

These database commands are read-only and do not need operational YAML. Record views
omit histories and bound metadata; `--field title --field url` selects metadata fields.
`_truncation` reports omitted fields/items/characters and preview-budget stops.
`--assets` selects up to 100 candidate asset previews, subject to the displayed preview
budget. Record listing returns complete keys, bounded titles and completion hints;
use its `next_after` value with `--after` to continue. CLI limits range from 1–100.
Error views distinguish active discovery, historical discovery and last-run errors,
with a total preview limit of 1–100. Full evidence stays in PostgreSQL.
The overview processes sources individually; snapshot paths inspect archived state only.
Compact CLI results include S3 counts and up to three 500-character error previews.
Nested provider fields also share a bounded preview budget with omission indicators.
Status uses one read-only PostgreSQL snapshot projected to latest observations/results,
with a SQL aggregate for historical result counts; it establishes no write baseline.
The same snapshot serves provider status and publication counts.
`ingestion/paths.py` resolves source directories for native runtimes and all core stages,
including Common Crawl's custom artifact directory during status.

`ingestion/commands.py` defines typed invocation options and shared capability validation.
Operational `Settings.source_options` contains source configuration, not invocation flags.
Plain source listing remains lazy; detailed listing imports only selected adapters to resolve capabilities.

`ingestion/checkpoints.py` coordinates explicit progress commits and post-commit work.
Pass the coordinator through runtimes/manifests; use `Manifest.checkpoint()` for progress
boundaries. `Manifest.save()` and `Repository.save()` only persist state. Receipt and
explicit import writes must use persistence-only saves. The core injects S3 publication
only for `run`, retaining one upload budget across its checkpoints; standalone publication
still reconciles receipts and pending outputs. Never call publication from repository saves.
See [historical verification](archive/implementation-verification.md).

## Litres PDF code map

`litres_pdf.py` retains acquisition orchestration and compatibility helper imports.
`litres_browser.py` owns authenticated fetching, challenge fallback and response diagnostics.
`litres_pdf_assembly.py` owns local image validation/encoding and atomic PDF assembly;
`litres_pdf_config.py` validates PDF and browser settings. Keep transport out of assembly.

## Operational configuration

Select `config/sources/<source>.yaml` explicitly. Shared values live in
`config/defaults.yaml`; source-specific options, including native helper options,
are always passed in `Settings.source_options`. Do not introduce operational
literal defaults in Python. Add public values to the selected YAML instead;
retain parser/protocol constants and intentional library defaults in code.

Legacy helper functions use `runtime_config.option(module, key)` inside the
invocation established by `core.run`; never read these values at module import
time. Function defaults depending on configuration resolve inside the function.
Use `ConfiguredThreadPoolExecutor` for helper workers needing this invocation
context. Plain source listing must continue to work without configuration,
credentials or provider imports. See the [operations guide](ingestion/operations.md) for inheritance,
environment references and migration of private combined files.
