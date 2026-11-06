# Source guide index

Open only the selected source guide. It owns source URLs, admission/access rules,
commands and sample evidence. PostgreSQL holds current progress; historical sample
counts and file manifests in guides are dated evidence, not live queue status.

Use `cli.py sources --details --source NAME` for current capabilities;
`ingestion/registry.py` is the source inventory authority. Shared behavior lives in
[operations](ingestion/operations.md); code navigation starts at the
[adapter map](adapter-development.md). For coverage audits, use the
[review register](source-discovery-reviews.md).

| Source ID | Guide | Scope / access |
| --- | --- | --- |
| `common_crawl` | [Common Crawl / FinePDFs](ingestion/common-crawl.md) | Tatar Cyrillic/Latin PDF dataset records and WARC offsets |
| <a id="tugan-zhir-archive"></a>`tuganzhir` | [Tugan Zhir](ingestion/tuganzhir.md) | Publisher-declared Tatar/Russian issue PDFs |
| <a id="dum-rt-contemporary-tatar-publications"></a>`dumrt` | [DUM RT](ingestion/dumrt.md) | Contemporary Tatar newspaper and modern Шура PDFs |
| <a id="fänni-tatarstan-issue-pdfs"></a>`ftatarstan` | [Fänni Tatarstan](ingestion/ftatarstan.md) | Explicitly Tatar-labelled full-issue PDF galleys |
| <a id="sarhaan-tatar-publications"></a>`sarhaan` | [Sarhaan](ingestion/sarhaan.md) | Explicit Tatar-labelled PDFs; alphabet lessons held |
| <a id="obuchalka-reviewed-tatar-textbooks"></a>`obuchalka` | [Obuchalka](ingestion/obuchalka.md) | Individually reviewed Tatar textbooks |
| <a id="echo-of-centuries-article-pdfs"></a>`echovek` | [Echo of Centuries](ingestion/echovek.md) | Explicitly Tatar-labelled article PDFs |
| <a id="nizgar-magazine-archive"></a>`nizgar` | [Nizgar](ingestion/nizgar.md) | Linked bilingual magazine PDFs |
| <a id="yazuchy-publisher-catalog"></a>`yazuchy` | [Yazuchy](ingestion/yazuchy.md) | Tatar-labelled or hash-reviewed publisher PDFs |
| <a id="turuz-dictionaries"></a>`turuz` | [Turuz](ingestion/turuz.md) | Tatar-labelled dictionary originals |
| <a id="мәгарифвакыт-textbook-packages"></a>`magarif_vakyt` | [Мәгариф–Вакыт](ingestion/magarif-vakyt.md) | Linked PDFs and textbook ZIP/reader assemblies |
| <a id="безнең-мирас-issue-archive"></a>`beznenmiras` | [Безнең мирас](ingestion/beznenmiras.md) | Issue metadata and linked original documents |
| <a id="isxaki-books-and-works"></a>`isxaki` | [Isxaki](ingestion/isxaki.md) | Original editions, works and books about Iskhaki |
| <a id="internet-archive-originals"></a>`internet_archive` | [Internet Archive](ingestion/internet-archive.md) | Public original documents explicitly labelled Tatar |
| <a id="kfu-historical-books-and-manuscripts"></a>`kfu_books` | [KFU books](ingestion/kfu-books.md) | Turkic–Tatar books: direct files and supported readers |
| `kfu_manuscripts` | [KFU manuscripts](ingestion/kfu-books.md) | Turkic–Tatar manuscripts: direct files and supported readers |
| <a id="kfu-ил-newspaper"></a>`kfu_il` | [KFU «Ил»](ingestion/kfu-il.md) | Explicitly Tatar-labelled newspaper issues |
| <a id="tataroved-publication-archive"></a>`tataroved` | [Tataroved](ingestion/tataroved.md) | Bibliographic Tatar-language claims or hash-reviewed originals |
| <a id="kfu-academic-electronic-archive"></a>`kfu_dspace` | [KFU academic archive](ingestion/kfu-dspace.md) | Tatar-topic search; language claims or reviewed files |
| <a id="kfu-historical-repository-all-collections"></a>`kfu_repository` | [KFU historical repository](ingestion/kfu-repository.md) | All collections; explicit Tatar item-language admission |
| <a id="kfu-азад-халык-newspaper"></a>`kfu_azad_halyk` | [KFU «Азад халык»](ingestion/kfu-azad-halyk.md) | Explicitly Tatar-labelled newspaper issues |
| <a id="kfu-шура-journal"></a>`kfu_shura` | [KFU «Шура»](ingestion/kfu-shura.md) | Explicitly Tatar-labelled historical journal issues |
| <a id="kfu-вакыт-newspaper"></a>`kfu_vakyt` | [KFU «Вакыт»](ingestion/kfu-vakyt.md) | Exact-series search; explicit Tatar item-language admission |
| <a id="tatar-galyame-educational-catalog"></a>`tatargalyame` | [Tatar Galyame](ingestion/tatargalyame.md) | Hosted educational documents across all languages |
| <a id="wikimedia-commons-original-documents"></a>`commons` | [Wikimedia Commons](ingestion/commons.md) | Checksum-verified original document uploads |
| <a id="miras-periodicals"></a>`miras_periodicals` | [Miras periodicals](ingestion/miras-periodicals.md) | Tatar source claims; browser session required |
| <a id="miras-books-and-browser-session-access"></a>`miras` | [Miras books](ingestion/miras.md) | Exposed book PDFs across all languages; browser session required |
| `magarif` | [Мәгариф](ingestion/magarif.md) | Archive attachments |
| `tatarica` | [Tatarica](ingestion/tatarica.md) | Documents linked from library books and journal articles |
| `darul_kutub` | [Darul-Kutub](ingestion/darul-kutub.md) | Public book/journal originals across all languages |
| `tatkniga` | [Tatkniga](ingestion/tatkniga.md) | Tatar/bilingual originals and supported public flipbooks |
| `kazanutlary` | [Kazan Utları](ingestion/kazanutlary.md) | Scanned issue images assembled into PDFs |
| `litres` | [Litres](ingestion/litres.md) | Unified stages, SID access and legacy migration |
| `milli_kitaphana` | [Milli Kitaphana](ingestion/milli-kitaphana.md) | Unified stages, configured access and legacy migration |

## Deferred candidates

[Belem.ru](ingestion/belem-deferred.md) remains deferred by the owner.

## Compatibility bookmarks

<a id="deferred-source-belemru"></a>
<a id="shared-configuration-and-operation"></a>
<a id="file-level-language-reviews"></a>
<a id="miras-cookie-based-access-pilot"></a>
<a id="remembered-fallback-ordinary-browser-extension"></a>

- [Shared configuration and recovery](ingestion/operations.md).
- [File-level language reviews](ingestion/kfu-dspace.md#file-level-language-reviews).
- [Miras session access and browser fallback](ingestion/miras.md).
