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

Next concrete work: inspect metadata output from live PTY session 77614, then extend
`magarif_vakyt` to discover `/reading` and acquire linked original PDFs using shared
Yandex checksums/delivery. Keep ZIP derivation intact. Source inventory notes have
been updated for Sarhaan and Tatfolk. Echo of Centuries PTY 96859 remains running;
last inspection showed 603 records, 26 listing requests completed and no errors.
