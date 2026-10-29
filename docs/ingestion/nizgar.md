# Nizgar magazine archive

Add this entry under `sources` in your selected operational YAML:

```yaml
nizgar:
  archive_url: https://nizgar.ru/zhurnal-nizhegorodskie-tatary-nizhgar-tatarlary/
```

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source nizgar --max-pages 1
.venv/bin/python cli.py --config ingestion.yaml download --source nizgar --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source nizgar
```

The selected native page has WordPress file blocks rather than issue-detail
pages. Discovery therefore stores one archive record with individual issue cards
and one asset per unique PDF URL. Status record counts refer to the archive;
asset counts refer to issue files. Each card retains its raw issue label, date
label, issue-number/year/month claims, and title/download links. Two anchors
pointing at the same issue PDF produce one file acquisition. Unexpected file-block
structure, mismatched title/button URLs or pagination holds discovery for review.

The source is the bilingual magazine **«Нижегородские татары. Нижгар татарлары»**,
not the separate «Туган як» newspaper advertised inside it. Admission follows
explicitly labelled issue PDFs in this selected series, as authorized for this
adapter. The inspected April 2016 issue contains substantial Tatar text alongside
Russian articles. Series membership does not verify each issue's Tatar content,
language proportion or monolinguality; keep that distinction for downstream
language filtering. Cover images, sidebar news, social channels and the old
website are outside this slice.

The current listing exposes 12 unique PDFs, labelled 2014–2018 plus a 2024
anniversary issue. Number 9 is absent; no missing issues or URLs are synthesized.
Dates are retained as source claims: for example, issue 6 is labelled November
2016 while issue 7 is April 2016. The adapter does not silently correct this
sequence. The uploads' `/2026/02/` path is not a publication-date field.
Anniversary labels retain their full text and year without inventing a month.

Only same-origin HTTPS `/wp-content/uploads/` PDFs are acquired. External file
references remain unsupported metadata. The shared downloader validates PDF
signatures, complete transport lengths when supplied, configured byte/time/disk
limits and local SHA-256/MD5 before atomic publication. Originals remain unchanged
under `<artifacts_root>/nizgar/files/`, with provenance and results in the manifest.
No source-provided checksum is advertised here. Integrity checks do not establish
completeness against a printed issue. Downloads skip hash-verified local originals;
missing/corrupt files remain eligible, and `--recheck` requests revalidation.
Run discovery again to refresh metadata and mark removed links inactive.

Requests use the shared GET-only guard with this adapter's archive/upload path
allowlist. Redirects remain allowed within those validated native paths, retaining
the existing file-alias behavior; other origins and HTTP downgrades are rejected.

Pre-implementation inspection downloaded issue 7 anonymously: 7,271,105 bytes,
100 PDF pages, SHA-256
`816a09bf15b2969fbf0e130004955a9be637a8613a8f14e365ba28c56a08bf72`.
Readable Cyrillic Tatar interview text appears on PDF page 10; Russian content
appears elsewhere. Evidence: `/tmp/nizgar-2016-7.pdf`. This sample does not verify
the other issue layouts, catalog date accuracy, or printed-edition completeness.

Manual CLI verification on 2026-10-28 completed discovery in two requests with
12 unique PDF assets and no errors. One subsequent CLI acquisition saved issue 1
(July 2014): 9,822,185 bytes, 91 PDF pages, SHA-256
`c435af7fadb929ff04ff41890947c2c413e31de48d86a4effefdafc321da1e6d`.
The PDF opened successfully; sampled page 73 contains readable Tatar text.
An isolated single-file replay skipped that hash-verified original with zero
network requests. Evidence: `/tmp/nizgar-verification/` and `/tmp/nizgar-replay/`.
The full discovery manifest retains the other 11 assets as pending; they were
not bulk-acquired through the CLI. Apart from the separately inspected issue 7,
their bytes and language content remain unverified.
