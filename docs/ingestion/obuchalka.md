# Obuchalka reviewed Tatar textbooks

Add this entry under `sources` in your selected operational YAML:

```yaml
obuchalka:
  archive_url: https://obuchalka.org/knigi-po-tatarskomu-yaziku/
```

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source obuchalka --max-pages 1
.venv/bin/python cli.py --config ingestion.yaml download --source obuchalka --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source obuchalka
```

Discovery follows dated book-record links inside the selected category's
`groupdata` area. It does not traverse related-book recommendations, advertisements,
other subject categories or buy/search buttons. Records retain their native post
identifier, title, description, catalog context and delivery links. The current
category has 36 book records and 38 Fileskachat file-page candidates; some records
offer multiple representations. Candidate file counts are not counts of Tatar PDFs.
The date in a record URL is not inferred to be the book's publication date.

This is a mixed subject catalog containing Russian-language studies, Crimean
Tatar and Bashkir items as well as Tatar textbooks. Neither category membership,
title, annotation nor target-school language grants acquisition. Every file needs
an individual content review with a pinned SHA-256 identifying Tatar content.
Reviewed content may still contain other languages; sampled-page review does not
certify monolinguality, extraction quality or completeness against a printed book.
Unreviewed files remain `unsupported` with `language_unknown`. The adapter's PDF
extension is the selected acquisition format, not a verified provider-format claim
for these opaque, uninspected file-page links.

Checked-in reviews live in `ingestion/obuchalka-language-reviews.json`. Optional
`<artifacts_root>/obuchalka/language-reviews.json` uses the same version-1 `files`
mapping, keyed by the stable `https://fileskachat.com/file/ID_HASH.html` URL.
Each review requires `sha256`, `languages` including `tt`, `reviewer` and `reason`.
Record `observed_size`, observed PDF pages and sampled pages when available.
Grant reviews from actual content inspection, never just titles or annotations.
Local entries override matching built-in reviews; removing an override falls
back to the built-in review. Withdraw a built-in review by removing it from the
checked-in file. Decisions refresh before downloads without a catalog rescan.

For an admitted file, acquisition retrieves its stable file page, follows the
ordinary advertised download link, then the explicit direct file link. Literal
link markup inside `document.write` strings is parsed without executing JavaScript.
No CAPTCHA solving, form submission, account, purchase or ad interaction occurs.
Only validated Fileskachat routes and `staticN.fileskachat.com` PDF delivery URLs
with the same numeric file identity are allowed. Known reviewed oversize files are
rejected before network requests. File-page format claims must identify a PDF;
DjVu, Word, archives, other providers and package expansion are outside this slice.
Yandex alternatives remain discovery metadata and are not fetched.

The result retains stable file-page identity, download/direct-link provenance,
provider filename/displayed-size claims, actual final delivery URL and the matching
review SHA-256. Delivery URLs are resolved anew rather than used as durable file
identities. A changed file fails hash validation before publication. The shared
downloader enforces PDF signatures, transport length when supplied, configured
time/byte/disk limits and atomic publication. Originals remain unchanged under
`<artifacts_root>/obuchalka/files/`. Verified local originals are skipped; missing
or corrupt files remain eligible. `--recheck` requests source revalidation.

The initial reviewed sample is the 2023 first-grade literary-reading teaching
guide: 410,886 bytes, 66 PDF pages, SHA-256
`7a6e37cb91ac21ab9a932d034352a621f1d339b93262c262c287aabd84e71abe`.
PDF page 5 contains readable Tatar pedagogical text. Evidence:
`/tmp/obuchalka-adabi-uku-2023.pdf`. No conversion or assembly was used.

Implementation verification on 2026-10-28 completed all 36 category records in
37 CLI requests without errors, yielding 38 stable file-page candidates. Bounded
manual inspection then confirmed ten additional Tatar school-book PDFs, bringing
the checked-in review set to **11 PDFs**. Text samples were inspected for eight
of the 11 reviewed files; three image-only/sparsely extracted books were checked
visually on rendered pages (2017 Татар теле, 2017 Әдәби уку and 2007 Уку китабы).
One alternate sixth-grade delivery page reported a non-PDF format and was not
downloaded. Inspection evidence is under `/tmp/obuchalka-textbook-review/`.

Two CLI acquisitions passed review-hash verification: the 410,886-byte / 66-page
2023 guide above and the 872,299-byte / 52-page fifth-grade guide (2022), SHA-256
`95df80e06a88d85779029ad64098ad781fab0f455649689600c046decbadbeec`.
Each used three retrieval calls through file page, download page and direct file
link. Adding the new reviews refreshed admission without rescanning the catalog;
the full manifest now has two downloaded, nine pending and 27 held candidates.
The remaining nine reviewed files have manual inspection evidence, not CLI
acquisition results. A repeated download before adding reviews skipped the first
verified original with zero network requests.

An isolated single-file CLI check with an intentionally wrong review hash rejected
the complete response before publication, leaving no PDF or partial file. Its
expected error state is under `/tmp/obuchalka-hash-rejection/`; this override is
not part of the checked-in reviews or the operational manifest. Successful CLI
evidence is under `/tmp/obuchalka-verification/`.
