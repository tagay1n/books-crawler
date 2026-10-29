# Turuz dictionaries

Add this entry under `sources` in your selected operational YAML:

```yaml
turuz:
  archive_url: https://turuz.com/index/pitik/category/2
```

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source turuz --max-pages 1
.venv/bin/python cli.py --config ingestion.yaml download --source turuz --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source turuz
```

This initial slice covers the single native dictionary-category table, not the
whole Turuz library. One collection record retains individual dictionary cards,
raw row numbers, titles, formats, displayed sizes, links and selection decisions.
The manifest's record count is therefore a collection count, not a book count.
Discovery inspects the listing twice (enumeration and metadata observation).
Displayed row numbers are provenance, not permanent book identifiers; asset URLs
identify files, and duplicate selected file URLs share one acquisition entry.

Selection requires a dictionary title beginning with `Tatar`, `Tatarca` or
`Lehceyi Tatari`, allowing accents, spaces, hyphens and underscores. Explicit
Crimean Tatar titles and general multilingual titles are excluded. Tatar–English
and Tatar–Turkish dictionaries are included. These are catalog language
claims, not verified monolingual Tatar content. Every keyword-matching row,
including exclusions, remains in collection metadata for review. Unlabelled
works and Tatar titles elsewhere on the site are outside this slice.

Only same-origin HTTPS `/storage/` PDF, DjVu and Word files are acquired.
RAR/archive links remain unsupported in the manifest; no package expansion,
executable content, reader conversion, account or external delivery is used.
Source checksums are not supplied by this listing: the shared downloader checks
transport length when available, file signatures, local SHA-256/MD5, configured
byte/time/disk limits and atomic publication. These checks do not establish
completeness against a printed edition. Originals are retained unchanged under
`<artifacts_root>/turuz/files/`, alongside `manifest.json` and metadata observations.
Ordinary repeated downloads skip verified local files; missing/corrupt files are
eligible again. `--recheck` requests source revalidation. Run discovery again to
refresh the collection observation and mark removed links inactive.

Pre-implementation access checks downloaded two complete PDFs: the Tatar–English
dictionary (9,929,569 bytes, 103 PDF pages) and Tatar–Turkish dictionary (624,650
bytes, 178 pages). The first record claims 200 pages; preserve that claim separately
from observed PDF pages. Its scan has noisy OCR; the smaller Latin-script
dictionary exposes readable bilingual text. This is not an assessment of every
file's extraction quality, edition completeness, reuse rights or unique coverage.

Manual adapter verification on 2026-10-28 completed discovery in two requests:
18 keyword rows, 13 selected file URLs, 11 eligible originals and two unsupported
RAR links. Five rows were excluded (including duplicated general multilingual
links and explicit Crimean Tatar titles). In an isolated single-asset copy of the
live manifest, CLI acquisition saved the complete 624,650-byte / 178-page
Tatar–Turkish PDF with SHA-256
`7c272fcff13f159342972e8d6d6aff3db96deece71e21d24eb0b8f1565d5a9a3`,
matching the earlier independent sample. A repeated CLI download skipped it with
zero network requests. Evidence is under `/tmp/turuz-verification/` (full
discovery) and `/tmp/turuz-small-verification/` (isolated PDF acquisition/reuse).
The full-discovery manifest also acquired the first phraseological-dictionary
DjVu unchanged: 24,682,420 bytes, SHA-256
`cdd230c94398d507a2d3637264086048964d91a1505056f23170f60deadb0fbf`.
`djvused` opened it and reported 494 pages. That transfer took approximately
188 seconds; allow sufficient deadline for larger files. Word originals and the
remaining file layouts have not been verified through acquisition.
