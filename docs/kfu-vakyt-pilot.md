# KFU «Вакыт» acquisition pilot

Historical report. The follow-up implementation now registers `kfu_vakyt`, adds
filtered-search traversal and validated JPEG2000 acquisition, and keeps the
explicit item-language policy below. See [current usage](ingestion/kfu-vakyt.md).
Statements about deferred production support describe the pilot stage.

Date: 2026-10-27. This is a bounded investigation, not a registered production
source or a full collection crawl. The current explicit Tatar language policy
remains in effect. No automated tests were added.

## Scope and language evidence

The [native series search](https://repo.kpfu.ru/jspui/handle/net/86/simple-search?filterquery=%D0%92%D0%B0%D0%BA%D1%8B%D1%82&filtername=is_part_of_series&filtertype=equals)
advertised 2,233 records. Its visible pagination uses ten results per page and a
`start` offset while retaining the exact `is_part_of_series = Вакыт` filter.

The pilot inspected the first ten relevance-sorted results and one separately
selected, already known Tatar-labelled issue. This is a targeted sample; its
eligibility counts must not be extrapolated to all 2,233 catalog records.

| Cohort | Records | Source language | Page assets | Admission |
| --- | ---: | --- | --- | --- |
| First native search page | 10 | No `DC.language` supplied | 44 advertised JPEG2000 pages | All held as `language_unknown` |
| Known `net/26933`, №125, 1907 | 1 | `tt` | Four public JPEG pages; restricted ZIP | Admitted for image acquisition |

The held handles are `net/7229`, `net/7231`, `net/7230`, `net/7227`, `net/7228`,
`net/7223`, `net/7224`, `net/7226`, `net/7225`, and `net/7294`. Native metadata and
per-file access descriptions are retained. The record's Tatar title, series name,
and script are not substituted for a missing document-language label.

## Complete labelled issue

[№125, 1907 (`net/26933`)](https://repo.kpfu.ru/jspui/handle/net/26933) exposes an
ordered four-page JPEG reader with filenames `1907-125-1.jpg` through
`1907-125-4.jpg`. Its ZIP package is restricted and was not downloaded.

The shared KFU reader was extended to recognize a matching literal prefix before
the numbered filename suffix. Prefix, extension, padding, count, bitstream range,
and IIIF canvas order must still agree. Existing plain numbered sets retain the
same filenames and asset identities. JPEG2000 sets remain unsupported by the
production reader; this change adds prefixed JPEG ranges only.

The pilot retained all four original JPEGs (15,611,732 bytes total) and produced
a complete four-page PDF of 10,891,710 bytes using the existing 200 DPI RGB,
JPEG-quality-85 policy. Measured effective resolution was at least 200 DPI on
both axes for every PDF page. The source scans are grayscale; no additional
grayscale conversion was introduced. Original hashes, page order, and the
assembly input fingerprint remain in the pilot manifest.

Acquisition used two reader/manifest requests and four file requests without
retries or errors. Poppler rendering was inspected for all four pages. A repeat
acquisition reused all four verified images and the derived PDF with zero network
requests. The ten unlabelled records remain unsupported with no acquired issue.

## JPEG2000 conversion research

One public page from the held
[1906 №109 record (`net/7229`)](https://repo.kpfu.ru/jspui/handle/net/7229) was
downloaded separately for codec research. It is explicitly marked as a research
page sample, outside the issue-acquisition manifest. The six-page issue was not
admitted or assembled.

| Measurement | Result |
| --- | --- |
| Native page | `1906-109-1.jp2`, 16,416,960 bytes |
| Source pixels and resolution | 9,236 × 13,196, approximately 600 DPI |
| Source colour mode | Grayscale (`L`) |
| Derived research PDF | One page, 2,367,199 bytes |
| Output policy | RGB JPEG, quality 85, at least 200 DPI |

The installed Pillow/OpenJPEG stack decoded the original and the existing
colour-page conversion function produced a usable PDF. Poppler rendering was
visually inspected. This establishes feasibility for this page, not complete
production JPEG2000 support or OCR accuracy. The 121.9-megapixel input triggers
Pillow's large-image warning; memory bounds need attention in any production
decoder. Image safety limits were not disabled.

## Local evidence and next decision

Evidence is under `__artifacts/kfu-vakyt-pilot/`:

- `metadata-sample.json`: all eleven inspected records and language decisions.
- `acquisition/manifest.json`: ten held records, four retained JPEGs, and one
  complete issue PDF in `derived/`.
- `acquisition-summary.json` and `reuse-summary.json`: transfer and reuse evidence.
- `research/report.json`: native JPEG2000 dimensions, DPI, hashes, sample-only
  status, and conversion measurements.
- `research/1906-109-1-research-only-200dpi-colour.pdf`: research page output.

The pilot is complete. A production `kfu_vakyt` CLI source is deliberately not
registered. Further work needs a decision on language admission when item labels
are missing, plus native filtered-search pagination and bounded JPEG2000 reader
acquisition/validation. The shared JPEG filename-prefix improvement is ready for
use by existing KFU readers. No full-archive download, language-policy override,
or acquisition of the held issues was performed.
