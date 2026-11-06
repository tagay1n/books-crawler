# Historical implementation verification

Dated implementation checks; these do not establish current deployment health.
Use [Postgres operations](../postgres-migration.md), [publication](../ingestion/operations.md#s3-publication),
and [scheduled operations](../scheduled-ingestion.md) for current behavior.

## Configuration: per-source configuration migration verification

Implemented 34 public source configurations, explicit shared YAML inheritance,
recursive overrides, environment references, invocation-local provider helper
settings and configured KFU collection selection. The obsolete private ingestion.yaml was removed at the user’s request without
reading its contents. Workflow creation remains separate.

Manual verification:

- Loaded all 34 source configurations without publication credentials.
- Imported registered adapters and native provider helper modules with temporary
  placeholder environment variables; no upstream calls or state writes.
- Ran `cli.py sources --details` without configuration.
- Checked mapping overrides, list replacement, explicit nulls and cycle rejection
  using temporary YAML files outside the repository.
- Checked missing environment-variable diagnostics without printing values.
- Exercised Yazuchy native normalization, rejection of external origins, changed
  configured roots, sequential invocation isolation and helper worker context.
- Ran `.venv/bin/python -m compileall -q ingestion` and `git diff --check`.

No automated tests were added or restored. Live discovery, acquisition and remote
publication were not run; provider credentials, PostgreSQL integration and upstream
availability remain deployment verification steps. Source admission/parser rules
remain code. Standalone configuration-free inspection/database administration
commands retain their existing CLI defaults.

## Publication verification history

Implementation verification (2026-11-06): compiled ingestion modules, checked
CLI publication help and source listing, loaded the example configuration for
all 34 sources, verified placeholder S3 configuration fails before source work,
and ran `git diff --check`. No automated tests were added. Live database/S3,
interruption/recovery, and provider reacquisition verification remain pending:
this implementation environment has no DATABASE_URL and cannot access Docker.

### Agent tooling and checkpoint refactor (2026-11-06)

Completed documentation consolidation, compact S3/error views, selected-state inspection,
typed command routing and explicit checkpoint orchestration. Progress callers now use
`checkpoint()`; receipt/import saves remain persistence-only. The final publication pass
shares the run's checkpoint upload budget.

Verification: compiled all ingestion/scripts modules; CLI source listing and detailed
capabilities for 34 adapters; inspection command help; unsupported finalize, publication
target and recheck rejection; manual compact error preview limits; lazy startup imports;
PostgreSQL asset-query compilation; missing-DATABASE_URL handling; `git diff --check`.
No automated tests were added or run. No operational configuration or originals changed.
Live selected-record/error inspection and database/S3 interruption, recovery and receipt
reconciliation remain unverified: DATABASE_URL is unset and Docker socket access is denied.

### Follow-up agent efficiency refactor (2026-11-06)

Added explicit preview omission metadata and record field selection, paged record-key
listing, selected-source capabilities, shared artifact directories, read-only projected
status snapshots and a SQL history-count aggregate. Split Litres PDF transport, assembly
and configuration into focused modules while retaining helper imports at the old path.

Verification: all 50 original Litres PDF function/class AST bodies match their moved
versions; local two-page PDF assembly succeeded and repeat assembly preserved its bytes.
Compiled ingestion/scripts modules; checked capability filters, unknown sources, CLI help,
record-list limits and missing-database errors. Reviewed snapshot/write-baseline separation
and shared path use. No automated tests added. Live PostgreSQL projection, pagination,
and publication counts remain unverified: DATABASE_URL is unset and Docker access is denied.

## Postgres migration verification


Verified against an isolated PostgreSQL 16 container, without automated tests:
all four imports and repeat imports; persisted counts (527 Litres records,
16,579 Milli records, 90 Tatkniga records with 278 assets, 36,607 Common Crawl
records); rollback; competing writers; lock-session loss; completion skipping
with empty workspaces; and two bounded live Magarif discovery invocations with
persisted progress and no discovery errors. Imported tables/indexes occupied
approximately 53 MiB before subsequent discovery. Compilation and
`git diff --check` passed. These initial checks did not modify Aiven.

### Removal of local progress dependencies

Manual follow-up verification covered all 33 registered source status operations,
Litres candidate admission/review persistence, Milli split/selection recovery and
named recovery journals across empty workspaces. These operations produced no
local files. Two bounded live Magarif discovery invocations resumed from Postgres
with no discovery errors and no local progress output. Completed direct downloads
and image publications skipped missing local files; unfinished finalization
reported `awaiting_inputs`, and an unchanged recorded recipe skipped finalization.
A worker rejected a terminated Postgres lock session. Real Milli recovery journals
(1,969 records in `default`, two in the other journal) imported successfully;
repeat import was a no-op. Source website credentials and publication destinations
were not exercised. No automated tests were added.

Before changes, local indexes were archived under
`__artifacts/state-backups/20261106T133402Z/`. The complete archive is
`processing-state-complete.zip`: 249 files, 248,633,931 uncompressed bytes,
31,536,375 archive bytes, with a SHA-256 inventory. Archive contents were verified
and all original progress files were confirmed unchanged. The archive is ignored
by Git and readable only by its owner. Aiven was subsequently initialized and
imported as recorded below.

### Aiven migration applied (2026-11-06)

Initialized the ingestion schema for all 34 registered sources over an SSL
connection and applied all four established-source imports. Read-back verification
confirmed 527 Litres records, 16,579 Milli Kitaphana records, 90 Tatkniga records
with 278 assets, and 36,607 Common Crawl records. Completion evidence was preserved,
including 478 acquired Litres records, 14,759 fully downloaded Milli records,
189 acquired Tatkniga assets and 35,113 uploaded Common Crawl records.

Milli's recovery journals retained 1,969 records in `default` and two records in
`two-pending-20261030`. All other source record tables were empty. Four import
receipts were verified. Final database size was 65,631,935 bytes (about 63 MiB),
including 56,516,608 bytes of ingestion tables and indexes. Local indexes and
backups were left unchanged. Future CLI and workflow processes must supply
`DATABASE_URL`; connection credentials are not stored in this repository.

## Scheduled ingestion verification (2026-11-06)


No automated tests were added or run. Manual/CLI inspection verified:

- 33 callers exactly match the registry excluding Common Crawl; shared wiring and
  source-specific secret mappings were inspected. All source configurations load
  with the profile without resolving unrelated source credentials.
- 66 distinct twice-monthly UTC cron slots, days 1–28, including Februaries in
  2024, 2025, 2026 and 2028. All workflow YAML parses; every embedded shell script
  passes `bash -n`; source files currently contain manual triggers only.
- Budget probes show one shared ingestion deadline, a discovery stop that leaves
  acquisition eligible, and a 1,800-second publication reserve. An exhausted
  overall budget reports `soft deadline`.
- In an empty temporary workspace, missing image inputs become pending while
  result history remains intact; a second recovery call is unchanged. Missing
  Litres/Milli inputs retain recovery evidence and become eligible again.
- A real bounded CLI invocation with missing `LITRES_SID` fails before database
  access and writes a failed Actions summary. Missing `DATABASE_URL` fails the
  read-only overview promptly. Changed modules compile; `git diff --check` passes.

No configured Postgres service, S3 service, source sessions or GitHub CLI were
available for integration verification. Still required against isolated state:
real checkpoint/resume and repeat-run receipt skipping, upload/HEAD reconciliation
and injected upload failure, source lock contention across processes, expired
source access, and an end-to-end image assembly on a fresh workspace. Actions
schema validation was by YAML/shell parsing and inspection; `actionlint` and
GitHub-hosted execution were unavailable. Do not enable production sources merely
to perform these checks.
