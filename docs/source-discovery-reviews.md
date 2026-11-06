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
| `dumrt` | [DUM RT publications](ingestion/dumrt.md) | 2026-11-06 | Partial | 2026-11-07: 37 archive pages/235 issue URLs; metadata retention extended and one original verified. Full issue/attachment refresh and live PostgreSQL/S3/repeat-run checks remain outstanding. |
| `echovek` | [Echo of Centuries](ingestion/echovek.md) | 2026-11-06 | Partial | 2026-11-07: 64 listing pages/1,385 records; abstract/raw-field retention extended; one original verified. One unresolved card; full detail/admission and live PostgreSQL/S3 checks remain outstanding. |
| `ftatarstan` | [Fänni Tatarstan](ingestion/ftatarstan.md) | 2026-11-06 | Partial | 2026-11-07: 51 issue pages/48 admitted galleys; contents metadata preserved and one original verified. One unlabelled galley and two missing issue files; live PostgreSQL/S3/repeat-run checks remain outstanding. |
| `internet_archive` | [Internet Archive](ingestion/internet-archive.md) | 2026-11-06 | Partial | 2026-11-07: 20 item inventories expose 47 eligible original PDFs; one verified. File-only scope/counts documented. Full scan, held-record sampling and live PostgreSQL/S3/repeat-run checks remain outstanding. |
| `isxaki` | [Isxaki](ingestion/isxaki.md) | 2026-11-06 | Partial | 2026-11-07: five collections/63 unique file URLs; card metadata extended and one original verified. Sixteen cards lack file links; remaining file availability and live PostgreSQL/S3/repeat-run checks remain outstanding. |
| `kazanutlary` | [Kazan Utları](ingestion/kazanutlary.md) | 2026-11-06 | Baseline | — |
| `kfu_azad_halyk` | [KFU «Азад халык»](ingestion/kfu-azad-halyk.md) | 2026-11-06 | Partial | 2026-11-07: all 15 public PDFs inventoried; direct-file policy enforced and one original verified. Remaining downloads and live PostgreSQL/S3/repeat-run checks remain outstanding. |
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

### 2026-11-07 — dumrt — Partial

Native homepage navigation confirms both archives. Bounded listing traversal
completed 37 pages and 235 issue URLs (187 newspaper, 48 almanac) with no remaining
frontier. Four issue samples cover contemporary publications, a 2011 newspaper
and a metadata-only launch announcement. Three expose original PDFs; the launch
announcement correctly remains metadata-only. Parser version 3 preserves raw
titles, description HTML, page metadata, size labels, listing cover URLs and
attachment evidence without changing identities or file selection.

One complete newspaper original was verified locally (4,533,125 bytes, 16 pages,
SHA-256 matching the prior review); rendered text is Tatar. See the
[source guide](ingestion/dumrt.md) and ignored
`__artifacts/dumrt-review-20261107/` for evidence, hashes and commands. Compilation,
metadata/pagination inspection, capability/configuration and manual workflow
generation checks passed. No automated tests were added. Existing PostgreSQL,
S3 and manual Actions integration is retained. No production database writes,
uploads or workflow dispatch occurred. Individual remaining issues/attachments,
durable resume, repeat-run skipping and S3 receipts remain unverified; the latter
checks need configured credentials. Preserve the baseline review date pending
that verification.

### 2026-11-07 — echovek — Partial

Inspected native homepage navigation, all three archive pages and 61 publication
pages: 1,375 article URLs and ten metadata-only books, no remaining listing
frontier, one distinct malformed article card without a node identifier retained
as unresolved evidence. Parser version 2 preserves issue-card/article abstracts,
raw labelled bibliography/HTML links, cover URLs and page metadata, keeping node
identities, explicit Tatar admission and article-only acquisition unchanged.
All retained listing pages were re-parsed to verify abstract context retention.

Representative Tatar and Russian article pages preserved admission/exclusion;
a publisher book remained metadata-only. A complete 1,811,915-byte, ten-page
article PDF matched the prior SHA-256 and rendered Tatar body text. See the
[source guide](ingestion/echovek.md) and ignored
`__artifacts/echovek-review-20261107/` for evidence. Compilation, metadata and
workflow/configuration checks passed; no automated tests were added. Full detail
and unknown-language admission coverage was not refreshed. Database/storage
credentials remain prerequisites for live persistence/resume, full acquisition,
repeat-run and S3 receipt checks. Existing shared integration is retained. No
production writes, remote uploads or GitHub dispatch occurred; preserve the
baseline review date pending remaining verification.

### 2026-11-07 — ftatarstan — Partial

