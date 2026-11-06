# Source discovery reviews

Use this register when asked to pick the next source and check whether document
discovery still makes sense. It covers all shared CLI sources in
`ingestion/registry.py`, including Common Crawl, Milli Kitaphana and Litres. Keep separate
rows for adapters on the same website because their scopes and filters differ.
Add a row when a new source is implemented; unimplemented candidates remain in
their existing inventory.

All initial last-reviewed dates are **2026-11-06**, at the owner's request.
These are rotation baseline dates, not evidence of fresh audits on that day.
`Baseline` means no audit has yet been recorded in this register. Existing source
guides and the historical [source review log](archive/source-investigations.md#autonomous-source-review-2026-10-28) provide
background; their checks do not establish current discovery completeness.

## Choose the next source

Choose the eligible row with the oldest last-reviewed date, breaking ties
alphabetically by source ID. Review one source per request. Skip a source only
while a documented blocker prevents a substantive review; record its prerequisite
in the table and reconsider it when that prerequisite becomes available. If all
remaining sources are blocked, report the blockers rather than advancing dates.
Known gaps stay visible in the findings column but do not override the rotation.
Explicit owner deferrals are excluded until their stated reactivation condition
is met; preserve their review dates and record the decision in history.

## Register

Dates use `YYYY-MM-DD`. Outcomes are `Baseline`, `Reviewed`, `Partial`, or
`Blocked`, or `Deferred`; a completed review may still have documented limitations or follow-ups.
For partial or blocked attempts, preserve the last completed review date (or
initial baseline date) and record the attempt date in the history below.

| Source ID | Source guide | Last reviewed | Outcome | Outstanding findings / blockers |
| --- | --- | --- | --- | --- |
| `beznenmiras` | [Безнең мирас](ingestion/beznenmiras.md) | 2026-11-06 | Partial | 2026-11-07: metadata preservation extended; sampled issues expose no originals. PostgreSQL/S3 verification requires credentials and a downloadable sample. |
| `common_crawl` | [Common Crawl / FinePDFs](ingestion/common-crawl.md) | 2026-11-06 | Deferred | 2026-11-07: owner deferred this valuable special source. Resume only on explicit owner request; exclude from ordinary source rotation. |
| `commons` | [Wikimedia Commons](ingestion/commons.md) | 2026-11-06 | Partial | 2026-11-07: 35 originals discovered; one PDF checksum verified; canonical record URLs fixed. Live PostgreSQL/S3 and repeat-run checks require credentials. |
| `darul_kutub` | [Darul-Kutub](ingestion/darul-kutub.md) | 2026-11-06 | Partial | 2026-11-07: catalog/article context and chapter metadata retention fixed; one original PDF verified. Full scan and live PostgreSQL/S3/repeat-run checks remain outstanding. |
| `dumrt` | [DUM RT publications](ingestion/dumrt.md) | 2026-11-06 | Baseline | — |
| `echovek` | [Echo of Centuries](ingestion/echovek.md) | 2026-11-06 | Baseline | — |
| `ftatarstan` | [Fänni Tatarstan](ingestion/ftatarstan.md) | 2026-11-06 | Baseline | — |
| `internet_archive` | [Internet Archive](ingestion/internet-archive.md) | 2026-11-06 | Baseline | — |
| `isxaki` | [Isxaki](ingestion/isxaki.md) | 2026-11-06 | Baseline | — |
| `kazanutlary` | [Kazan Utları](ingestion/kazanutlary.md) | 2026-11-06 | Baseline | — |
| `kfu_azad_halyk` | [KFU «Азад халык»](ingestion/kfu-azad-halyk.md) | 2026-11-06 | Baseline | — |
| `kfu_books` | [KFU books](ingestion/kfu-books.md) | 2026-11-06 | Baseline | — |
| `kfu_dspace` | [KFU academic archive](ingestion/kfu-dspace.md) | 2026-11-06 | Baseline | — |
| `kfu_il` | [KFU «Ил»](ingestion/kfu-il.md) | 2026-11-06 | Baseline | — |
| `kfu_manuscripts` | [KFU manuscripts](ingestion/kfu-books.md) | 2026-11-06 | Baseline | — |
| `kfu_repository` | [KFU historical repository](ingestion/kfu-repository.md) | 2026-11-06 | Baseline | — |
| `kfu_shura` | [KFU «Шура»](ingestion/kfu-shura.md) | 2026-11-06 | Baseline | — |
| `kfu_vakyt` | [KFU «Вакыт»](ingestion/kfu-vakyt.md) | 2026-11-06 | Baseline | — |
| `litres` | [Litres](ingestion/litres.md) | 2026-11-06 | Baseline | — |
| `magarif` | [Мәгариф](ingestion/magarif.md) | 2026-11-06 | Baseline | — |
| `magarif_vakyt` | [Мәгариф–Вакыт](ingestion/magarif-vakyt.md) | 2026-11-06 | Baseline | — |
| `milli_kitaphana` | [Milli Kitaphana](ingestion/milli-kitaphana.md) | 2026-11-06 | Baseline | — |
| `miras` | [Miras books](ingestion/miras.md) | 2026-11-06 | Baseline | — |
| `miras_periodicals` | [Miras periodicals](ingestion/miras-periodicals.md) | 2026-11-06 | Baseline | — |
| `nizgar` | [Nizgar](ingestion/nizgar.md) | 2026-11-06 | Baseline | — |
| `obuchalka` | [Obuchalka](ingestion/obuchalka.md) | 2026-11-06 | Baseline | — |
| `sarhaan` | [Sarhaan](ingestion/sarhaan.md) | 2026-11-06 | Baseline | — |
| `tatargalyame` | [Tatar Galyame](ingestion/tatargalyame.md) | 2026-11-06 | Baseline | — |
| `tatarica` | [Tatarica](ingestion/tatarica.md) | 2026-11-06 | Baseline | — |
| `tataroved` | [Tataroved](ingestion/tataroved.md) | 2026-11-06 | Baseline | — |
| `tatkniga` | [Tatkniga](ingestion/tatkniga.md) | 2026-11-06 | Baseline | — |
| `tuganzhir` | [Tugan Zhir](ingestion/tuganzhir.md) | 2026-11-06 | Baseline | — |
| `turuz` | [Turuz](ingestion/turuz.md) | 2026-11-06 | Baseline | — |
| `yazuchy` | [Yazuchy](ingestion/yazuchy.md) | 2026-11-06 | Baseline | — |

A dash means no finding has been entered here; read the source guide for existing
limitations and access requirements before beginning a review.

## Review one source

1. Read its guide and discovery/admission implementation. For shared ingestion,
   start with the [adapter development map](adapter-development.md) and summarize
   available manifests with `scripts/ingestion_overview.py` before inspecting
   targeted observations. Use `.venv/bin/python` where available.
2. Explore the current source independently of the crawler's known routes.
   Inspect native navigation, search, archives, pagination, and alternative
   document surfaces where available. Compare these with configured seeds and
   traversal assumptions; a successful scan of known routes alone is insufficient.
   For Common Crawl, examine dataset selection, language/script filters, shard
   coverage, and indexing assumptions rather than treating it as a single website.
3. Compare live evidence with discovered records and admission decisions. Sample
   rejected, unlabelled, and held records for missed Tatar documents; distinguish
   document language from subject or interface language. Check newly found routes
   and supported file/reader formats without assuming every exposed item qualifies.
4. Fix confirmed discovery or filtering gaps and verify with bounded manual/CLI
   checks in isolated ignored artifacts. Check representative included and excluded
   records and, where relevant, pagination/resume behavior. Follow source access
   restrictions and existing deferrals; record unavailable access as a blocker.
   Do not add automated tests, perform bulk acquisition, or publish remotely.
5. Append a dated history entry and update the table outcome and outstanding
   findings. Advance the last-reviewed date only after a substantive completed
   audit, including verification of any fixes. Record partial or blocked attempts
   without advancing it. A completed bounded review does not establish exhaustive
   site coverage; describe the sampled scope and remaining limitations explicitly.

## Review history

### 2026-11-07 — common_crawl — Deferred by owner

Owner requested deferral because Common Crawl is a valuable special source needing
separate attention. Preserve the baseline review date; this is a prioritization
decision, not a completed audit or an access failure. Reactivation requires an
explicit owner request. Next eligible candidate after the recorded Безнең мирас
attempt is `commons` (Wikimedia Commons), under the same ingestion requirements.

Append one short entry per completed or attempted review
with the following information; keep earlier entries as historical evidence:

- Date, source ID, and outcome.
- Scope examined: live routes, filters, and representative records checked.
- Findings and fixes, with relevant code/commit or source-guide references.
- Verification commands, compact results, and evidence artifact paths. Keep
  credentials, private configurations, and downloaded originals out of Git.
- Remaining limitations, follow-ups, or blockers and their prerequisites.

### 2026-11-07 — beznenmiras — Partial

Inspected native homepage navigation, all three archive listing pages (41 cards),
October 2026 and April 2023/2024 issue pages, robots, sitemap index and custom-page
sitemap. No issue originals or embedded readers were found in the sampled issue
content; policy PDFs and covers remain excluded. Parser version 2 preserves
publisher HTML, lead, subscription-index paragraphs, page metadata and content/
reader links without changing record identities. Existing shared local download,
S3 publication, PostgreSQL state and manual Actions wiring are retained.

Bounded `cli.py inspect` requests and configured parser invocations verified listing
pagination and metadata extraction; module compilation and workflow/configuration
inspection passed. See the [source guide](ingestion/beznenmiras.md) for evidence
paths and run commands. No automated tests were added. No production writes,
publication or workflow dispatch occurred. Missing database/S3 credentials and
the absence of a verified original prevent live persistence/resume and transfer/
receipt verification. Preserve the baseline date until those checks are possible;
the bounded route review does not establish exhaustive site coverage.

### 2026-11-07 — commons — Partial

Inspected the native Tatar-language books category and its API category tree:
five listing batches, 40 requests, 35 original document records (34 PDF, one
DjVu), no remaining frontier. Two root images and one subcategory image stayed
excluded. All returned extended file metadata was retained. Category membership
remains admission evidence rather than verified per-file language/completeness.
Fixed literal configuration text in canonical record URLs; parser version 4
refreshes observations without changing `file:<id>` identities.

A bounded 247,549-byte PDF sample matched publisher size/SHA-1 and rendered as
Tatar on its imprint page. Evidence and hashes are in the
[source guide](ingestion/commons.md) and ignored
`__artifacts/commons-review-20261107/`. Live metadata parsing, compilation,
capability/configuration and workflow generator checks passed; no automated tests
were added. Existing PostgreSQL, S3 and manual Actions integration is retained.
No production database writes, S3 publication or workflow dispatch occurred.
Full persistence/resume, database-backed acquisition and repeat-run/upload receipt
verification still require configured database/storage credentials; preserve the
last-reviewed baseline date until that verification is available.

### 2026-11-07 — darul_kutub — Partial

Inspected main search, its native books filter, two adjacent main catalog pages,
and representative journal/book pages (3160 and 2245). Main search advertises
15,573 rows and the books filter 1,591; neither is a verified unique-publication
count. Forty sampled article rows now retain their bibliography and parent issue
relationships through catalog context. Parser version 2 also preserves chapter
JSON, badges, subjects and descriptive HTML; native identities and original-file
selection remain unchanged. Both publication samples expose direct PDFs.

One bounded original transfer acquired a valid 7,823,809-byte, 29-page PDF with
complete declared length. Hashes, render findings, commands and evidence paths
are recorded in the [source guide](ingestion/darul-kutub.md). No full catalog
scan, production state writes, S3 uploads or workflow dispatch occurred. Manual
pagination/metadata inspection, compilation and workflow/configuration checks
passed; no automated tests were added. Existing PostgreSQL/S3/manual workflow
integration is retained. Database/storage credentials are required for durable
resume, full acquisition, repeat-run and receipt verification; preserve the
baseline review date pending that work and broader catalog coverage.
