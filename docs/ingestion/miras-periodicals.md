# Miras periodicals

The separate `miras_periodicals` source uses the existing Miras session export and
PDF downloader with its own manifest under `<artifacts_root>/miras_periodicals/`.
Add this entry under `sources` in your operational YAML:

```yaml
miras_periodicals:
  archive_url: https://miras.info/projects/mirasxane/periodicals/
```

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source miras_periodicals --max-pages 1 \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
.venv/bin/python cli.py --config ingestion.yaml download --source miras_periodicals --limit 1 \
  --session-file ~/Downloads/books-crawler/miras/miras-session.json
.venv/bin/python cli.py --config ingestion.yaml status --source miras_periodicals
```

Records represent periodical series, identified by native numeric IDs as
`periodical:<id>`. Catalog pagination and record checkpoints are independent of
the books source. Description, series-level language evidence, catalog context,
reader links, and selector labels/values are retained. Source-described historical
issue totals are not downloadable-holdings counts. No existing books or pilot
manifest is imported or rewritten.

Only explicitly exposed same-origin original PDFs are supported: direct links,
`viewer.html?file=...` references, and selectors whose values are actual PDF or
viewer URLs. The adapter does not construct file paths from year/issue numbers or
execute website scripts. Unresolved selector options are retained as metadata and
hold the series' otherwise eligible PDFs with `reader_unresolved`, avoiding a
partial default-issue acquisition presented as complete coverage. Other formats
and external files remain unsupported. An explicit Tatar language claim in series
metadata or description is required; unlabelled series are held with
`language_unknown`. This is upstream evidence, not verified document language.

**Verification pending (2026-10-28):** the bounded CLI run with the saved browser
session stopped after one access rejection, before catalog inspection. It exited
nonzero and preserved an incomplete scan with one pending listing request and zero
records, assets, or acquired bytes. CLI registration, configuration loading,
read-only status, compilation, and whitespace checks passed. Diagnostics are under
`/tmp/miras-periodicals-verification/miras_periodicals/`.
A refreshed session is required to verify live
pagination and issue-selector behavior and acquire a complete issue PDF. Dynamic
selector resolution remains unfinished; no complete periodical acquisition or
catalog coverage has been verified. Existing PDF validation, hashes, budgets,
access rejection handling, and session format are reused from `miras`.
