# Autonomous source review: 2026-10-28

Session started at 22:46 UTC; planned end is 2026-10-29 03:46 UTC.
Allocation: three hours new public original-file sources, two hours existing
coverage including verification and handoff. Registration-required downloads are
deferred. Existing owner deferrals remain in force. No automated tests are added.
Session evidence and manifests: `__artifacts/session-20261028/` (ignored).

## Current checkpoint (2026-10-29 00:01 UTC)

Planned end: **2026-10-29 03:46 UTC**. Reserve 03:26–03:46 for handoff.
The goal is active; keep working on new public original-file sources and existing
coverage. Registration-required sources remain deferred; do not add automated tests.

- Completed new adapters: Sarhaan `42f06f4`, Fänni Tatarstan `bdd62a0`, contemporary
  DUM RT publications `91893c1` (235 records / 227 unique PDF candidates).
- Existing-source work: Magarif-Vakyt gained 19 direct PDFs (`934d755`); Echo of
  Centuries completed 1,385 records / 95 Tatar-labelled PDFs (`e78c1aa` fixed books);
  Tatar Galyame completed 279 records / 128 eligible documents under its existing
  all-language policy. KFU auxiliary-viewer parsing repaired in `72044be`.
- Efficiency commits: `6f86e1c` overview/map, `7b27f93` agent guidance,
  `f331934` shared native GET/redirect guard (three live provider checks and PDF
  revalidation passed), `6bc6ecc` compact large manifests (same JSON data/schema;
  a roughly 29 MB snapshot reduced to about 15 MB; CLI status reads it correctly).
- **Live process: KFU discovery PTY 27121**, log
  `__artifacts/session-20261028/kfu-repository-discovery-3.log`. It resumed the
  terminal PTY 70428 using compact checkpoints. Poll before restarting. Previous
  scan reached 513 records / 35 listing requests and had no remaining record errors.
- Verified 85 MB dictionary was imported into the main KFU manifest through the
  existing `reuse_originals` helper under a source lock: one provenance-preserving
  local import, zero requests. Evidence: `kfu-local-import.json`. No manual asset
  overwrite was used. The active scan is still incomplete across 180 collections.
- All DUM RT discovery/verification processes are terminal. Final scan: 37 archive
  pages / 235 records, 187 newspaper + 48 modern almanac entries; 227 distinct PDF
  URLs, eight metadata-only almanac entries, 17 dangling-quote repairs. Three CLI
  samples acquired and replayed with zero requests. Raw links and repair provenance
  are retained. Shared inventory and usage docs are updated.
- Budget checkpoint: **204,568,967 bytes accounted**, including manual samples and
  an 8 MiB probe allowance; **869,172,857 bytes remain** under 1 GiB. Update
  `document-budget.json` before large transfers (new CLI summaries plus top-level
  manual PDFs). Actual sample transfers remain bounded; no bulk acquisition.
- Worktree should contain only the three preexisting unrelated config edits.
  Selectively stage any future example-YAML edits; never commit private configs.
- Next work: qualify another public website. Useful research directions are new
  official domains for Ruhiyat/Tatneft or Bashkortostan library, and original-file
  repositories. BAYĞIŞ root advertises **HTTP** `/aftorlar`; only HTTPS was rechecked
  in this session (403). A literal advertised HTTP check may distinguish a real
  access failure from a different virtual host. Social channels remain deferred.
  Tatar Ile's two direct PDF transfers stalled after partial bytes; do not repeat
  them without a distinct delivery route. No registration is inferred from generic
  login links, HTTP 401/403 or timeouts alone.

## Initial findings

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

## Existing coverage

Echo of Centuries discovery resumed from the prior manifest using the repository
virtual environment. Operational configuration is `/tmp/crawler-session.yaml`;
its limits include a 1 GiB acquisition budget, 100 MiB per-file cap and 5 GiB
free-space reserve. Discovery output is `echovek-discovery.log` in the session
directory. A copied manifest preserves prior observations and file results;
existing downloaded files remain at their recorded original locations.

## Resume checkpoint

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

## Publisher discovery expansion completed

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

## Next new-source candidate: Fänni Tatarstan

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

## 23:26 UTC checkpoint

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

### Latest resume details

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
