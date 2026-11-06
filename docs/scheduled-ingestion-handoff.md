# Handoff: scheduled source ingestion

Status: agreed requirements, ready for implementation in another thread.
Prepared 2026-11-06. This file is the handoff deliverable; it does not deploy or
enable workflows.

## Goal and agreed defaults

Implement a separate GitHub Actions workflow for each registered ingestion source
except `common_crawl`. There are currently 34 registered sources, so this means
33 source workflows. Common Crawl took months to acquire and is explicitly
excluded from this automation; keep its local functionality available.

- Run each included source **twice per calendar month** by default. This
  supersedes the initial suggestion of once monthly. Support per-source cadence
  overrides without duplicating ingestion logic.
- Spread starts approximately across the full month, including February, and
  avoid the start of the hour. Do not spend substantial effort optimizing exact
  spacing: adding sources and regenerating schedules must be straightforward.
- Use standard GitHub-hosted Linux runners in a public repository.
- Allow rare overlap between different sources when starts are delayed. Prevent
  simultaneous runs of the same source without cancelling an active run.
- Keep all ingestion execution code and configuration usable locally through the
  same shared CLI. Actions should supply setup and orchestration.
- All source workflows must initially be **disabled through GitHub's native
  workflow controls**, until the user explicitly enables individual workflows.

## Start with the current implementation

Read `AGENTS.md` and [the adapter development map](adapter-development.md).
**Do not write, generate, add, or restore automated tests.** Use code inspection
and bounded manual or CLI verification with `.venv/bin/python` where available.
Inspect targeted files; do not print private operational configurations or secrets.

The source registry is `ingestion/registry.py`. Use it as the inventory authority;
exclude `common_crawl` explicitly. At preparation time the included names are:

```text
milli_kitaphana, litres, magarif, tatarica, darul_kutub, sarhaan,
ftatarstan, dumrt, tuganzhir, beznenmiras, miras_periodicals, magarif_vakyt,
turuz, yazuchy, nizgar, echovek, obuchalka, kazanutlary, tatkniga, miras,
commons, isxaki, internet_archive, kfu_repository, kfu_dspace, tataroved,
kfu_books, kfu_manuscripts, kfu_il, kfu_azad_halyk, kfu_vakyt, kfu_shura,
tatargalyame
```

Reinspect configuration and publication interfaces before implementing: they
changed during this discussion, and some source guides describe older behavior.
Check `git status` and preserve unrelated work. No workflow files existed when
this handoff was prepared.

Relevant components:

- `cli.py` / `ingestion/cli.py`: shared entrypoint and source commands.
- `ingestion/core.py`: `run` lifecycle, checkpoint publication, and recovery.
- `ingestion/publication.py`: finished artifact inventory, S3 receipts and
  missing-file handling.
- `ingestion/config.py`, `config/defaults.yaml`, `config/sources/`: inherited
  configuration and environment-based credential references.
- [Postgres operations](postgres-migration.md): durable state and advisory locks.
- [Source guides](local-ingestion.md): source-specific access and assembly rules.

Use `scripts/ingestion_overview.py --database` for current progress summaries.
Local manifest summaries describe archived snapshots, not current progress.

## Execution, storage, and failure behavior

Use thin source workflows with shared runner setup and execution logic. Each
source needs both scheduled and manual triggers once rollout is complete.
Provide a simple schedule-generation command and a readable source/schedule
table. Regeneration may adjust existing slots; perfect historical slot stability
is not required. Do not automatically include newly added sources in enabled
automation: apply the disabled rollout procedure to them too.

Run the shared pipeline to discover, acquire, finalize supported outputs, and
publish completed documents to the configured **S3** destination. Do not add
automatic Yandex, Hugging Face, or other publication targets.

- Allow up to **five hours of ingestion** inside a **six-hour total job timeout**.
  Apply one overall ingestion deadline, rather than a separate five-hour budget
  per stage. Reserve the remaining time for setup, uploads, shutdown and reporting.
- Fast sources exit when finished. Save progress at existing durable checkpoints.
  Budget exhaustion is a successful partial run; resume at the next regular
  schedule. Do not launch automatic continuation runs.
- Review page, item, byte, disk and network limits. Current pilot defaults
  (15 minutes, 25 pages/items, 1 GiB transfer) must not accidentally restrict the
  new runtime policy. Keep explicit safety limits and source pacing.
