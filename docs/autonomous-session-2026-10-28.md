# Autonomous crawler session handoff

Session requested: five hours starting 2026-10-28 22:46 UTC, planned end
2026-10-29 03:46 UTC. Final verification followed the interrupted session's
resumption at 04:46 UTC. All bounded discovery jobs had already stopped normally
by 00:56 UTC; none remains running. The figures below describe the retained
evidence, not five hours of uninterrupted execution or exhaustive site coverage.

## Implemented and committed

| Source | Completed observed discovery | Admission and verification | Commit |
| --- | --- | --- | --- |
| Sarhaan | Seven category pages, 79 records, 74 PDF candidates | 69 eligible from consistent publisher Tatar labels; five held. Two Tatar originals inspected; an Arabic-alphabet sample remains held despite the site label. | `42f06f4` |
| Fänni Tatarstan | Three archive pages, 51 issues, 49 full-issue PDF galleys | 48 explicitly Tatar-labelled PDFs; one unlabelled galley held, two issues without a full-issue galley. A complete 196-page issue verified. | `bdd62a0` |
| DUM RT contemporary publications | 37 archive pages, 235 records, 227 distinct PDF URLs | Publisher evidence identifies the newspaper and modern almanac as Tatar. Three CLI samples verified: 2024 newspaper, modern Шура №54, and a narrowly repaired 2013 newspaper link. | `91893c1` |
| Tugan Zhir / Родной край | One archive observation, 36 distinct linked issue PDFs | Publisher-declared Tatar/Russian series; complete 2017 and 2022 samples, 148 and 264 PDF pages, contain Tatar narrative. | `f1eefad` |

These are 380 eligible linked PDF candidates across four new adapters, not 380
downloaded or individually language-verified files. DUM RT's modern Шура is
distinct from the existing historical KFU Шура collection. Per-file language
proportions and completeness against printed editions remain unverified unless
specifically documented in [local ingestion usage](local-ingestion.md).

Existing adapters also gained concrete coverage and fixes:

- Magarif-Vakyt: 19 direct PDFs added alongside 14 textbook ZIPs (`934d755`).
  A 70-page Tatar methodology PDF passed source size/MD5/SHA-256 checks.
  Verified ZIP reuse and reconstruction of its missing derived PDF required no
  requests; a file-cap check rejected an oversized original before requesting it.
- Echo of Centuries: a non-journal book no longer blocks later archive traversal
  (`e78c1aa`). Completed 1,385 records, with 95 Tatar-labelled article PDFs and
  three retained verified originals. Other-language files remain held.
- KFU: unsupported single-file auxiliary viewers no longer reject a book's public
  PDF (`72044be`). The 323-page Tatar philosophical dictionary was verified;
  restricted receipt images remain unsupported. Its local import preserved
  observation provenance and made no requests.
- Yazuchy: a SHA-256-pinned review admits the 478-page Tatar translation of
  Shargunov's «1993» (`bfcd806`). The observed slice now has ten eligible reviewed
  PDFs and four held candidates. Sampled narrative pages were inspected.
- Tatar Galyame: completed all 34 category responses / 279 visible resources,
  yielding 128 eligible hosted documents under the existing all-language policy.
  A newly acquired 150,316-byte PPTX has 13 slide XML parts and readable Tatar on
  inspected slides 1–3. This was container/text inspection, not rendered slides.

## Broader discovery retained for resumption

No bulk document acquisition accompanied these scans. Totals are retained records;
current-scan counts can differ because earlier observations are kept.

| Source | Retained records | Discovery state at stop |
| --- | ---: | --- |
| KFU historical repository | 1,563 | 88 listing requests; five pending record requests and a listing frontier; no current discovery errors. Full tree has 180 collections and remains incomplete. |
| Darul-Kutub | 243 | 302 catalog pages; 6,040 search rows of 15,573 advertised. Rows often refer to articles within the same publication. 242 publications inspected in this scan; pagination remains. |
| Tatarica | 607 | 68 listing requests; four pending records and further batches. Advertises 1,532 entries, including video records without document attachments. |
| Kazan Utları | 379 | 34 listing requests; nine pending records and 75 queued listings. 73,800 page-image assets described, not PDFs acquired; 20 previously acquired pages retained. |
| Internet Archive | 612 | Fresh scan inspected 612 of 700 enumerated records; 88 pending records and pagination remain. Advertised count changed from 5,295 to 5,304, correctly triggering restart. |

The latest Internet Archive run ended without errors. Its manifest retains the
earlier count-change diagnostic; this is distinct from a current failed request.
The other four runs ended at their configured page cap or soft deadline without
discovery errors. Completion of this bounded session does not mean these large
catalogs were exhausted. Their saved frontiers are ready for a future session.

