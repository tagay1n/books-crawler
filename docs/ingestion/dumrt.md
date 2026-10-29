# DUM RT contemporary Tatar publications

`dumrt` covers two native publisher archives: «Дин вә мәгыйшәт» newspaper and
the contemporary «Шура» almanac. The latter is distinct from `kfu_shura`'s historical
collection. Configure the primary archive; discovery also follows the explicitly
selected almanac archive on the same publisher website:

```yaml
sources:
  dumrt:
    archive_url: https://dumrt.ru/media/din-va-magishet/
```

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source dumrt --max-pages 40
.venv/bin/python cli.py --config ingestion.yaml download --source dumrt --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source dumrt
```

Use a YAML page cap of at least 40 for that discovery command, or use smaller
batches and resume. Native `curPos`/`cur_cc` pagination, issue cards and record
identifiers are retained. Only PDF links/objects in each record's attachment area
are acquired; related publications, covers and footer links are excluded. Older
launch announcements with no PDF remain metadata. Posting dates remain source
text and are not treated as printed issue dates: for example, almanac №51 was
posted in December 2025 but its PDF identifies January–March 2026.

The publisher's [activity report](https://dumrt.ru/netcat_files/multifile/2627/otchet_DUM_2018.pdf)
identifies both publication series as Tatar-language media. This series-level
claim and content samples establish admission; individual file composition is
not verified by the website's Tatar interface or a filename. Arabic quotations
and other languages can occur. Language evidence and raw source links remain in
metadata. The inspected originals download anonymously without registration or payment.

Requests stay on native HTTPS archive/record routes and original PDF storage.
Canonical record URL claims are checked when provided; legacy pages can omit
them. PDFs use `/netcat_files/`, `/files/pdf/` or the advertised legacy `/pdf/`
paths. A narrowly scoped repair removes one dangling quote after `.pdf` in legacy
`/files/pdf/` links, retaining the literal URL and `source_url_repair` evidence.
The inspected malformed target returned 403; its quote-free original returned a
complete Tatar newspaper PDF. Missing issue numbers and filenames are not guessed.

Final manual CLI discovery on 2026-10-28 completed 37 archive pages and 235 records,
exposing 227 PDF asset candidates with no remaining frontier or discovery errors.
Three isolated CLI acquisitions verified:

- Newspaper №12 (353), December 2024: 4,533,125 bytes / 16 pages, SHA-256
  `2b4f0dcec0bc1391c9797513bbc9cfd46813496e9f2d255a6cd16aba6fde253c`.
- Almanac №54: 6,259,590 bytes / 130 pages, SHA-256
  `d2aaefdc1f7e5a59ef3daf6f61a0cb1b16a31d32c926bad84894a2e7830c0c4e`.
- Repaired 2013 newspaper №7 (202): 8,375,447 bytes / four pages, SHA-256
  `6b2b92c710bf318fcc9065e87a4788178dd65e316ddc1967a8e3917c5772f0a0`.

Rendered samples contain Tatar text; old files can have legacy-font extraction
errors. A repeat skipped all three originals with zero requests. Separate manual
samples also verified the 2011 legacy storage path and almanac №51. Evidence is
under `__artifacts/session-20261028/`, with CLI samples under `dumrt-samples/`.
The full discovery manifest's files remain pending; sample acquisitions use an
isolated manifest. Full-file availability, language composition of remaining
files and printed-edition completeness are unverified. No bulk acquisition,
archive expansion, PDF assembly or original-file modification is introduced.
