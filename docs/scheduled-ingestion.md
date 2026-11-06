# Scheduled ingestion operations

Implementation is prepared locally. **No workflows have been deployed, enabled,
run, or verified disabled on GitHub.** The 33 generated source workflows currently
have `workflow_dispatch` only. Common Crawl remains available locally and has no
workflow. The reusable `ingestion-runner.yml` accepts calls only.

## Runtime and storage

Every caller uses `.github/workflows/ingestion-runner.yml`, a standard
`ubuntu-latest` runner and a six-hour job timeout. Source concurrency groups use
`cancel-in-progress: false`; an active source run survives another trigger.
Different sources can overlap. PostgreSQL advisory locks also protect Actions and
local writers. No Actions cache or artifact stores progress or documents.

The runner invokes the ordinary CLI with a public configuration overlay:

```bash
.venv/bin/python cli.py --summary-only --config config/sources/magarif.yaml \
  --profile config/scheduled.yaml run --source magarif
```

`--profile` merges over the explicitly selected source YAML. Relative artifact
paths in the overlay resolve beside that overlay. This command is also usable
locally; it performs real ingestion when supplied credentials. Do not use it as a
dry run. No production run is required to deploy these files.

The profile allows five hours total ingestion across all stages, including native
Litres and Milli helpers. Budget objects share one invocation deadline rather
than restarting the clock per stage. Discovery has at most one hour; incomplete
frontiers checkpoint and resume, leaving acquisition time. Litres and Milli
finalize each newly acquired document during profile-driven `run`, so a large
acquisition backlog does not postpone all finalization until time expires.
Standalone local stages retain their existing behavior.

Checkpoint uploads share a single publication budget ending half an hour after
the ingestion deadline. Setup, final uploads, reporting and shutdown must all fit
the six-hour job. Deadlines are cooperative at existing operation/checkpoint
boundaries; a network request or local assembly already in progress may finish
after the deadline. SDK retries and network timeouts remain bounded.

The profile caps discovery at 10,000 pages, acquisition/publication at 10,000
items, incoming transfers at 20 GiB, individual inputs at 1 GiB, derived PDFs at
2 GiB, and reserves 3 GiB free disk. Source pacing and source-specific format and
assembly safeguards remain in effect. Runner disk can bind before transfer caps;
insufficient space is a visible failure. These are explicit safety limits, not
the previous 25-item/15-minute pilot policy. Budget stops are successful partial
runs; no automatic continuation is dispatched. Other database, acquisition and
upload errors fail the job. Fast sources finish early.

Postgres must already have the schema initialized (see
[Postgres operations](postgres-migration.md)); Actions never initializes or imports
production state. S3 is the only automatic remote publication target. Finished
PDFs, direct documents and Markdown/media bundles use existing deterministic keys,
receipt commits and HEAD reconciliation. No intermediate inputs are stored in S3.

A fresh runner resets missing, unpublished acquisition inputs to eligible state,
retaining acquisition results and native recovery evidence. Incomplete image
assemblies reacquire missing page files instead of trusting `downloaded` flags.
Litres/Milli missing input inventories also invalidate acquisition flags. Completed
S3 receipts allow repeat runs to skip already published documents. `run` leaves
unavailable outputs pending after a budget stop; standalone `publish` continues
to report missing local files as errors. Receipt counts are reported separately
from the acquisition backlog.

Large image books, reader text/media bundles or encrypted assemblies that cannot
be acquired and finalized in one run may reacquire the same inputs every schedule.
Use a persistent local workspace for these cases or implement a later recovery
improvement. This implementation deliberately adds no intermediate S3 persistence.

## Credentials and access

Configure repository Actions secrets:

- All sources: `DATABASE_URL`, `S3_BUCKET`, `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY`; optional `AWS_SESSION_TOKEN`.
- Litres only: `LITRES_SID`. The runner's installed Chrome supports the existing
  browser helpers. Access challenges/expired credentials remain failures.
- Milli only: `MILLI_KITAPHANA_AES_RAW_KEY`, `MILLI_KITAPHANA_AES_DEFAULT_IV`,
  `MILLI_KITAPHANA_AES_SALT`, `MILLI_KITAPHANA_PRIV_KEY`,
  `MILLI_KITAPHANA_SIG_PREFIX`. No legacy Yandex or upstream metadata credentials
  are required for S3 ingestion.
