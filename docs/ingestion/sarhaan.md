# Sarhaan Tatar publications

`sarhaan` discovers the publisher's native Tatar category, including its advertised
pagination, and stores each book separately. Configure `sources.sarhaan.archive_url`
as `https://sarhaan.com/a/tatar-%d8%aa%d8%aa%d8%a7%d8%b1%d9%8a/` in an explicitly
selected operational YAML, using the usual local limits and network settings.

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source sarhaan
.venv/bin/python cli.py --config ingestion.yaml download --source sarhaan --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source sarhaan
```

Acquisition requires matching explicit Tatar labels in the book hero and detail
metadata, plus an individually advertised PDF filename and format. Arabic-alphabet teaching
records are held for individual file-language review despite category labels. Category
membership alone does not admit Arabic or other language editions. Individual
image, office and audio files are retained as excluded-file metadata; generic
Download All links are not followed. No package expansion or PDF assembly occurs.
These are publisher language claims, not verified monolingual content: sampled
PDFs include Arabic quotations alongside Cyrillic Tatar text.

Only native HTTPS category, book and selected download routes are allowed.
Observed `/page/N/` redirects preserve category-page identity; download redirects
must preserve their package ID, and supplied delivery filenames must match the
selected file. Source filename, size/date descriptions and raw links are retained
separately from actual download size, hashes, MIME and final URL. No registration,
ad links, social sharing, favorites or subscription controls are used.

Manual verification on 2026-10-28 traversed seven category pages and all 79 book
records: 74 individual PDF candidates: 69 admitted by item-language labels and
five held (one other-language record and four files in Arabic-alphabet teaching
records requiring individual review). Two complete originals were acquired through
the shared CLI; the alphabet sample is now held. A replay restricted to the
remaining admitted verified sample skipped it with zero requests.
Separate initial inspection of `Карун` verified a 6,597,204-byte, seven-page PDF,
SHA-256 `ce15586942c9c318a10c21248672499e6d3f7101d7f98094ac2f12de0e260293`;
rendered page 5 contains Tatar and Arabic. Sample text extraction was empty, so
download success does not establish OCR quality. Evidence is under the ignored
`__artifacts/session-20261028/` directory. Full acquisition and per-file language
composition remain unverified.
