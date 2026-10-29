# KFU academic electronic archive

`kfu_dspace` is a separate source from `kfu_repository`. Configure
`sources.kfu_dspace.archive_url: https://dspace.kpfu.ru/xmlui/discover` in the
operational YAML (also shown in `ingestion.example.yaml`).

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source kfu_dspace --max-pages 2
.venv/bin/python cli.py --config ingestion.yaml download --source kfu_dspace --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source kfu_dspace --max-pages 2 --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source kfu_dspace
```

Discovery follows the native `татар` topic search, with ten items per page. The
initial search advertised 248 records. This is a candidate-search slice, not
exhaustive coverage of every Tatar document in the academic repository. Search
terms, subjects and titles do not establish document language. The source's UI
did not offer a working language filter during inspection. Native pagination,
displayed ranges, unique handles, count changes and final root-count verification
are checked. Bounded discovery resumes from saved pages and record checkpoints.
A changed count or repeated identity requires a fresh scan.

Each item is fetched using its native `?show=full` route. Full metadata rows,
raw DC tags, authors, dates, series, rights and file inventories are retained.
The third metadata-table column is the locale of a metadata value; `ru_RU` there
is not treated as the document's language. `dc.language.iso`, `dc.language` and
`DC.language` values supply the explicit item-language claims. Recognized Tatar
labels admit files; recognized other-language labels exclude them. Missing,
blank or unknown language labels remain held. Existing historical KFU language
policies are unchanged.

Public original PDFs are resolved from the explicitly linked native viewer's
record ID, filename and sequence using the same path construction as the site's
PDF.js script. Explicit native original links are supported too. Access flags and
record-level restrictions are retained; “только для КФУ” and other explicit access
restrictions take precedence over language evidence. Restricted files are not
requested, and account/institutional access follow-up is deferred. Only same-origin
HTTPS GET requests on the fixed search, item and original routes are permitted;
login/resource-changing redirects, unsafe filenames and mismatched record/file
identities are rejected. Unsupported formats remain inventory. PDFs retain their
original bytes; no OCR, image assembly, resampling, or automated language classifier
is introduced. Acquired PDFs must have a PDF signature, readable page structure,
and no password requirement. File/transfer/item/time/disk limits, atomic publication,
SHA-256/MD5 hashes, conditional rechecks and verified local reuse apply.

## File-level language reviews

For files without usable item-language labels, inspect the actual PDF before
admitting it. Record the review at
`<artifacts_root>/kfu_dspace/language-reviews.json`. It is optional and local to the
artifact directory; it is not a default allowlist embedded in the adapter.

```json
{
  "version": 1,
  "files": {
    "https://dspace.kpfu.ru/xmlui/bitstream/handle/net/22102/10_179_000944.pdf?sequence=1&isAllowed=y": {
      "sha256": "ebc76333771db7ce4969665ffc4d2a300bd658e8823aef0eab89e18369975f50",
      "languages": ["tt", "ru"],
      "reviewer": "Codex manual PDF text inspection",
      "reason": "Title page and body pages 5, 18, 45, 90 and 141 contain substantive Tatar and Russian textbook text."
    }
  }
}
```

The example hash is from the inspected original, not a wildcard. Use the exact
original URL recorded in the manifest. Each review requires a lowercase SHA-256,
Tatar-containing language labels, a reviewer and a reason; additional audit fields
such as inspection date and page numbers are retained. Reviews affect only their
individual PDF and never lift access restrictions or format exclusions. They can
override an inaccurate non-Tatar source label while preserving the raw source claim.

Discovery records matching reviews. `download` also reapplies current reviews to
already discovered records and writes an observation when evidence changes, so a
full catalog rescan is unnecessary to grant or withdraw a review. A new URL still
needs discovery before acquisition. Withdrawing a review holds the file again;
existing original bytes and acquisition history are retained. A changed hash
forces fresh acquisition and validation. A PDF whose bytes differ from its review
hash fails before publication and needs a new manual review. Language uncertainty
is not silently replaced by a title-based guess.

Artifacts live under `__artifacts/ingestion/kfu_dspace/`; separate source manifests
and existing collectors are unaffected. Language inspection samples used during
implementation are retained separately under `__artifacts/kfu-dspace-inspection/`.

Manual verification completed the full 248-record search scan, including native
pagination, a resumed invocation, and final advertised-count verification. Older
thesis records without URI metadata are matched using their native full/short-view
self-links; separate cover viewers remain unsupported-format inventory. There are
no remaining discovery errors. Source language claims selected no records directly:
82 records had recognized other-language labels, while 166 had missing or unknown
labels. Seven records explicitly declared KFU-only access. These categories do not
imply that every record exposes a downloadable original.

Two individual PDF reviews were recorded after actual content inspection:

| Record | Original | Size | PDF pages | Review evidence |
| --- | --- | ---: | ---: | --- |
| `net/176943` | `kils2022_480_484.pdf` | 284,735 bytes | 5 | Tatar prose on pages 1 and 3; references on page 5 |
| `net/22102` | `10_179_000944.pdf` | 4,891,338 bytes | 147 | Tatar and Russian text across the title and five sampled body pages |

Both were acquired through normal CLI downloads and matched their pinned SHA-256.
Repeat download reused both with zero HTTP requests. An isolated withdrawn-review
run held the original without requests while retaining its bytes and acquisition
history. An isolated deliberately incorrect review hash fetched one PDF, rejected
it and published no original. Compilation and diff checks passed. No automated
tests were added, and no corpus-wide content-language inference was performed.