Native homepage navigation confirms the configured archive. Three archive pages
and all 51 issue pages were inspected (55 requests including one retry): 49
full-issue galleys, 48 explicitly Tatar-labelled and one unlabelled/held; two
issues have no full-issue file. Parser version 2 preserves all 111 exposed article
cards as contents evidence, listing/issue covers, descriptions and attachment
locators. Issue/galley identities, Tatar-label admission and whole-issue-only
acquisition remain unchanged. Article PDFs and cover images stay excluded.

One viewer resolved to its advertised original; a complete 8,714,023-byte,
196-page PDF matched the earlier sample hash. See the
[source guide](ingestion/ftatarstan.md) and ignored
`__artifacts/ftatarstan-review-20261107/` for commands, hashes and evidence.
Metadata/count checks, compilation and workflow/configuration verification
passed; no automated tests were added. Other viewers were not resolved or
acquired. Existing PostgreSQL/S3/manual Actions integration is retained; live
durable resume, database-backed acquisition, repeat-run skipping and upload
receipts require credentials. No production writes, uploads or workflow dispatch
occurred. Preserve the baseline date pending remaining verification.

### 2026-11-07 — internet_archive — Partial

Owner clarified that outputs must be downloadable document files, without webpage
text extraction or HTML conversion. Existing original-file admission already
enforces that scope. Parser version 2 adds eligible/held/ignored file counts and
an explicit note when no eligible original exists; item/file identities, source
metadata preservation and size/MD5 integrity rules are unchanged.

Two search pages enumerated 200 identifiers; 20 item inventories were inspected
in 22 requests without errors or retries. They expose 47 eligible original PDFs
and 567 ignored entries, with no held originals in this sample. The advertised
5,343 items are not a downloadable-file count. One 1,945,345-byte, eight-page PDF
was acquired and verified against Archive's size/MD5, including exact Unicode
filename identity across a storage redirect. The other files remain unverified
candidates. See the [source guide](ingestion/internet-archive.md) and ignored
`__artifacts/internet-archive-review-20261107/` for evidence and hashes.

Compilation, parsing/counts/integrity and workflow/configuration checks passed;
no automated tests were added. Existing PostgreSQL/S3/manual workflow integration
is retained. Full discovery, held/unknown-language sample coverage, database-backed
resume/acquisition, repeat-run and S3 receipt verification remain outstanding;
live database/storage checks need configured credentials. No production state,
uploads or workflow dispatch occurred. Preserve the baseline review date pending
remaining verification.

### 2026-11-07 — isxaki — Partial

Live entry-point navigation and all five configured collections were inspected
in six requests without retries: 83 cards, 64 eligible document relationships,
63 unique URLs. Sixteen cards have no supported file link; two expose a malformed
`http://3hatinile` target that is retained as evidence and never requested.
Parser version 2 preserves description HTML, cover URLs, non-document link
evidence, card acquisition notes and per-collection file counts. Existing file
selection/identities and the file-only output scope remain unchanged.

A complete 437,423-byte, five-page publisher-linked «Мансур» PDF passed transfer
length/format checks and rendered Tatar body text. See the
[source guide](ingestion/isxaki.md) and ignored
`__artifacts/isxaki-review-20261107/` for hashes and evidence. Compilation,
metadata/file-count and workflow/configuration checks passed; no automated tests
were added. Existing PostgreSQL/S3/manual workflow integration is retained.
Other originals were not freshly acquired; database/storage credentials remain
prerequisites for live persistence/resume, full acquisition, repeat-run and S3
receipt verification. No production writes, uploads or workflow dispatch occurred.
Preserve the baseline review date pending remaining verification.

### 2026-11-07 — kfu_azad_halyk — Partial

Selected for existing-document downloads; Kazan Utları remains a separate pending
candidate because its current adapter assembles page images. Live collection
inspection and count verification completed in 17 requests: 15 `tt`-labelled
records, 15 eligible public direct PDFs, no remaining frontier. Restricted ZIPs
remain inventoried and unrequested. Source metadata preservation is retained.

Added typed opt-in `direct_files_only` for KFU collection configuration and enabled
it in this source's YAML. Parser version 4 preserves policy and file counts;
readers remain metadata, image assembly is bypassed, and publication inventory
excludes prior assembled outputs while retaining direct document assets. Other
KFU configurations keep their previous reader behavior. One 8,466,638-byte,
eight-page PDF matched prior hashes. A read-only helper reader check and manual
publication-projection scenario verified policy boundaries without production
state writes. See the [source guide](ingestion/kfu-azad-halyk.md) and ignored
`__artifacts/kfu-azad-halyk-review-20261107/` for details and evidence.

Compilation, configuration/capability and workflow-generator checks passed;
no automated tests were added. Other originals were not freshly acquired.
Database/storage credentials remain prerequisites for live resume, full
acquisition, repeat-run and S3 receipt verification. No production writes,
uploads or workflow dispatch occurred. Preserve the baseline date pending
remaining verification.
