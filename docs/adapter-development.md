# Adapter development map

Read `AGENTS.md` first: do not add automated tests. Use code inspection and bounded
manual CLI verification. Use `.venv/bin/python`; the shell's default Python may
belong to another project.

For periodic discovery audits, use the
[source discovery review register](source-discovery-reviews.md) for source
selection, the review checklist, and recording findings and review dates.

## Find the relevant code without a full repository tour

- `ingestion/registry.py`: registered sources; check before proposing a new
  adapter. `ingestion/config.py` validates explicitly selected operational YAML.
  The registry is a lazy mapping: listing/checking names imports no providers;
  lookup loads and caches only the selected module or KFU collection instance.
- `ingestion/common_crawl.py`: Common Crawl/FinePDFs stage dispatch. Its
  `common_crawl_*.py` helpers retain the native Postgres record layout and the
  existing result/cache paths; see [usage](ingestion/common-crawl.md).
- `ingestion/discovery.py` and `paging.py`: durable listing frontier, per-record
  context, pagination fingerprints and resume checkpoints. Incomplete scans
  resume; calling discovery after completion starts a new scan.
- `ingestion/diagnostics.py`: shared current-scan versus historical error scoping
  for discovery, CLI status and the read-only overview. Legacy diagnostics are
  classified without rewriting a manifest during a status command.
- `ingestion/core.py`, `network.py`, `state.py`: reuse bounded streaming, format
  signatures, atomic publication, retry budgets, observations, hashes,
  source locks and repeat-run skipping. Do not duplicate these in adapters.
  `network.install_native_get_guard` shares read-only native URL and redirect
  checks; callers retain their own allowlist and optional delivery equivalence.
- `ingestion/language_reviews.py`: reuse SHA-256-pinned manual language reviews
  when reliable item-language claims are absent. A subject or interface locale
  does not establish document language.
- `ingestion/languages.py`: exact-label classification shared by KFU, KFU DSpace,
  Tataroved and file reviews. Publisher-specific tokenization/admission in
  Tatkniga and Internet Archive remains separate.
- `ingestion/output.py` and global `--summary-only`: compact JSON counts and
  artifact paths without progress logs. Use this for agent-driven CLI runs.
- `ingestion/inspection.py` and `cli.py inspect`: bounded public-page evidence,
  link extraction and optional PDF-prefix probes. Use this instead of custom
  fetch scripts; see [inspection usage](source-inspection.md).
- `docs/local-ingestion.md`: short index of per-source guides under
  `docs/ingestion/`. Open the selected guide rather than reading every adapter.
- `ingestion/yazuchy.py`: direct PDFs and manual reviews. `echovek.py`:
  archive-to-issue-to-article traversal. `sarhaan.py`: language claims and
  individual files behind native redirects.

## Inspect state efficiently

Authoritative state now lives in PostgreSQL; see [migration and setup](postgres-migration.md).
Use `.venv/bin/python scripts/ingestion_overview.py --database` for current state.
The file-based examples below inspect archived snapshots only.


```bash
.venv/bin/python scripts/ingestion_overview.py __artifacts/ingestion
.venv/bin/python scripts/ingestion_overview.py __artifacts/session-20261028
.venv/bin/python scripts/ingestion_overview.py --details __artifacts/session-20261028/kfu_repository
.venv/bin/python cli.py --summary-only --config config/sources/kfu_repository.yaml status --source kfu_repository
```

The helper reads selected roots' immediate source manifests only, emits one JSON
line per manifest, and never opens configurations, modifies artifacts or makes
network requests. Explicit source directories and manifest paths also work.
Operational checkpoints commit observations and frontier progress together in PostgreSQL.
Use the shared manifest APIs to maintain asset ownership indexes.
Discovery completeness is distinct from advertised-count verification and from
download completion. `--details` adds current-scan counts (distinct from total
retained records), advertised-count verification, asset formats and grouped
discovery error messages without large continuation URLs or record contents.
`discovery_errors` counts active diagnostics; `historical_discovery_errors`
counts prior-scan and resolved diagnostics. `--details` groups both separately.
Inspect individual observations only when a summary points
to a concrete question; avoid dumping complete manifests or private configs.

## Verify and hand off

Use a dedicated ignored artifact root and explicit operational YAML. Run
discovery, acquire a bounded original, inspect its format and content language,
then repeat acquisition to verify hash-based skipping. Exercise resume or failure
behavior when changing those paths. Serialize commands writing the same source;
different sources have independent locks. Compile changed modules and run
`git diff --check`. Record scope, evidence, remaining frontier and commands in a
short work log; commit only relevant paths or hunks. Keep originals out of Git.

## Unified stage contract (Litres reference)

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
stages; review and remote publication remain explicit. Status is read-only.
The manifest owns record state; any compatibility index is a projection.

Other providers currently combining acquisition and assembly retain their
behavior. Migrate them toward these separate stages incrementally; do not change
their run semantics incidentally while implementing a new adapter. Source
writers must share a lock, checkpoint progress, and produce structured summaries.
Keep verification manual/CLI-based; do not add automated tests.

## Shared S3 publication

All sources support `publish --source NAME --target s3` (S3 is the default target).
`run` checkpoints finished local documents and publishes them automatically.
`download` and `finalize` remain local stages. Existing explicitly selected legacy
publication targets remain available. Local files are retained.

Configure a single destination in the selected operational YAML:

```yaml
storage:
  s3:
    bucket: your-bucket
    endpoint_url: https://your-s3-compatible-endpoint
    region: us-east-1
    prefix: books
```

Endpoint and region are optional for AWS. Credentials use boto3's standard
credential chain, including `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and
optional `AWS_SESSION_TOKEN`; do not put credentials in YAML. `DATABASE_URL`
continues to select authoritative progress and upstream metadata storage.

`ingestion/publication.py` projects native source state into
`PublishableArtifact` values. Extend that projection for new output layouts;
reuse the transfer implementation. Completed direct documents, assembled PDFs,
and Markdown with relative media are published; scan inputs, encrypted parts,
ZIP packages, and temporary files are excluded. Objects have deterministic
source/content keys and SHA-256 object metadata. PostgreSQL `s3_publications`
receipts retain destination, provenance and object hashes. Legacy Yandex flags
never count as S3 receipts. Run restores missing unpublished inputs; standalone
publish reports missing files without visiting upstream sites.

Publication runs after committed checkpoints under the source lock; receipts
are committed after uploads. An interrupted upload/checkpoint pair is reconciled
with S3 HEAD on retry. Upload work is capped by the configured item count and
uses bounded SDK retries/timeouts. A scan/download budget stop leaves publication
backlog eligible for the next command. Status reports recorded publication counts
without contacting S3. No public bucket access or metadata sidecar is required.

## Bounded agent inspection and command routing

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
See [historical publication verification](publication-verification.md).

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
credentials or provider imports. See the operations guide for inheritance,
environment references and migration of private combined files.
