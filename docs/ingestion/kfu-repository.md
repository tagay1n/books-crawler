# KFU historical repository: all collections

`kfu_repository` selects `https://repo.kpfu.ru/jspui/community-list`. Add the
matching entry from `ingestion.example.yaml` to the operational YAML. This covers
all collections explicitly listed by that historical repository, including new
collections appearing on later scans. Other domains such as `dspace.kpfu.ru`,
`allfind.kpfu.ru` and `tatargalyame.kpfu.ru` are outside this adapter.

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source kfu_repository --max-pages 25
.venv/bin/python cli.py --config ingestion.yaml download --source kfu_repository --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source kfu_repository --max-pages 25 --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source kfu_repository
```

The native tree advertised 180 collections and 20,645 collection memberships
when inspected. These counts include non-Tatar holdings and overlaps; they are
not a count of unique eligible documents. Each collection is enumerated using
its own native offset pagination and advertised count, then its first page is
fetched again to verify that count. Duplicate records within a collection trigger
a restart; records shared by different collections retain all discovered
memberships under one handle. Collection titles, handles, community ancestry,
source counts, issue titles, dates, type labels and series values are retained.

Work proceeds one collection at a time, starting with existing Tatar-focused
slices. The durable frontier retains remaining collections, page offsets and
record checkpoints. A final fetch checks that the complete collection tree is
unchanged. A changed count, repeated identity within a collection or changed
final tree requires a new scan. Bounded invocations report incomplete discovery.
Counts are verified per collection; the shared `count_verified` field remains
false because there is no single repository-wide unique-item count. Completion
requires exhausting every collection and its verification request, the final tree
check, and all pending records. A new invocation after completion refreshes the tree.

All collections use explicit item-level Tatar admission, including multilingual
records containing a recognized Tatar label. Missing labels remain held; recognized
other languages are excluded. Neither collection title nor script substitutes for
a language label. Existing books/manuscripts adapters retain their original
all-language policy. Restricted files and unsupported formats remain inventories;
no authentication, copy-request submission, or archive expansion is introduced.
Explicit native “no files” records are retained as metadata rather than errors.
Public direct documents and supported JPEG/JPEG2000 readers reuse the shared KFU
downloader; complete page sets produce 200 DPI colour PDFs under existing limits.

Single-file viewer links (`bitstream.jsp?net/ID/SEQUENCE/view`) can identify
auxiliary images such as receipts. They are retained as unsupported metadata
instead of making the entire book fail parsing; restricted images remain
`kfu_restricted`. The downloader still rejects single-file viewers as supported
image-reader routes, so this adds no receipt/image acquisition capability. Public
document files in the same record are evaluated independently.
Manual verification of `net/26934` acquired only its public `Фәлсәфи сүзлек` PDF:
85,064,699 bytes / 323 pages, SHA-256
`b1276d71dc029ac7dc176c94da9b792a7b38734c224be758d9ed3eb109881577`.
Rendered page 11 contains Tatar dictionary text. The restricted receipt remained
unsupported; an isolated repeat skipped the verified PDF with zero requests.
Evidence: `__artifacts/session-20261028/kfu-single-viewer/` and session logs.

Before acquisition, the adapter looks for matching original URLs, formats and
source versions in other `kfu_*` manifests under the same configured artifact root.
It verifies file size and SHA-256, then imports by hard link (or atomic copy) into
its own content-addressed store. Imported results retain the original source,
asset, result and observation IDs alongside their new observation relationship.
Existing manifests are not changed. Derived PDFs are rebuilt locally if needed;
page originals are reused. `--recheck` still performs normal HTTP revalidation.
This avoids repeat original transfers between the old slices and this adapter;
content identity of different previously unseen URLs is established after retrieval.
Artifacts live under `__artifacts/ingestion/kfu_repository/`. Existing source names
remain available for narrowly scoped collection runs.

Manual verification discovered the live 180-collection tree and 19 records in the
first two collections, including one explicit metadata-only record. A separate
invocation resumed the same scan and inspected 20 Il records without errors.
Two live Il listing batches correctly advanced offsets 0 → 20 → 40 and retained
40 distinct identities. A Russian-labelled record was excluded and an unlabelled
Vakyt record remained held. The final-tree verification branch was checked against
the saved native tree; a complete repository traversal was not performed.

Acquisition imported an existing 8,466,638-byte PDF from `kfu_azad_halyk` and
retrieved one new 8,751,131-byte PDF with one HTTP request. Both originals opened
as eight-page PDFs. An isolated repeat reused both with zero requests. Request
identities remain compact while larger resume snapshots stay in the frontier;
legacy adapters retain their original request-key behavior. After that change,
a fresh bounded CLI scan verified the first collection's complete 15-record count
without errors. Compilation and diff checks passed; no automated tests were added.
