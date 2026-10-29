# KFU «Вакыт» newspaper

`kfu_vakyt` uses the exact `is_part_of_series = Вакыт` search within newspaper
collection `net/86`. Its YAML `archive_url` is
`https://repo.kpfu.ru/jspui/handle/net/86/simple-search` (without query parameters).
The adapter supplies the fixed filter and native ten-record pagination itself;
it does not enumerate the other newspapers in that collection.

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source kfu_vakyt --max-pages 25
.venv/bin/python cli.py --config ingestion.yaml download --source kfu_vakyt --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source kfu_vakyt --max-pages 25 --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source kfu_vakyt
```

Repeated discovery resumes the saved frontier and pending records. The advertised
count (2,233 during inspection), displayed ranges, native next link, unique record
identities, exact series metadata, and final count verification are checked.
A changed count or repeated identity requires a fresh scan. A bounded invocation
is reported as incomplete until all listing pages and records have been checked.

As for Il/Shura, only explicit recognized Tatar item-language labels admit files.
Missing/unknown labels remain `language_unknown`; recognized other languages are
excluded. Titles, script and collection membership do not override this policy.
Metadata and restricted-file inventory are retained; restricted files are not
requested and access follow-up remains deferred.

Readers support numbered JPEG and JPEG2000 ranges, including matching date/issue
prefixes. Native filenames, bitstream sequences, counts and IIIF order must agree.
Originals are retained with hashes, validated by the matching codec and decoded
before publication. Each page must be a single image of at most 150 megapixels;
Pillow's own safety limits remain enabled. Large accepted pages can require
substantial memory, but pages are processed sequentially. Corrupt, oversized or
unsupported pages leave the issue incomplete rather than publishing a partial PDF.

Complete issues use 200 DPI RGB JPEG quality 85, preserving physical page size and
RGB colour profiles. Source DPI must be at least 200 on both axes; no upscaling
or lower-resolution fallback is used. File, transfer, item, disk, deadline and
separate derived-PDF limits apply. One issue consumes one image-download item;
interrupted issues resume from verified originals. Repeat runs verify local hashes
and reuse complete PDFs without network requests; `--recheck` revalidates originals.
Public direct PDFs are preferred when available. Artifacts are stored under
`__artifacts/ingestion/kfu_vakyt/`. See the [earlier pilot](../kfu-vakyt-pilot.md)
for the original investigation; the source is now registered for production use.

Implementation verification inspected 30 native results across three listing pages,
including resumption in a separate invocation without duplicate identities or errors.
A separately selected, explicitly `tt`-labelled `net/26933` issue was observed and
then downloaded through the normal CLI: four originals (15,611,732 bytes) and a
four-page 10,891,710-byte PDF. Every output page measured at least 200 DPI on both
axes. Repeat download reused all four originals and the PDF with zero requests.
The native six-page `net/7229` JPEG2000 reader enumerated correctly; its existing
121.9-megapixel research original passed full codec validation. That unlabelled
issue remained held. The full 2,233-record scan and a complete eligible JPEG2000
issue download were not performed. Compilation, diff checks, and manual CLI
verification passed; no automated tests were added.
