# Historical source investigations

Evidence from October 2026; counts, access findings and local paths are dated snapshots.
Do not execute old resume instructions or treat these reports as current state.
Use [current source guides](../local-ingestion.md) and PostgreSQL for ongoing work.

## Autonomous crawler session handoff

Session requested: five hours starting 2026-10-28 22:46 UTC, planned end
2026-10-29 03:46 UTC. Final verification followed the interrupted session's
resumption at 04:46 UTC. All bounded discovery jobs had already stopped normally
by 00:56 UTC; none remains running. The figures below describe the retained
evidence, not five hours of uninterrupted execution or exhaustive site coverage.

### Implemented and committed

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
specifically documented in [local ingestion usage](../local-ingestion.md).

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

### Broader discovery retained for resumption

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

### Reuse and operator efficiency

- Read-only overview and code map: `6f86e1c`, agent guidance `7b27f93`.
- Shared native GET/redirect guard: `f331934`; source-specific identity and file
  integrity checks remain in the adapters.
- Compact large manifests: `6bc6ecc`; same JSON schema and atomic replacement,
  with the inspected roughly 29 MB snapshot reduced to about 15 MB.
- Optional compact scan/format/error details: `bd4ef38`. This distinguishes page
  images, known PDF assets and unresolved formats without dumping large manifests.

Start with [the adapter map](../adapter-development.md), then:

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

### Access and deferrals

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

### Final verification and practical limits

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
[local-ingestion.md](../local-ingestion.md).

## Autonomous source review: 2026-10-28

Session started at 22:46 UTC; planned end is 2026-10-29 03:46 UTC.
Allocation: three hours new public original-file sources, two hours existing
coverage including verification and handoff. Registration-required downloads are
deferred. Existing owner deferrals remain in force. No automated tests are added.
Session evidence and manifests: `__artifacts/session-20261028/` (ignored).

### Final checkpoint (2026-10-29 04:52 UTC)

