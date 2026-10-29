# Echo of Centuries article PDFs

Add this entry under `sources` in your selected operational YAML:

```yaml
echovek:
  archive_url: https://www.echovek.ru/ru/publications
```

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source echovek --max-pages 2
.venv/bin/python cli.py --config ingestion.yaml download --source echovek --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source echovek
```

The adapter follows native issue-archive pagination, then the contents of each
issue, then article detail pages. Archive and issue pages both consume the listing
page cap; article detail requests are bounded by the shared deadline and network
settings. Two listing pages typically inspect the initial archive and one issue.
Discovery persists its frontier and resumes across invocations. Repeat discovery
until `discovery_complete` is true before claiming complete traversal of this
selected catalog. The archive advertises three pages at initial inspection; this
is not a verified count of Tatar articles or complete issue PDFs.

Only the native contents area is followed; sidebar featured articles and the
site's unrelated news are excluded. A publication's issue URL/title and the
article card's title remain in catalog provenance. Native cards pointing at
`/ru/node/` without an identifier are preserved as `unresolved_article_cards` in
that issue's article contexts, without fabricated URLs. An issue with no
resolvable articles remains a discovery error. These unresolved cards mean a
completed traversal does not establish complete publisher holdings.

The publication archive also lists books alongside journal issues. Recognized
native book pages are retained as `non_journal_metadata`, with their title,
publication node identifier and available language claim; no book files are
acquired through this article adapter. This prevents unrelated publisher books
from blocking later archive pages. The 2026-10-28 live continuation passed four
such records and resumed subsequent journal issues without restarting the scan.

The completed 2026-10-28 continuation exhausted all three archive pages and 61
publication pages: 1,385 records (1,375 articles and ten non-journal books), with
no remaining frontier or discovery errors. It exposed 1,091 article PDF assets,
95 admitted by explicit Tatar labels and 996 held for language. This verifies
traversal of the selected catalog, not complete publisher holdings or the content
language of every file. Three originals are verified locally. Two additional
samples from the completed scan are Хәмидуллина's 2009 article (1,681,874 bytes /
five pages / SHA-256 `fc920792121f5363ebd0b84bd2be3dd736bf55b78f675815cc61d666f53b3745`)
and Макарова on Хәсән Сарьян (1,279,194 bytes / 15 pages / SHA-256
`a6a8ffd7c59d00ddf1db91ce247472eadaae0c2c8a4be95aec3e52590b1e7645`).
Rendered samples contain Tatar; the older file's extracted text has legacy-font
encoding errors. Evidence and the completed manifest are under
`__artifacts/session-20261028/echovek/` and `echovek-samples/`.

Article records retain the Drupal node identifier, title, authors, rubric,
article type, publication-date text and explicit language field. Node identity
deduplicates article aliases; `echovek.ru` and `www.echovek.ru` normalize to the
HTTPS `www` origin. Acquisition requires `Татарский` in the article-language
field, including explicitly listed multilingual combinations. The interface
locale, title, author or a Tatar topic does not grant admission. Known non-Tatar
labels and missing/unrecognized labels remain unsupported metadata. HTML-only or
gated records are retained without inventing download URLs.

Downloads use only explicitly exposed article-PDF links from the native download
block and `/sites/default/files/statya/` paths. Whole issues, issue previews
(labelled `Читать отрывок`), covers, image readers, conversion and authenticated
access are outside this slice. Redirects may use the two HTTPS host aliases but
must preserve the native resource. No form submissions or account creation occur.

The shared downloader enforces file signatures, transport lengths when supplied,
byte/time/disk limits and atomic publication. Unchanged originals are retained
under `<artifacts_root>/echovek/files/`, with SHA-256/MD5 and observation provenance.
Local hash-verified files are skipped; missing/corrupt files remain eligible.
`--recheck` requests source revalidation. The source does not supply checksums
here; a complete PDF transfer does not certify article or printed-issue completeness.

Pre-implementation inspection downloaded article 2683 on К. Насыйри anonymously:
1,811,915 bytes, 10 PDF pages, SHA-256
`38056a12c5b5c26b1088a22eb8b3567c93d3c29a8f7d057d39f6170ae70e86fd`.
The article is explicitly labelled Tatar; sampled PDF page 4 contains readable
Tatar body text, with multilingual front matter. Evidence:
`/tmp/echovek-nasyri-2024.pdf`. This sample does not verify all catalog files or
their extraction quality.

Manual CLI verification on 2026-10-28 inspected the initial archive and one issue
in 19 requests, then resumed to another issue in 16 requests with the same scan
identifier and no discovery errors. The resulting manifest has 32 article records:
three Tatar-labelled PDF candidates (one downloaded, two pending) and 29 Russian
PDF links held as unsupported. The traversal remains incomplete with its saved
frontier; these are sampled yields, not catalog totals. Separate bounded reads
parsed all three archive pages (25, 25 and 11 issue links); issue contents beyond
the two CLI-inspected issues remain unverified.

CLI acquisition saved the complete Tatar-labelled Гайнетдинов article on Тукай
poetry in Arabic-script inscriptions: 1,084,267 bytes, six PDF pages, SHA-256
`1171fc22f8fa75917bd66756d26c91d15e6699001d594d7017a7a3a4ba24549e`.
The PDF opened and sampled page 3 contains readable Tatar text. A repeat download
before resuming discovery skipped it with zero requests. Evidence is under
`/tmp/echovek-verification/`; acquisition made one request with no errors.
