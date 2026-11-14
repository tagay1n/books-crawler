# Litres unified pipeline

Follow [shared operations](operations.md) for configuration, limits, recovery and
compact CLI output, and the [stage contract](../ingestion-architecture.md#unified-stage-contract)
for shared lifecycle rules. Set `sources.litres.sid` to your Litres SID cookie for
catalog discovery, downloads and metadata refresh. Status and local finalization
do not require a SID. Provider helpers use the active runtime, never the retired
`litres/config.yaml`.

## Source-specific stages

Select your operational YAML with `--config`; for example:

```bash
.venv/bin/python cli.py --config config/local/litres.yaml discover --source litres --max-pages 1
.venv/bin/python cli.py --config config/local/litres.yaml download --source litres --format pdf --limit 1
.venv/bin/python cli.py --config config/local/litres.yaml finalize --source litres --limit 1
```

Discovery modes are `catalog`, `candidates` and `all`. Candidate discovery retains
the provider's language filters and scoring. Review actions are `export`, `sync`
and `import`; statuses are `candidate`, `accepted`, `rejected` and `maybe`. Only
accepted candidates are admitted by review import. The review TSV is an explicit
export; PostgreSQL holds current books, candidates and progress.

Download accepts `--format pdf`, `text` or `all`. PDF inputs are page images; text
inputs are decoded fragments and media. Finalization verifies recorded input
hashes and builds PDFs or Markdown locally, reporting missing unfinished inputs
as `awaiting_inputs`. `--recheck` refreshes acquisition inputs.

`run` composes discovery, acquisition, finalization and automatic S3 publication
under the [shared publication rules](operations.md#s3-publication). Review and
legacy publication targets remain explicit commands.

## Legacy state and publication targets

Use `import-state --source litres --from DIRECTORY` to import former book and
candidate indexes and review TSV files. Originals remain untouched. Valid local
PDFs and Markdown are copied and hashed; missing files remain eligible for
acquisition. Imported outputs do not establish complete source-image or text-input
inventories. Repeat import preserves existing records and review decisions. See
[database migration](../postgres-migration.md) for importing completion evidence
without local document files.

Explicit legacy targets are Yandex Disk plus monocorpus (`--target yandex`), the
`yasalma/tt-litres-books` Hugging Face dataset (`hf`), and Markdown media exports
(`s3-media`). They retain provider-specific credentials and destination-level
completion tracking; these are separate from shared S3 artifact receipts.
Yandex uses `sources.litres.yandex.oauth_token`, media exports use
`sources.litres.s3`, and HF uses its SDK credentials.

## Source-specific limits and evidence

Catalog completion requires native pagination evidence; missing cards or repeated
batches are errors. Candidate search checkpoints completed pages and restarts a
completed campaign on the next invocation. Browser navigation has page-load
timeouts and deadline checks, but browser-internal traffic is not byte-accounted.
Authenticated acquisition and browser fallback require live verification with a
valid SID. Follow the [manual verification workflow](../adapter-development.md#verify-changes).
[Historical migration checks](../archive/litres-verification.md) retain prior
sample counts, temporary paths and retired command names.