The bounded autonomous session is complete. All discovery jobs stopped normally
at their configured limits; no crawler process remains running. The original
03:46 UTC end passed during an interruption; final verification followed resumption.
The authoritative handoff is [autonomous-session-2026-10-28.md](#autonomous-crawler-session-handoff).
Sections below are historical evidence, including superseded resume instructions.

- Four new source adapters committed: Sarhaan `42f06f4`, Fänni Tatarstan
  `bdd62a0`, DUM RT publications `91893c1`, Tugan Zhir `f1eefad`.
  Their completed observed catalogs expose 380 eligible PDF candidates; this is
  not a successful-download or individually verified-language count.
- Existing improvements: 19 Magarif-Vakyt direct PDFs (`934d755`), complete Echo
  of Centuries discovery / 95 Tatar-labelled PDFs (`e78c1aa`), KFU auxiliary-viewer
  repair (`72044be`), reviewed 478-page Tatar novel (`bfcd806`), full Tatar Galyame
  tree / 128 all-language documents and a verified Tatar PPTX sample.
- Larger bounded scans retained: KFU 1,563 records, Darul-Kutub 243, Tatarica 607,
  Kazan Utları 379, Internet Archive 612. These remain explicitly incomplete and
  resumable. Read the handoff before any future resumption; do not claim exhaustion.
- Efficiency work: overview/map `6f86e1c`, agent guidance `7b27f93`, shared native
  guard `f331934`, compact large manifests `6bc6ecc`, optional scan details `bd4ef38`.
- Eight final isolated CLI replays: 11 skips, zero requests, no errors.
  Local audit: 46 original references / 41 distinct hashes and two derived PDFs
  verified; no operational downloaded-file integrity errors. The intentional cap
  fixture's missing historical file is separately documented. No automated tests.
- The copied Kazan Utları derived file was relocated from the original artifact
  root after hash/size verification; provenance records were unchanged.
- Budget: 266,351,391 bytes accounted including an 8 MiB probe allowance, below
  1 GiB. No bulk acquisition. Evidence/configs remain in the ignored session root.
- Registration-gated Lisan library route is deferred under the standing rule.
  No accounts, member-content API calls, payments or social-channel acquisition.
  Shared candidate inventory has current access findings and implementation notes.
- Relevant changes are committed. Preserve the three preexisting unrelated config
  edits in ingestion.example.yaml, litres/config.yaml and milli_kitaphana/config.yaml.


### Initial findings

- **Sarhaan Tatar category:** public category returned HTTP 200 and advertises
  seven pages. First page mixes Tatar-labelled PDF/office files, image-only
  items, and an Arabic-labelled multilingual entry. Category membership alone
  cannot admit files. Native category:
  <https://sarhaan.com/a/tatar-%d8%aa%d8%aa%d8%a7%d8%b1%d9%8a/>.
  One advertised `Карун` PDF downloaded anonymously: 6,597,204 bytes, seven
  PDF pages, SHA-256
  `ce15586942c9c318a10c21248672499e6d3f7101d7f98094ac2f12de0e260293`.
  Rendered page 5 has Cyrillic Tatar narrative alongside Arabic quotations;
  sampled text extraction is empty. Delivery resolves to native
  `https://sarhaan.com/?wpdmdl=78780`. No account or registration was used.
  Adapter qualification is in progress; total eligible holdings are unverified.
- **Tatfolk:** public catalog returned HTTP 200 after redirecting to HTTP.
  All sixteen advertised PDF links received bounded initial-byte checks: fifteen
  returned HTTP 404; one returned a PDF. The complete surviving conference volume
  is 9,438,765 bytes / 543 PDF pages, SHA-256
  `188bd658455d0d107e0d61a106681f2846e612b9e1a20aee2cc7c3651bd8d7c3`.
  Text samples include Russian and Tatar. A character-frequency screen identified
  121 Tatar-letter-rich pages, not 121 individually verified Tatar pages. Its
  current reachable yield does not meet the normal implementation threshold.
- **Infourok:** sampled public record returned HTTP 401 with a 265-byte response.
  This establishes an access failure, not a demonstrated registration workflow.
- **Lisan:** `/sahifelerimiz` returned an 814-byte shell. File access and any
  membership requirement remain unverified.
- **ebook.tatar:** public root returned HTTP 200, 29,459 bytes, with an
  authorization link and textbook cards. An authorization link alone does not
  establish that original downloads require registration; item access remains
  unverified.

### Existing coverage

Echo of Centuries discovery resumed from the prior manifest using the repository
virtual environment. Operational configuration is `/tmp/crawler-session.yaml`;
its limits include a 1 GiB acquisition budget, 100 MiB per-file cap and 5 GiB
free-space reserve. Discovery output is `echovek-discovery.log` in the session
directory. A copied manifest preserves prior observations and file results;
existing downloaded files remain at their recorded original locations.

### Resume checkpoint

- Efficiency improvement committed as `6f86e1c`: read-only
  `scripts/ingestion_overview.py` and `docs/adapter-development.md`. Manual CLI
  invocation and compilation passed. Future work should use the compact overview
  instead of repeated full-manifest dumps.
- Sarhaan adapter is committed as `42f06f4`. Initial live discovery
  completed seven pages / 79 records / 74 PDF candidates, 73 initially admitted.
  CLI acquired `Яшерен булган нәрсәләрдән ачкыч.pdf`: 5,497,235 bytes / five
  pages, SHA-256 `4c0462ccaac480d810cb2292f280fc260cde9b1c01c9d4394bfcf8d5184b78f1`;
  rendered page 3 contains Tatar. Another CLI sample is an Arabic alphabet lesson;
  despite the site's Tatar label, it is now held pending individual language
  review. Parser policy 2 adds a hold for Arabic-alphabet teaching titles.
  Full rediscovery under policy 2 completed all seven pages / 79 records: 69
  admitted PDF candidates and five held. The current admitted sample replay skipped
  one verified original with zero requests. Documentation and the shared inventory
  are updated. The rejected alphabet sample remains as historical acquired bytes;
  its asset is unsupported. No further Sarhaan implementation work is pending.
- Echo of Centuries discovery is still running (PTY session 96859); do not restart
  it without polling or authoritative terminal evidence. Its log is
  `echovek-discovery.log`. It has passed 500 article records without errors.
- User added targeted refactoring/code reuse and missed-resource discovery to the
  approved scope. Prioritize real coverage gaps over broad refactoring.
- Concrete existing-source gap: `magarif-vakyt.ru/reading` has 19 public Yandex
  links, using `/i/` shares unsupported by the ZIP-only adapter. The first metadata
  request returned a 46,237,257-byte PDF (`Ад уку_5 кл 2027.pdf`), MD5
  `028f257fbcec5e52d8495e0c1d611707`, SHA-256
  `743529dd990ed780022c0eab78b986298b97367ff5a8517d23b82ea5b1afb8e6`.
  Evidence: `magarif-vakyt-reading-links.json` and
  `magarif-vakyt-reading-resource.json`. Next inspect the other resources and
  extend the existing adapter to reuse its verified Yandex delivery for direct
  PDFs as well as ZIPs; do not register a duplicate publisher source.
- `magarif-vakyt.ru/online` returned HTML but no ordinary book links or iframes;
  inspect its native reader markup before assuming no additional holdings.
- ebook.tatar root is reachable but the sampled native textbook record timed out;
  registration is still unproven. Do not label the entire source registration-gated
  merely because its root has an authorization button.

Next concrete work: implement Fänni Tatarstan on its new public OJS domain,
using the verified native full-issue PDF route described below. Publisher coverage
expansion is committed as `934d755`; do not duplicate that implementation.
Echo of Centuries remains active in PTY 32838; poll before restarting it.

### Publisher discovery expansion completed

Мәгариф–Вакыт now traverses `/online2` and `/reading`: live CLI discovery
completed 33 resources, the existing 14 ZIPs plus 19 direct PDFs. The fifth-grade
methodology PDF acquired through CLI is 1,190,772 bytes / 70 pages, SHA-256
`249a2ddc3e1d8850fe36334fd81f41c6cf97c02749cef0868e43aa0a00c3934e`; source
size/MD5/SHA-256 all matched, and extracted page 5 is readable Tatar. The direct
PDF and an existing ZIP/derived PDF each replayed with zero requests. Removing
only the isolated verification copy of the derived PDF forced successful local
reassembly (`pdf_assembled=1`, zero requests). A 1 MB file cap rejected the direct
PDF with zero requests. No automated tests were added. The common delivery path
handles both formats; repeated file-budget checks were consolidated and stream
errors redact temporary signed delivery locators.

Additional missed reader lead: `/reading` links four Bonboni readers. First-grade
reader HTML and `javascript/config.js` are public. Its configuration advertises
124 pages, whereas the inspected existing ZIP advertises 114. Do not dismiss it
as duplicate coverage. Native reader: `https://books.bonboni.ru/adabi-uku/1class/`;
no direct PDF link was found and download control is hidden. Reader acquisition
is not implemented in this change. Evidence: `bonboni-1class.html` and
`bonboni-1class-config.js`. `/new4` is reachable but its only Yandex links are
footer policies; these must remain excluded. `/online` exposes Google Drive
reader links that remain unverified.

Echo of Centuries initial run ended normally at its 900-second deadline with
889 records and a remaining frontier. It resumed using the same manifest in
PTY session 32838, log `echovek-discovery-2.log`. PTY 96859 is terminal.

### Next new-source candidate: Fänni Tatarstan

The old `https://ft.antat.ru/` catalog, archive and sampled advertised PDF returned
HTTP 502. Official indexed migration notices identify the replacement
`https://ftatarstan.ru/`, which is reachable (HTTP 200). Native OJS archive:
`https://ftatarstan.ru/index.php/ftat/ru/issue/archive`, 25 issue cards on its first
page and an advertised next page `/issue/archive/2`. The homepage advertises
`PDF (татарский)` for issue 51, № 3 (2026). Its public galley
`/index.php/ftat/ru/issue/view/51/50` returned HTML with an explicit download link
`/index.php/ftat/ru/issue/download/51/50`, whose anonymous response is HTTP 200
application/pdf. Bounded full sample inspection completed: 8,714,023 bytes / 196 PDF pages,
SHA-256 `d0db9116e265154bf764e61ed027837fb75364e8db513fed3937b97cf1a45a09`.
Extracted page 6 contains readable Tatar scientific text; the issue also has
Russian/English abstracts and references. PTY 80730 is terminal. Source acquisition must
use advertised native links and distinguish complete issue galleys from article
PDFs and author-account navigation. Registration is not required merely because
OJS displays author registration links. This journal is a distinct native surface
from the previously deferred IYALI electronic-library catalog. Evidence HTML and
link inventories are under the session directory. The complete original and Tatar content are verified; proceed with adapter
implementation after inspecting native issue-page galley labels and remaining
archive pagination. Use whole-issue original PDFs, excluding article galleys.

Other candidate check: `https://islamhouse.com/tt/books/` returned 404; no verified
Tatar collection or download route. Do not infer site-wide unreachability or
registration requirements from that obsolete/unverified route.

### 23:26 UTC checkpoint

- New `ftatarstan` adapter committed as `bdd62a0`: native three-page archive /
  51 issues / 48 eligible full-issue PDFs, one unlabelled held galley and two
  metadata-only issues. CLI original/replay and documentation are complete; shared
  inventory is updated. No pending implementation work for this source.
- Echo of Centuries fully completed the same resumed scan: 64 listing requests
  (three archive pages plus 61 publication pages), 1,385 records: 1,375 articles
  and ten non-journal metadata records. 1,091 PDF assets: 95 Tatar-labelled eligible,
  996 unsupported by language. Three verified downloads now live in the main
  session manifest (two additional samples were integrated under a source lock
  only after matching their observation IDs and local hashes). Additional samples:
  2009 Хәмидуллина: 1,681,874 bytes / five pages / SHA-256
  `fc920792121f5363ebd0b84bd2be3dd736bf55b78f675815cc61d666f53b3745`;
  Макарова on Хәсән Сарьян: 1,279,194 bytes / 15 pages / SHA-256
  `a6a8ffd7c59d00ddf1db91ce247472eadaae0c2c8a4be95aec3e52590b1e7645`.
  Rendered sample pages 2 and 4 show Tatar; the 2009 file has legacy-font extraction
  errors. Source scope fix committed as `e78c1aa`. PTY 55617 is terminal.
- Tatar Galyame discovery completed: 34 listing requests, 279 records, 128 eligible
  hosted documents under the existing all-language policy and 27 unsupported
  assets. This is not 128 verified Tatar files. PTY 65139 is terminal.
- KFU repository discovery is live in PTY 76311, log
  `kfu-repository-discovery.log`. Initial 15-record checkpoint expanded past 270
  records; the scan is incomplete. Two errors were observed: net/26934 auxiliary
  single-file viewer and a read timeout on net/28071. The currently running process
  predates the parser fix; let it stop normally before resuming to retry errors.
- KFU parser fix committed as `72044be`: unsupported single-file viewers (including
  restricted receipt images) remain metadata and do not reject public book PDFs.
  Isolated net/26934 verification acquired only Фәлсәфи сүзлек: 85,064,699 bytes /
  323 pages / SHA-256
  `b1276d71dc029ac7dc176c94da9b792a7b38734c224be758d9ed3eb109881577`.
  Rendered page 11 is Tatar. Repeat made zero requests. Restricted images/ZIPs
  stayed unsupported. Successful result remains in `kfu-single-viewer/`; do not
  edit the live main manifest to import it while discovery is running.
- Verified copies of old local originals were copied into the new Echo of Centuries,
  Tatar Galyame and KFU roots. A manifest copy alone does not relocate relative
  file references.
- Do not merge the isolated Magarif direct-PDF sample by overwriting a newer asset:
  final rediscovery added provenance metadata and changed the observation ID. The
  isolated sample remains valid evidence; main scan legitimately reports pending.
- Lan and CulturaX inventory rows now explicitly follow the standing registration
  deferral rule. No accounts or terms were accepted.
- Tatar16.ru currently serves an unrelated casino site; it is not the historical
  educational source. Do not follow its registration links. BAYĞIŞ root is reachable
  but its advertised `/aftorlar` returned HTTP 403 on this check; no adapter selected.
- Tatar Ile native book record is public and advertises a literal `iframeURL` PDF.
  Both sampled original transfers returned HTTP 200 PDF then stalled: story volume
  8,300 bytes retained, children’s book 16,356 bytes. No complete original verified;
  no adapter selected. Its robots file advertises a native sitemap, but do not
  continue spending time there without a distinct reason to expect file delivery.
- Document budget checkpoint `document-budget.json`: 159,122,136 accounted bytes
  including an 8 MiB probe allowance; about 914.6 MB remain under the 1 GiB session
  cap. Sum new CLI summaries and top-level manual PDFs before large transfers.
- Next new candidate: publisher DUM RT newspaper archive. Indexed native public
  PDFs for Дин вә Мәгыйшәт include
  `https://dumrt.ru/netcat_files/557/751/DvM_10_2023.pdf` and
  `https://dumrt.ru/netcat_files/557/751/DvM_06_2018_0.pdf`; indexed text is Tatar.
  Public root/link inspection is running; inspect its output before choosing a
  native archive URL or implementing anything.

#### Latest resume details

Modern DUM RT archives are reachable: `https://dumrt.ru/media/din-va-magishet/`
(six native issue cards per page; pager `curPos` advances by six with `cur_cc=751`)
and `https://dumrt.ru/media/shura-almanah/` (ten cards per page; advances by ten
with `cur_cc=757`). The root advertises both. These are contemporary publications,
not the already implemented historical KFU Шура collection. Native issue-page
inspection is running in the latest tool-returned PTY session; consult
`dumrt-din-issue.html`, `dumrt-shura-issue.html` and their PDF-link JSON files.
No complete original has yet been acquired for this candidate. Do not implement
until PDF language/access verification passes.

Coding-agent guidance committed as `7b27f93`: AGENTS.md points to the compact
developer map, overview helper and repository interpreter. Existing no-tests rule
is intact. KFU parser repair is `72044be`, FT journal is `bdd62a0`. Main KFU
discovery PTY 76311 is still running and predates the repair; wait for its terminal
state before resuming to retry net/26934 and the transient net/28071 timeout.

### Additional access evidence and Tugan Zhir (00:33 UTC)

Bashkortostan's official resources page still advertises ebook.bashnl.ru. Its TLS
leaf is valid but the server omits the GlobalSign intermediate. The public CA
certificate was retrieved over verified HTTPS and verified against default trusted
roots, then used as a temporary chain supplement; hostname/expiry checks stayed
on. Catalog and native search became reachable. Search for «татарском» returned
13 mixed documents/collections, not 13 verified Tatar files. Explicit collection
ResourceCollection-4392 names Povarisov's works in Tatar and contains one file.
Its advertised Resource-20465 Get link redirects to a public image reader using
SecureViewer/Page delivery. No original PDF route was verified. Findings are in
the shared inventory; no TLS bypass or image-reader adapter was implemented.

Tugan Zhir's native archive exposes 36 distinct issue PDF URLs (2017–2026),
including publisher-linked Congress storage. Two small complete originals were
inspected: №1/2022, 2,170,679 bytes / 264 PDF pages, SHA-256
70c572cd1cdb747214419b9dd6711394eee8165b4f1bd4ef698700cc3af2412b;
№1/2017, 1,506,264 bytes / 148 pages, SHA-256
8795293f00ce54cd8a3b2c0fae52828da91f96bbc3d38c7653a0e0f0558a16c7.
Both imprints declare Tatar/Russian, and rendered narrative pages are Tatar.
Letter-frequency screens are exploratory, not individually verified page counts.
The latest 58 MB issue returned PDF headers but its bounded read timed out before
any chunk was retained; it is not counted as a verified original.

Live CLI discovery completed one archive observation with 36 eligible PDF assets.
Initial cross-host acquisition was rejected by the shared same-origin fallback;
a source-specific validator now requires exact advertised file identity across
all response URLs. Both selected samples then acquired with matching hashes and
replayed with zero requests / two skips. Changed-file redirects, POST, HTTP and
unrelated origins were manually checked against the shared guard. No automated
tests were written. Docs distinguish bilingual-series admission from per-file
language proportions or printed completeness; unrelated electronic-library books
remain outside scope. Evidence/configs are in the ignored session artifact root.

## KFU «Вакыт» acquisition pilot

Historical report. The follow-up implementation now registers `kfu_vakyt`, adds
filtered-search traversal and validated JPEG2000 acquisition, and keeps the
explicit item-language policy below. See [current usage](../ingestion/kfu-vakyt.md).
Statements about deferred production support describe the pilot stage.

Date: 2026-10-27. This is a bounded investigation, not a registered production
source or a full collection crawl. The current explicit Tatar language policy
remains in effect. No automated tests were added.

### Scope and language evidence

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

### Complete labelled issue

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

### JPEG2000 conversion research

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

### Local evidence and next decision

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
