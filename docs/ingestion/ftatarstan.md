# Fänni Tatarstan issue PDFs

`ftatarstan` uses the journal's new official OJS website, separately from the
IYALI electronic-library catalog. The previous `ft.antat.ru` domain published a
migration notice; its sampled live routes currently return 502. Configure:

```yaml
sources:
  ftatarstan:
    archive_url: https://ftatarstan.ru/index.php/ftat/ru/issue/archive
```

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source ftatarstan --max-pages 3
.venv/bin/python cli.py --config ingestion.yaml download --source ftatarstan --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source ftatarstan
```

Discovery follows the native archive pager and issue title links, then resolves
advertised full-issue PDF viewers to their explicit original download links.
Native issue and galley identifiers are retained; redirects must preserve the
selected identity and remain on the configured HTTPS journal routes. No download
URL is guessed. Source title/date/DOI, raw galley language labels and catalog
context remain separate from actual file size, hashes and final download URL.

Only whole-issue galleys labelled `PDF (татарский)` are acquired, case-insensitively.
The website's Russian interface and Russian article titles do not determine PDF
language. Issues can contain Russian/English abstracts and references alongside
Tatar scientific text. Article PDFs and covers are excluded; missing full-issue
files remain metadata, and an unlabelled `PDF` galley remains unsupported. No
author registration or login is used; account navigation does not imply that
the anonymously downloadable originals require registration.

Manual CLI discovery on 2026-10-28 completed three archive pages and 51 issue
records, spanning source titles from 2014 through 2026: 49 full-issue PDF galleys,
48 explicitly Tatar-labelled and one unlabelled/held. Two issues have no full-issue
PDF in the inspected native contents (№ 4 of 2023 and № 2 of 2020).
CLI acquisition verified № 3 (2026): 8,714,023 bytes / 196 PDF pages, SHA-256
`d0db9116e265154bf764e61ed027837fb75364e8db513fed3937b97cf1a45a09`.
Extracted and rendered page 6 contains Tatar, Russian and English text. Its hash
matches the separate prior anonymous download. An isolated replay skipped the
verified original with zero requests. Evidence: ignored
`__artifacts/session-20261028/ftatarstan/` and session logs. Remaining PDFs and
printed-edition completeness remain unverified; no bulk acquisition was performed.
