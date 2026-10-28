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
- `ingestion/core.py`, `network.py`, `state.py`: reuse bounded streaming, format
  signatures, atomic publication, retry budgets, observations, hashes,
  source locks and repeat-run skipping. Do not duplicate these in adapters.
  `network.install_native_get_guard` shares read-only native URL and redirect
  checks; callers retain their own allowlist and optional delivery equivalence.
- `ingestion/language_reviews.py`: reuse SHA-256-pinned manual language reviews
  when reliable item-language claims are absent. A subject or interface locale
  does not establish document language.
- `ingestion/yazuchy.py`: direct PDFs and manual reviews. `echovek.py`:
  archive-to-issue-to-article traversal. `sarhaan.py`: language claims and
  individual files behind native redirects.

## Inspect state efficiently

```bash
.venv/bin/python scripts/ingestion_overview.py __artifacts/ingestion
.venv/bin/python scripts/ingestion_overview.py __artifacts/session-20261028
```

The helper reads selected roots' immediate source manifests only, emits one JSON
line per manifest, and never opens configurations, modifies artifacts or makes
network requests. Explicit source directories and manifest paths also work.
Manifests with at least 1,000 assets or 500 records use compact JSON to reduce
checkpoint serialization and disk writes; their schema is unchanged. Smaller
manifests and other JSON artifacts retain indentation. Use the overview or parse
selected fields rather than printing a large manifest's single line.
Discovery completeness is distinct from advertised-count verification and from
download completion. Inspect individual observations only when a summary points
to a concrete question; avoid dumping complete manifests or private configs.

## Verify and hand off

Use a dedicated ignored artifact root and explicit operational YAML. Run
discovery, acquire a bounded original, inspect its format and content language,
then repeat acquisition to verify hash-based skipping. Exercise resume or failure
behavior when changing those paths. Serialize commands writing the same source;
different sources have independent locks. Compile changed modules and run
`git diff --check`. Record scope, evidence, remaining frontier and commands in a
short work log; commit only relevant paths or hunks. Keep originals out of Git.
