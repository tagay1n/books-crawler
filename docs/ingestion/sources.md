# Implemented acquisition sources

The shared `cli.py` implements these acquisition sources:

- `tuganzhir`: <https://tuganzhir.org/archive/>, linked original PDFs of the
  publisher-declared Tatar/Russian journal series.
- `dumrt`: <https://dumrt.ru/media/din-va-magishet/>, linked original PDFs of the
  contemporary Tatar newspaper and modern Шура almanac.
- `ftatarstan`: <https://ftatarstan.ru/index.php/ftat/ru/issue/archive>, full-issue
  PDF galleys explicitly labelled Tatar.
- `sarhaan`: <https://sarhaan.com/a/tatar-%d8%aa%d8%aa%d8%a7%d8%b1%d9%8a/>,
  individual PDFs with consistent explicit Tatar labels; alphabet lessons held.

- `magarif`: <https://magarif-uku.ru/documents>, collecting archive attachments.
- `magarif_vakyt`: <https://magarif-vakyt.ru/online2>, retaining publisher-linked
  Tatar textbook ZIPs and assembling PDFs from their explicit reader page lists.
- `beznenmiras`: <https://beznenmiras.ru/categories/widget/list/svezii-vypusk>,
  discovering issue metadata and linked original documents; cover images are skipped.
- `tatarica`: <https://tatarica.org/tat/razdely/tatarika-kitaphanse>, collecting
  document editions linked from the library catalog's books and journal articles.
- `darul_kutub`: <https://darul-kutub.com/search>, collecting originals for books
  and journal issues across all languages in the public search catalog.
- `kazanutlary`: <https://kazanutlary.ru/j-archive>, collecting scanned issue
  images and assembling complete PDFs locally with PyMuPDF.
- `tatkniga`: <https://tatkniga.ru/catalog/biblioteka/>, collecting directly
  linked files with explicit Tatar or Tatar-containing bilingual language labels,
  plus supported public flipbook pages assembled into local PDFs.
- `miras`: <https://miras.info/projects/mirasxane/books/>, collecting exposed
  original book PDFs across all languages using an exported browser session.
- `miras_periodicals`: <https://miras.info/projects/mirasxane/periodicals/>,
  periodical-series discovery and explicitly exposed PDFs with Tatar source claims;
  live reader verification is pending a refreshed session.
- `commons`: <https://commons.wikimedia.org/wiki/Category:Tatar-language_books>,
  discovering document-format books through the public metadata API and acquiring
  their checksum-verified original uploads.
- `isxaki`: <https://isxaki.com/ijat/>, collecting linked document files from
  original editions, three works periods, and books about Iskhaki.
- `turuz`: <https://turuz.com/index/pitik/category/2>, collecting direct Tatar-labelled
  dictionary PDFs, DjVu and Word originals from the native dictionary listing.
- `yazuchy`: <https://sptatar.com/yazuchy-n-shriyaty/>, collecting publisher book
  PDFs with explicit Tatar target-language claims or individually reviewed hashes.
- `nizgar`: <https://nizgar.ru/zhurnal-nizhegorodskie-tatary-nizhgar-tatarlary/>,
  collecting linked original PDFs of the bilingual magazine archive.
- `echovek`: <https://www.echovek.ru/ru/publications>, following journal issues
  and acquiring article PDFs explicitly labelled Tatar.
- `obuchalka`: <https://obuchalka.org/knigi-po-tatarskomu-yaziku/>, discovering
  the mixed subject category and acquiring individually reviewed Tatar PDFs.
- `internet_archive`: <https://archive.org>, collecting public original document
  uploads from text items explicitly labelled as Tatar.
- `tataroved`: <https://tataroved.ru/publication/>, collecting linked originals
  with bibliographic Tatar-language claims or individual reviewed-file evidence.
- `kfu_dspace`: <https://dspace.kpfu.ru/xmlui/discover>, discovering native Tatar
  topic results and acquiring public PDFs with explicit language or reviewed-file evidence.
- `kfu_repository`: <https://repo.kpfu.ru/jspui/community-list>, discovering all
  historical repository collections with explicit Tatar item-language admission.
- `kfu_vakyt`: <https://repo.kpfu.ru/jspui/handle/net/86/simple-search>, collecting
  exact-series Vakyt results with explicit Tatar item-language admission.
- `kfu_books`: <https://repo.kpfu.ru/jspui/handle/net/27574>, collecting public
  direct document files and supported JPEG readers from the Turkic–Tatar books collection.
- `kfu_manuscripts`: <https://repo.kpfu.ru/jspui/handle/net/18503>, collecting public
  direct document files and supported JPEG readers from the Turkic–Tatar manuscript collection.
- `kfu_il`: <https://repo.kpfu.ru/jspui/handle/net/28060>, collecting public
  «Ил» newspaper issue files with explicit Tatar source language labels.
- `kfu_azad_halyk`: <https://repo.kpfu.ru/jspui/handle/net/27528>, collecting public
  «Азад халык» newspaper issue files with explicit Tatar source language labels.
- `kfu_shura`: <https://repo.kpfu.ru/jspui/handle/net/25046>, collecting public
  «Шура» journal issue files with explicit Tatar source language labels.
- `tatargalyame`: <https://tatargalyame.kpfu.ru/catalogue>, collecting explicitly
  listed hosted educational documents across all languages.

All sources use the same local downloader and manifest implementation. Each
adapter follows its selected catalog. Existing legacy collectors remain independent.
