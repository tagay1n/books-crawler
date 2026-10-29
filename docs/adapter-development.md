# Adapter development map

Read `AGENTS.md` first: do not add automated tests. Use code inspection and bounded
manual CLI verification. Use `.venv/bin/python`; the shell's default Python may
belong to another project.

## Find the relevant code without a full repository tour

- `ingestion/registry.py`: registered sources; check before proposing a new
  adapter. `ingestion/config.py` validates explicitly selected operational YAML.
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
- `ingestion/inspection.py` and `cli.py inspect`: bounded public-page evidence,
  link extraction and optional PDF-prefix probes. Use this instead of custom
  fetch scripts; see [inspection usage](source-inspection.md).
- `docs/local-ingestion.md`: short index of per-source guides under
  `docs/ingestion/`. Open the selected guide rather than reading every adapter.
- `ingestion/yazuchy.py`: direct PDFs and manual reviews. `echovek.py`:
  archive-to-issue-to-article traversal. `sarhaan.py`: language claims and
  individual files behind native redirects.

## Inspect state efficiently

```bash
.venv/bin/python scripts/ingestion_overview.py __artifacts/ingestion
.venv/bin/python scripts/ingestion_overview.py __artifacts/session-20261028
.venv/bin/python scripts/ingestion_overview.py --details __artifacts/session-20261028/kfu_repository
```

The helper reads selected roots' immediate source manifests only, emits one JSON
line per manifest, and never opens configurations, modifies artifacts or makes
network requests. Explicit source directories and manifest paths also work.
Manifests with at least 1,000 assets or 500 records use compact JSON to reduce
checkpoint serialization and disk writes; their schema is unchanged. Smaller
manifests and other JSON artifacts retain indentation. Use the overview or parse
selected fields rather than printing a large manifest's single line.
Discovery commits each successful observation and its completed frontier work
in one atomic checkpoint. `Manifest.observe()` still saves immediately for other
callers; only discovery defers that save until its checkpoint is ready.
Discovery uses invocation-local membership sets and a pending-work deque while
retaining ordered JSON lists for resume compatibility. `Manifest.observe()` lazily
indexes assets by owning record instead of scanning every asset per observation.
Create assets and change their owning record through that method so the index
stays coherent; download status/result updates do not affect ownership.
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
