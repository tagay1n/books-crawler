# Tugan Zhir archive

`tuganzhir` uses the publisher's public [journal archive](https://tuganzhir.org/archive/).
It retains one archive observation and each explicitly linked original issue PDF,
including special issues. The observed archive has 36 distinct PDF links spanning
2017–2026. This is a listing count, not verification that all files are reachable.
No missing issue numbers or dates are inferred from filenames or upload paths.

```yaml
sources:
  tuganzhir:
    archive_url: https://tuganzhir.org/archive/
```

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source tuganzhir --max-pages 1
.venv/bin/python cli.py --config ingestion.yaml download --source tuganzhir --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source tuganzhir
```

The 2022 issue's imprint (PDF page 5) explicitly declares Tatar and Russian.
Rendered pages from that issue and the first 2017 issue contain Tatar articles;
the 2017 imprint also declares both languages. Admission is based on the
publisher's bilingual series, not its subject or website language. Individual
issue language proportions and printed-page completeness remain unverified.
The evidence URL, page and inspected file hash are retained in observations.

Only PDFs linked inside the archive's issue rows are selected. Raw labels,
year headings, rows and advertised size claims are preserved. Covers, HTML
articles and the separate electronic library are excluded. Native upload paths
on `tuganzhir.org`, `tatar-congress.org` and the explicitly advertised
`tatarcongress.firsts3.ru` storage host are supported. Other delivery locations
are retained as unsupported. Requests use GET only and reject redirects that
change the selected resource; no guessed mirrors or account access are used.
Shared streaming, file caps, PDF signature checks, hashing and repeat-run
skipping apply. New archive pagination or changed row structure requires review.

Manual samples in `__artifacts/session-20261028/`:

- №1 (2022): 2,170,679 bytes / 264 PDF pages, SHA-256
  `70c572cd1cdb747214419b9dd6711394eee8165b4f1bd4ef698700cc3af2412b`;
  rendered PDF page 49 has Tatar narrative.
- №1 (2017): 1,506,264 bytes / 148 PDF pages, SHA-256
  `8795293f00ce54cd8a3b2c0fae52828da91f96bbc3d38c7653a0e0f0558a16c7`;
  rendered PDF page 34 has Tatar narrative.

Live CLI discovery completed one archive page with 36 eligible PDFs and no errors.
The two selected samples were acquired with matching hashes from the native and
storage hosts. A repeat run skipped both with zero requests. Samples remain in
`tuganzhir-samples/`; the full catalog remains pending for bounded future runs.
