# Repository instructions

Do not write, add, generate, or restore automated tests in this repository.
Use code inspection and appropriate manual or CLI verification instead.

For shared ingestion work, start with `docs/adapter-development.md` for the code
map and reusable components. Use `scripts/ingestion_overview.py` for compact
manifest summaries before reading individual observations. Prefer
`.venv/bin/python` when available; the shell's default Python may belong to
another project. Inspect targeted files and avoid dumping private configurations.