- Ensure long discovery scans leave an opportunity for acquisition and
  publication; a source must not repeatedly spend its whole allowance discovering.
- Postgres is the progress authority. S3 retains completed documents. Actions
  artifacts and caches must not become authoritative state or document storage.
- **Do not introduce S3 persistence for intermediate assembly inputs.** Reacquire
  missing inputs from the source when needed, retaining acquisition history.
  Verify fresh-runner behavior rather than assuming recorded downloads imply
  local files exist. Document that assemblies too large for one run may need local
  execution or a later recovery improvement.
- Supply only credentials required by the selected source using existing
  environment-based configuration. Never commit credentials or browser sessions.
  Miras sources require session exports; Litres and Milli have their own access
  prerequisites. Once enabled, missing or expired access must fail promptly and
  visibly, rather than silently skip a source.
- Database, acquisition, and publication failures must remain visible failures.
  Do not swallow exit codes to make a partial failure appear successful.
- Retain existing Postgres source-lock protection for local and Actions writers;
  also configure source-specific Actions concurrency. Different sources may run
  together; do not introduce a global serialization gate.

Publish an Actions job summary with discovery progress, downloads, S3 publication
counts, remaining backlog, duration, and stop reasons. Distinguish normal budget
stops from failures. Keep logs and summaries free of credentials and session data.
At the maximum runtime, 66 monthly runs consume 330 ingestion runner-hours;
actual usage should be lower because fast sources exit early.

## Initially disabled rollout and user controls

GitHub's enabled/disabled state is external to workflow YAML; there is no YAML
field that makes a new workflow initially disabled. Use this staged procedure to
avoid accidental scheduled ingestion:

1. Publish source workflows with **manual triggers only**, without triggering them.
2. Disable every source workflow through GitHub UI, CLI, or API.
3. Verify every source workflow has state `disabled_manually`.
4. Add the scheduled triggers while the workflows remain disabled.
5. Verify they are still disabled after that update.

Do not enable workflows or launch production ingestion as part of deployment.
If GitHub access is unavailable, deliver the prepared changes and explicit
remaining rollout steps; do not claim the remote workflows are disabled.

The user enables sources individually: **Actions → select workflow → Enable
workflow**. To disable one, use its **⋯ → Disable workflow** menu. Disabled
workflows do not respond to scheduled or manual triggers. Local CLI commands
remain usable independently.

Include commands using the actual implemented filenames, for example:

```bash
gh workflow list --all
gh workflow disable ingest-magarif.yml
gh workflow enable ingest-magarif.yml
gh workflow run ingest-magarif.yml
```

GitHub CLI was unavailable in the preparation environment; these are operating
examples, not actions already performed. Manual runs require an enabled workflow
with `workflow_dispatch` support.

Schedules run from the default branch and are best effort: starts may be delayed
or dropped. Spacing is not an exact-time or no-overlap guarantee. Public repository
schedules can be automatically disabled after 60 days without repository activity.
Document this limitation; do not add an external scheduler or automatic activity
commits as part of this work.

Official references:

- [Workflow enable/disable controls](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)
- [Scheduled events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [Actions limits](https://docs.github.com/en/actions/reference/limits)

Recheck current GitHub requirements during implementation.

## Manual verification and acceptance

Use isolated state, storage and bounded commands for verification; do not trigger
production acquisition or enable workflows merely to verify the implementation.

- Confirm 33 source workflows against the current registry, with no Common Crawl
  workflow. Confirm adding a source has a documented generation/disabled rollout.
- Inspect generated schedules for twice-monthly coverage, February and leap-year
  behavior, approximate full-month spacing, and distinct nominal start times.
- Validate workflow syntax, shared invocation wiring, source configuration and
  secret references through inspection and appropriate CLI checks.
- Verify bounded local execution, checkpoint resumption, repeat-run skipping, S3
  publication and recovery with an empty runner workspace.
- Exercise budget exhaustion, missing/expired credentials, upload failure and
  same-source concurrency. Confirm a failure remains visible and an active run
  is not cancelled by a later trigger.
- Inspect image-based assembly behavior after losing local inputs and describe
  any source that cannot make useful progress within one run.
- Verify disabled remote workflow state if deployment access is available;
  otherwise clearly record that deployment and state verification remain pending.
- Compile changed Python modules and run `git diff --check`. Add no automated
  tests. Report what was actually verified and any remaining limitations.
