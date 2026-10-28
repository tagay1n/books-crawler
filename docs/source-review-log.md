# Autonomous source review: 2026-10-28

Session started at 22:46 UTC; planned end is 2026-10-29 03:46 UTC.
Allocation: three hours new public original-file sources, two hours existing
coverage including verification and handoff. Registration-required downloads are
deferred. Existing owner deferrals remain in force. No automated tests are added.
Session evidence and manifests: `__artifacts/session-20261028/` (ignored).

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
