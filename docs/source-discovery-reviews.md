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
guides and the historical [source review log](source-review-log.md) provide
background; their checks do not establish current discovery completeness.

## Choose the next source

Choose the eligible row with the oldest last-reviewed date, breaking ties
alphabetically by source ID. Review one source per request. Skip a source only
while a documented blocker prevents a substantive review; record its prerequisite
in the table and reconsider it when that prerequisite becomes available. If all
remaining sources are blocked, report the blockers rather than advancing dates.
Known gaps stay visible in the findings column but do not override the rotation.

## Register

Dates use `YYYY-MM-DD`. Outcomes are `Baseline`, `Reviewed`, `Partial`, or
`Blocked`; a completed review may still have documented limitations or follow-ups.
For partial or blocked attempts, preserve the last completed review date (or
initial baseline date) and record the attempt date in the history below.

| Source ID | Source guide | Last reviewed | Outcome | Outstanding findings / blockers |
| --- | --- | --- | --- | --- |
| `beznenmiras` | [Безнең мирас](ingestion/beznenmiras.md) | 2026-11-06 | Baseline | — |
| `common_crawl` | [Common Crawl / FinePDFs](ingestion/common-crawl.md) | 2026-11-06 | Baseline | — |
| `commons` | [Wikimedia Commons](ingestion/commons.md) | 2026-11-06 | Baseline | — |
| `darul_kutub` | [Darul-Kutub](ingestion/darul-kutub.md) | 2026-11-06 | Baseline | — |
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

No audits recorded yet. Append one short entry per completed or attempted review
with the following information; keep earlier entries as historical evidence:

- Date, source ID, and outcome.
- Scope examined: live routes, filters, and representative records checked.
- Findings and fixes, with relevant code/commit or source-guide references.
- Verification commands, compact results, and evidence artifact paths. Keep
  credentials, private configurations, and downloaded originals out of Git.
- Remaining limitations, follow-ups, or blockers and their prerequisites.
