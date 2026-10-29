# Local document ingestion

Read only the guide for the source you are working on. The shared CLI uses
explicit operational YAML; examples are never loaded automatically. Start with
[configuration, budgets and recovery](ingestion/operations.md),
[implemented source scopes](ingestion/sources.md), or the
[adapter development map](adapter-development.md).

```bash
.venv/bin/python cli.py sources
.venv/bin/python cli.py --config ingestion.yaml status --source magarif
.venv/bin/python scripts/ingestion_overview.py __artifacts/ingestion
```

For candidate qualification before writing an adapter, use
[bounded source inspection](source-inspection.md).

## Source guides

Old section anchors are retained below for existing links and bookmarks.

| Source | Focused guide |
| --- | --- |
| <a id="tugan-zhir-archive"></a>Tugan Zhir archive | [Usage and evidence](ingestion/tuganzhir.md) |
| <a id="dum-rt-contemporary-tatar-publications"></a>DUM RT contemporary Tatar publications | [Usage and evidence](ingestion/dumrt.md) |
| <a id="fänni-tatarstan-issue-pdfs"></a>Fänni Tatarstan issue PDFs | [Usage and evidence](ingestion/ftatarstan.md) |
| <a id="sarhaan-tatar-publications"></a>Sarhaan Tatar publications | [Usage and evidence](ingestion/sarhaan.md) |
| <a id="obuchalka-reviewed-tatar-textbooks"></a>Obuchalka reviewed Tatar textbooks | [Usage and evidence](ingestion/obuchalka.md) |
| <a id="echo-of-centuries-article-pdfs"></a>Echo of Centuries article PDFs | [Usage and evidence](ingestion/echovek.md) |
| <a id="nizgar-magazine-archive"></a>Nizgar magazine archive | [Usage and evidence](ingestion/nizgar.md) |
| <a id="yazuchy-publisher-catalog"></a>Yazuchy publisher catalog | [Usage and evidence](ingestion/yazuchy.md) |
| <a id="turuz-dictionaries"></a>Turuz dictionaries | [Usage and evidence](ingestion/turuz.md) |
| <a id="мәгарифвакыт-textbook-packages"></a>Мәгариф–Вакыт textbook packages | [Usage and evidence](ingestion/magarif-vakyt.md) |
| <a id="безнең-мирас-issue-archive"></a>Безнең мирас issue archive | [Usage and evidence](ingestion/beznenmiras.md) |
| <a id="isxaki-books-and-works"></a>Isxaki books and works | [Usage and evidence](ingestion/isxaki.md) |
| <a id="internet-archive-originals"></a>Internet Archive originals | [Usage and evidence](ingestion/internet-archive.md) |
| <a id="kfu-historical-books-and-manuscripts"></a>KFU historical books and manuscripts | [Usage and evidence](ingestion/kfu-books.md) |
| <a id="kfu-ил-newspaper"></a>KFU «Ил» newspaper | [Usage and evidence](ingestion/kfu-il.md) |
| <a id="tataroved-publication-archive"></a>Tataroved publication archive | [Usage and evidence](ingestion/tataroved.md) |
| <a id="kfu-academic-electronic-archive"></a>KFU academic electronic archive | [Usage and evidence](ingestion/kfu-dspace.md) |
| <a id="kfu-historical-repository-all-collections"></a>KFU historical repository: all collections | [Usage and evidence](ingestion/kfu-repository.md) |
| <a id="kfu-азад-халык-newspaper"></a>KFU «Азад халык» newspaper | [Usage and evidence](ingestion/kfu-azad-halyk.md) |
| <a id="kfu-шура-journal"></a>KFU «Шура» journal | [Usage and evidence](ingestion/kfu-shura.md) |
| <a id="kfu-вакыт-newspaper"></a>KFU «Вакыт» newspaper | [Usage and evidence](ingestion/kfu-vakyt.md) |
| <a id="tatar-galyame-educational-catalog"></a>Tatar Galyame educational catalog | [Usage and evidence](ingestion/tatargalyame.md) |
| <a id="wikimedia-commons-original-documents"></a>Wikimedia Commons original documents | [Usage and evidence](ingestion/commons.md) |
| <a id="miras-periodicals"></a>Miras periodicals | [Usage and evidence](ingestion/miras-periodicals.md) |
| <a id="miras-books-and-browser-session-access"></a>Miras books and browser-session access | [Usage and evidence](ingestion/miras.md) |
| <a id="deferred-source-belemru"></a>Deferred source: Belem.ru | [Usage and evidence](ingestion/belem-deferred.md) |
| Magarif archive attachments | [Usage and evidence](ingestion/magarif.md) |
| Tatarica library | [Usage and evidence](ingestion/tatarica.md) |
| Darul-Kutub originals | [Usage and evidence](ingestion/darul-kutub.md) |
| Tatkniga public library | [Usage and evidence](ingestion/tatkniga.md) |
| Kazan Utları archive | [Usage and evidence](ingestion/kazanutlary.md) |

<a id="shared-configuration-and-operation"></a>
<a id="file-level-language-reviews"></a>
<a id="miras-cookie-based-access-pilot"></a>
<a id="remembered-fallback-ordinary-browser-extension"></a>

## Shared operation and compatibility links

- [Configuration, artifacts, budgets and recovery](ingestion/operations.md).
- [File-level language reviews](ingestion/kfu-dspace.md#file-level-language-reviews).
- [Miras session export and retained access pilot](ingestion/miras.md).
- [Remembered browser fallback](ingestion/miras.md#remembered-fallback-ordinary-browser-extension).
- [Latest autonomous session handoff](autonomous-session-2026-10-28.md).

Metadata claims, candidate counts, downloaded originals and derived PDFs are
separate evidence levels. Follow each adapter's admission and access policy.
