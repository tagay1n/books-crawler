# Per-source configuration migration verification

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
