# KFU «Шура» journal

`kfu_shura` selects <https://repo.kpfu.ru/jspui/handle/net/25046> and keeps an
independent manifest under `__artifacts/ingestion/kfu_shura/`. Add its source entry
from `ingestion.example.yaml` to the selected operational YAML.

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source kfu_shura --max-pages 2
.venv/bin/python cli.py --config ingestion.yaml download --source kfu_shura --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source kfu_shura --max-pages 2 --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source kfu_shura
```

Shura uses the same explicit Tatar language policy as Il: recognized Tatar labels
admit a record, known other-language-only labels are `language_excluded`, and missing
or unrecognized labels are `language_unknown`. Raw metadata and file references
remain available for review. Collection membership and a Tatar issue title do not
replace a language label. The shared periodical metadata identifies the publication
as `Шура`, kind `journal`, preserving issue titles, dates, and series as supplied.
Existing KFU books/manuscripts and Il retain their current admission policies.

The collection advertised eight records on 2026-10-27. Seven 1917 issues identify
`DC.language: tt` and expose public direct PDFs of roughly 13–18 MB each. The eighth
record, `net/492`, describes the 1910 volume containing №1–24 and exposes a public
PDF displayed as 373.86 MB, but provides no `DC.language`. It is deliberately held
as `language_unknown`; discovery retains its metadata and file URL without fetching
the volume. The current 100 MiB per-file cap would also need explicit adjustment
before a later approved acquisition of that volume. No language override or size-cap
increase is made for it.

Native listing-range and count checks, restriction handling, stable handle identities,
hashes, atomic publication, and resumable downloads reuse the existing KFU adapter.
For the current eight-record collection, one listing response plus its final root
count recheck consumes two discovery pages. `--limit` counts direct files or whole
image-based issues; supported readers inherit the existing 200 DPI colour policy.
Public direct PDFs take priority and are retained without conversion. No account,
copy-request submission, archive expansion, or new image format support is introduced.

Manual CLI verification on 2026-10-27 completed discovery of all eight records
and verified the advertised count. Seven PDFs were eligible; the 1910 volume
remained `language_unknown` with no acquired bytes. One bounded download acquired
`net/25077`'s `№ 7.pdf` (18,427,602 bytes) in one request without retries. Local
inspection confirmed 28 readable PDF pages, matching recorded SHA-256/MD5, and the
acquisition-observation link. An isolated repeat skipped the completed issue and
held volume with zero requests. The main queue retains six pending PDFs, one
downloaded issue, and the held volume. Existing Il publication/admission metadata
and the all-language books/manuscripts policy were manually checked. Verification
used code inspection, compilation, and CLI runs; no automated tests were added.
