# Isxaki books and works

Add `sources.isxaki.archive_url: https://isxaki.com/ijat/` to the operational YAML,
or copy the entry from the example configuration. No credentials are required.

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source isxaki
.venv/bin/python cli.py --config ingestion.yaml download --source isxaki --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source isxaki --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source isxaki
```

Discovery covers these five collections: `/ijat/kitaplar/` (original editions),
`/ijat/asarlar/` (1896–1907), `/asarlar-1908-1918-ellar/` (1908–1918),
`/1919-1947/`, and `/ijat/about/kitaplar/` (books about Iskhaki).
The entry point and five collection listing requests consume six discovery pages;
each collection is also inspected as a record through the shared discovery core.
A lower page cap resumes the saved frontier on the next invocation.

Each collection is one source record. Its metadata retains the book cards,
supplied bibliographic descriptions, cards without attachments, and source notes.
Document links within cards become assets; repeated links within a collection
share an asset, while overlapping collections retain separate provenance.
HTTP links on the source host are normalized to HTTPS and the observed `/tt/`
collection aliases are normalized to their canonical paths. Original link URLs
remain in card metadata. Navigation, cover images, news, letters, and diaries
are outside this adapter's scope. External document links remain unsupported.
Transport uses the shared GET-only guard with the existing native HTTPS-origin
rule, including same-origin redirects. External redirects and HTTP downgrades
remain rejected; link normalization does not relax the transport origin check.

Both historical editions and supplied modern text PDFs are eligible. Files are
saved unchanged under `__artifacts/ingestion/isxaki/files/` with the shared local
manifest, SHA-256/MD5, integrity checks, budgets, and recheck behavior. HTML-only
texts remain metadata; no HTML/text artifact or PDF is generated. A title or
bibliographic claim does not establish language, edition accuracy, or completeness.
Malformed or broken file links are retained and reported when downloads fail;
they are not silently repaired or dropped.

The 2026-10-27 live check completed all five configured collections in six
listing requests and five record requests: 64 document relationships pointing
to 63 unique file URLs. It downloaded “Бай углы” (31,535,638 bytes), verified the
saved SHA-256/MD5, size, and observation link, and checked that a repeated CLI
download skipped an isolated copy of the completed sample with zero requests.
The other 63 relationships remain pending; their file availability and integrity
have not been verified. Traversal completion covers these five sections, not
the entire website, and the source supplies no independent catalog count.
