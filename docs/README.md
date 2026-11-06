# Documentation map

Read `AGENTS.md` first. Select one task below, then open only the relevant source
or implementation file. Do not read every source guide or historical report.

| Task | Entry point |
| --- | --- |
| Change an adapter or shared ingestion | [Adapter code map](adapter-development.md) |
| Run ingestion, configure limits or publish to S3 | [Shared operations](ingestion/operations.md) |
| Find source scope, access rules and commands | [Source guide index](local-ingestion.md) |
| Set up PostgreSQL or import legacy progress | [Database operations](postgres-migration.md) |
| Inspect a candidate public website | [Bounded inspection](source-inspection.md) |
| Audit discovery coverage | [Review register and checklist](source-discovery-reviews.md) |
| Change stage, checkpoint or routing contracts | [Implementation contracts](ingestion-architecture.md) |
| Operate GitHub Actions ingestion | [Scheduled operations](scheduled-ingestion.md) |
| Inspect generated UTC slots | [Schedule table](ingestion-schedules.md) |
| Investigate old decisions or verification evidence | [Archive](archive/README.md) |

PostgreSQL and code/configuration are authoritative for current state and behavior.
Keep shared rules in their owning guide and link to them from source guides.
Record new source-specific evidence in that source's guide; use the review register
for periodic audit outcomes. Completed handoffs belong in the archive only when
they retain evidence absent from current guidance.
