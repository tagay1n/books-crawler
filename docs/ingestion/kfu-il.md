# KFU «Ил» newspaper

`kfu_il` selects only <https://repo.kpfu.ru/jspui/handle/net/28060> and keeps its
own manifest under `__artifacts/ingestion/kfu_il/`. Add the `kfu_il` source entry
from `ingestion.example.yaml` to the selected operational YAML. The existing
KFU books and manuscripts sources continue to admit all collection languages.

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source kfu_il --max-pages 1
.venv/bin/python cli.py --config ingestion.yaml download --source kfu_il --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source kfu_il --max-pages 1 --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source kfu_il
```

Il requires an explicit `DC.language` value of `tt`, `tat`, `Tatar`, `татарский`,
`татарча`, or `татар теле` (case and surrounding whitespace are normalized).
Multiple source language fields are allowed when at least one identifies Tatar.
Recognized other-language-only records are held as `language_excluded`;
missing or unrecognized labels are held as `language_unknown` for review.
Crimean Tatar (`crh`) does not count as Tatar. Titles, Arabic script, and collection
membership do not substitute for the source language label. Held records retain
metadata and file inventories; their public document/reader assets remain
unsupported and no reader requests or downloads are made. Existing restriction
markers take priority in each asset's unsupported reason.

The manifest retains the native handle, original issue title, publication dates,
series descriptions, full bibliographic rows, supplied script descriptions,
collection provenance, and language/access evidence. Issue titles and dates stay
as supplied; no calendar conversion or issue numbering is inferred. Different
handles remain distinct records even when issue titles repeat. File bytes are
deduplicated by hash within the source's existing file store.

Il reuses KFU's validated native offset pagination, count verification, anonymous
GET-only acquisition, restriction handling, and resumable original-file downloads.
Eligible public direct PDFs take priority. When only a supported public JPEG
reader exists, the inherited assembler retains originals and derives a complete
200 DPI colour PDF at JPEG quality 85. `--limit` counts a direct file or whole
image-based issue as one item. No ZIP expansion, login, or copy-request submission
is performed. Restrictions remain explicit follow-up candidates in the file inventory.

The collection advertised 110 catalog records during selection on 2026-10-27;
this is not a count of distinct issues or guaranteed public files. Two inspected
records, `net/28231` (№39, 1917) and `net/28230` (№31, 1917), both identify `tt`
and expose public PDFs alongside restricted ZIPs. Small byte-range requests
returned PDF signatures and total lengths of 7,911,593 and 8,066,846 bytes.

Manual CLI verification on 2026-10-27 discovered the first 20 records, all labelled
`tt`, with 20 eligible PDFs and 20 restricted ZIP blocks retained as metadata.
Discovery stopped cleanly at its one-page cap with `offset=20` saved for resumption.
One bounded download acquired `net/28231`'s `1917-39.pdf` (7,911,593 bytes) in one
request without retries. Local inspection verified four readable PDF pages,
matching SHA-256/MD5, and its acquisition-to-observation link. A repeat download
on an isolated copy skipped the completed file with zero network requests. The
main queue retains 19 pending PDFs; these are partial-scan results. Compilation,
code inspection, and manual CLI verification were used; no automated tests were added.