## Reuse and operator efficiency

- Read-only overview and code map: `6f86e1c`, agent guidance `7b27f93`.
- Shared native GET/redirect guard: `f331934`; source-specific identity and file
  integrity checks remain in the adapters.
- Compact large manifests: `6bc6ecc`; same JSON schema and atomic replacement,
  with the inspected roughly 29 MB snapshot reduced to about 15 MB.
- Optional compact scan/format/error details: `bd4ef38`. This distinguishes page
  images, known PDF assets and unresolved formats without dumping large manifests.

Start with [the adapter map](adapter-development.md), then:

```bash
.venv/bin/python scripts/ingestion_overview.py __artifacts/session-20261028
.venv/bin/python scripts/ingestion_overview.py --details __artifacts/session-20261028/kfu_repository
.venv/bin/python cli.py --config __artifacts/session-20261028/config.yaml status --source tatarica
```

To resume an incomplete source in a later authorized session:

```bash
.venv/bin/python cli.py --config __artifacts/session-20261028/config.yaml discover --source tatarica --max-pages 100
```

The public operational config and per-sample configs are retained under the
ignored session artifact root. Completed scans start fresh on another discovery
invocation. Do not overwrite newer observations with older isolated sample assets;
use provenance-preserving reuse helpers where available. Original and derived
files are local artifacts, not committed source files. The shared candidate
inventory is `/home/tans1q/projects/tatar-pipeline-design/sources.md`, outside this
Git repository, and has also been updated.

## Access and deferrals

Registration-required original downloads remain deferred, including the Lisan
members-area book route. Its public Google Sites entry links the route, which
serves only Tilda's members bootstrap; the published initializer routes anonymous
visitors to login. No member-content API or account workflow was invoked.
Existing owner deferrals for social groups, paid sources, duplicate Common Crawl
material and previously rejected candidates are preserved.

Additional bounded findings are recorded without claiming new working adapters:

- Bashkortostan catalog works with its missing intermediate certificate supplied
  as a verified chain supplement; TLS verification was never disabled. The
  inspected explicit Tatar author collection has one file link that redirects to
  a page-image reader. Original PDF delivery remains unverified.
- Nizgar's old newspaper page is public, but all three advertised PDF links return
  404 on the current site. No guessed host rewrites or reader assembly were added.
- Turuz's extra language/folklore categories mix Tatar-topic studies, Turkish
  texts and Crimean Tatar. Existing dictionary admission was not broadened merely
  from a title keyword.
- Isxaki's newly found newspaper page and its public API probe timed out.
  National-library electronic-library entry points timed out; Baskala failed DNS;
  Tazbash returned Cloudflare challenge pages. None establishes registration.

## Final verification and practical limits

- Repository modules compiled and `git diff --check` passed. No automated tests
  were written, generated, restored or run for this work.
- Eight final isolated CLI replays passed: Sarhaan, Fänni Tatarstan, DUM RT,
  Tugan Zhir, Yazuchy, Magarif direct PDF, Magarif ZIP and Tatar Galyame PPTX.
  Together they skipped 11 verified originals with **zero requests and no errors**.
- Local size/SHA-256 inspection verified 46 retained original references covering
  41 distinct hashes, plus two complete derived PDFs. One intentionally missing
  historical reference in the failed Magarif cap fixture is separately recorded;
  there are no operational downloaded-file integrity errors. The compact-manifest
  benchmark is excluded because it is not a relocated acquisition root.
- The existing Kazan Utları derived PDF was copied into its retained session path
  after matching its stored hash/size; no acquisition result was fabricated.
- Acquisition accounting is 266,351,391 bytes, including complete manual samples,
  CLI attempted transfer bytes and an 8 MiB probe allowance, below the 1 GiB
  session cap. Local relocations and derived files are not new network transfers.
  This is an accounting estimate, not exact wire traffic.
- Relevant code and documentation are committed. The three unrelated preexisting
  config edits remain uncommitted: `ingestion.example.yaml`, `litres/config.yaml`
  and `milli_kitaphana/config.yaml`.

Machine-readable evidence under `__artifacts/session-20261028/`:
`final-coverage.json`, `final-replays.json`, `final-original-integrity.json`,
`final-local-relocations.json` and `document-budget.json`, alongside native HTML,
rendered sample pages, manifests, CLI summaries and download logs. These local
artifacts are ignored by Git; detailed usage and sample hashes are in
[local-ingestion.md](local-ingestion.md).