- Miras only: `MIRAS_SESSION_JSON`; Miras periodicals only:
  `MIRAS_PERIODICALS_SESSION_JSON`. Each contains its valid browser session export
  as documented in the respective [source guide](local-ingestion.md). Missing,
  invalid or rejected sessions fail visibly and require a new export.

Repository variables: optional `S3_ENDPOINT_URL` (empty means AWS), optional
`AWS_DEFAULT_REGION` (defaults to `us-east-1`). The shared runner receives only the
selected source's secret values, using explicit caller mappings rather than
`secrets: inherit`. Session exports are written with mode 0600 under `RUNNER_TEMP`
and removed in an `always()` step. Sessions and raw CLI output are never uploaded
as artifacts. Raw output is captured to a temporary file and removed; durable
error details remain in Postgres. Job summaries contain numeric discovery,
download, assembly, publication and backlog counters, duration, failure count and
allowlisted stop reasons, with no error messages, URLs or session data. Setup
failures receive a fallback summary.

## Disabled rollout (required before adding schedules)

GitHub native workflow state is external to YAML. Follow this order on the
default branch; do not enable or dispatch a workflow as part of rollout:

1. Publish the current manual-only files. No push event runs them.
2. With authenticated GitHub CLI in this repository, run:

   ```bash
   .venv/bin/python scripts/ingestion_workflows.py disable
   .venv/bin/python scripts/ingestion_workflows.py verify
   ```

   `disable` disables every registered source workflow and verifies every state
   is `disabled_manually`. Missing workflows, API errors and other states fail.
3. Generate scheduled triggers only after that verification:

   ```bash
   .venv/bin/python scripts/ingestion_workflows.py generate --scheduled
   ```

   This independently checks all remote states before changing any files. Review
   and publish the generated update while every source workflow remains disabled.
4. After publishing, run `scripts/ingestion_workflows.py verify` with
   `.venv/bin/python` again. Do not claim rollout complete until this passes.

GitHub CLI is unavailable in the implementation environment. All four remote
steps and native-state verification remain pending. No remote state is assumed.
The `generate --scheduled` guard was exercised and refused to add schedules when
GitHub CLI was unavailable.

The user can then enable individual sources: **Actions → select workflow → Enable
workflow**. To disable: **⋯ → Disable workflow**. Equivalent commands using actual
filenames:

```bash
gh workflow list --all
gh workflow disable ingest-magarif.yml
gh workflow enable ingest-magarif.yml
gh workflow run ingest-magarif.yml
```

Manual dispatch requires an enabled workflow. Disabled workflows accept neither
scheduled nor manual starts. Disabling does not cancel an already active run.

## Regenerating cadence and adding sources

`config/ingestion-schedules.yaml` defaults to two starts per calendar month.
`overrides` maps source names to starts per month (integers 1–28). For example,
`overrides: {magarif: 1}` changes only cadence, not pipeline logic.

```bash
.venv/bin/python scripts/ingestion_workflows.py generate
```

This safe default writes manual-only callers and the readable
[source/schedule table](ingestion-schedules.md). It removes scheduled triggers
from existing generated callers too. For any schedule update or new registry
source, follow the full disabled rollout above: publish manual-only files, disable
and verify the entire source fleet, generate schedules, publish, verify again,
and let the user re-enable selected workflows. New sources therefore cannot
silently enter enabled automation. Retire removed-source workflows explicitly;
the generator refuses to silently delete stale callers.

Slots span days 1–28, with nonzero minutes; both leap and ordinary Februaries get
all starts. The final three days of long months intentionally have no nominal
starts. Regeneration can move existing slots. Default 33-source coverage has 66
distinct nominal starts; at maximum ingestion runtime that is 330 ingestion
runner-hours monthly, plus setup/publication time. Actual use should be lower.

GitHub runs schedules on the default branch and may delay or drop starts,
especially during busy periods. Public-repository schedules may be automatically
disabled after 60 days without activity. There is no external scheduler or
activity-commit workaround. These constraints and the six-hour hosted-runner limit
were checked against the official references on 2026-11-06:
[scheduled events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule),
[native workflow controls](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows),
[Actions limits](https://docs.github.com/en/actions/reference/limits).

## Verification record and remaining checks

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
