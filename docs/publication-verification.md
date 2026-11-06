# Publication verification history

Implementation verification (2026-11-06): compiled ingestion modules, checked
CLI publication help and source listing, loaded the example configuration for
all 34 sources, verified placeholder S3 configuration fails before source work,
and ran `git diff --check`. No automated tests were added. Live database/S3,
interruption/recovery, and provider reacquisition verification remain pending:
this implementation environment has no DATABASE_URL and cannot access Docker.

## Agent tooling and checkpoint refactor (2026-11-06)

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

## Follow-up agent efficiency refactor (2026-11-06)

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
