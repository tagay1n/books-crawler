# Yazuchy publisher catalog

Add this entry under `sources` in your operational YAML:

```yaml
yazuchy:
  archive_url: https://sptatar.com/yazuchy-n-shriyaty/
```

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source yazuchy --max-pages 1
.venv/bin/python cli.py --config ingestion.yaml download --source yazuchy --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source yazuchy
```

The initial slice follows book-card links on this publisher page, not the whole
Writers' Union website. Each native detail URL becomes a separate book record.
Observations preserve title, full annotation/bibliography, raw PDF links, listing
context and language evidence. Only direct same-origin HTTPS PDFs inside the
book article are candidates; covers, sidebars, policy documents and reader
assembly are outside the slice. Unexpected catalog pagination holds discovery
for review. Current totals are observed catalog entries, not site-wide holdings.

The catalog mixes Tatar originals, translations into Tatar and Russian editions
of Tatar works. A Tatar interface, title or author does not admit a PDF. Explicit
`татар теленә тәрҗемә` target-language evidence admits a file; missing claims and
Russian target-language claims hold acquisition unless an individual file review
identifies Tatar content. Raw translation descriptions remain in metadata.

The checked-in `ingestion/yazuchy-language-reviews.json` records ten individually
sampled Tatar PDFs with SHA-256, observed byte/page counts, sampled page numbers
and reviewer/reason. For review-based admission, the acquired SHA-256 must match
before publication. Changed bytes stay failed for a new review. The review
identifies Tatar content in sampled pages; it does not certify monolinguality or
edition completeness. Several PDF page counts differ from catalog print-page
claims, which remain separately preserved in raw bibliography.

Optional `<artifacts_root>/yazuchy/language-reviews.json` uses the same version-1
`files` mapping as the checked-in file and overrides matching built-in reviews.
Each entry requires a hosted PDF URL, `sha256`, `languages` including `tt`,
`reviewer` and `reason`; do not grant a review from a filename or annotation alone.
The adapter refreshes review decisions before downloading, without a catalog
rescan. Removing a local override falls back to the checked-in review, rather
than withdrawing it. A built-in review must be removed from the checked-in file
to withdraw it. Discovery still determines which files are current candidates.

Originals use the shared bounded downloader and immutable SHA-256 file paths in
`<artifacts_root>/yazuchy/files/`, with manifest observations and acquisition
results. No conversion, account, media API or package handling is needed.
Byte/time/disk limits, signature checks, retry behavior and verified-local-file
reuse are shared with other adapters. `--recheck` revalidates completed files.

During implementation, nine PDFs completed bounded manual inspection under
`/tmp/yazuchy-review/`. The likely Tatar translation of `1993` exceeded the 25 MiB
inspection cap and initially stayed held pending the follow-up below.
Four Russian editions were not downloaded for language review. Review artifacts
are distinct from CLI acquisition evidence under `/tmp/yazuchy-verification/`.

Live CLI verification on 2026-10-28 inspected all 14 detail records in 15 HTTP
requests, without errors: nine eligible PDFs and five held files (three explicit
Russian-language exclusions and two without an admitted language claim/review).
The CLI saved the complete `Шамил Гәрәй` PDF: 20,638,673 bytes, 70 PDF pages,
SHA-256 `079f0cc30d6e8ac117d97b9b103fa2fd8d4249bb359a074e04e900f74fec0a89`.
Its result records the matching reviewed SHA-256. An isolated single-asset replay
under `/tmp/yazuchy-replay/` skipped the verified original with zero requests.
The other eight admitted files have manual byte/language inspections, but were
not all reacquired through the CLI.

On 2026-10-29, the previously held `1993: роман` completed a larger bounded
inspection: 27,139,111 bytes / 478 PDF pages, SHA-256
`1aae2559d4adb0a62b1312c0ebcad6f58f2639d0ab1b0c416643f53086925150`.
PDF pages 3, 11, 101, 451 and 478 contain readable Tatar narrative; rendered page
11 was also inspected. Its checked-in review admits the existing asset without
rediscovery, bringing the known catalog slice to ten eligible files and four
held. An isolated CLI run changed this asset from unsupported to downloaded,
verified the reviewed SHA-256, and a repeat skipped it with zero requests.
Evidence: `__artifacts/session-20261028/yazuchy-1993/` and session logs. Actual
PDF-page counts remain distinct from printed numbering; edition completeness
is unverified. The other unknown-language file remains held.
