# KFU academic electronic archive

`kfu_dspace` is a separate source from `kfu_repository`. Configure
`sources.kfu_dspace.archive_url: https://dspace.kpfu.ru/xmlui/discover` in the
operational YAML (also shown in `ingestion.example.yaml`).

```bash
.venv/bin/python cli.py --config config/sources/kfu_dspace.yaml discover --source kfu_dspace --max-pages 2
.venv/bin/python cli.py --config config/sources/kfu_dspace.yaml download --source kfu_dspace --limit 1
.venv/bin/python cli.py --config config/sources/kfu_dspace.yaml run --source kfu_dspace --max-pages 2 --limit 1
.venv/bin/python cli.py --config config/sources/kfu_dspace.yaml status --source kfu_dspace
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
admitting it. The selected YAML explicitly sets `language_reviews_file` to
`../reviews/kfu_dspace.json`, resolved relative to that YAML's directory. This
versioned input carries two previously reviewed, hash-pinned files into fresh
GitHub runners. It is curated admission evidence, not processing state; matched
reviews are recorded in PostgreSQL observations. A configured missing or invalid
review input fails rather than silently admitting files or losing the reviews.

Optional local additions at `<artifacts_root>/kfu_dspace/language-reviews.json`
are loaded afterward and override configured entries for matching URLs. They are
not transferred to GitHub automatically. If `language_reviews_file` is omitted,
the existing local-only input behavior remains available. Neither input creates
records or guesses download URLs: discovery must still provide authoritative
file/access metadata before admission. Only actual PDF originals are acquired;
webpage text and HTML conversion are outside this source.

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
original URL recorded in PostgreSQL. Each review requires a lowercase SHA-256,
Tatar-containing language labels, a reviewer and a reason; additional audit fields
such as inspection date and page numbers are retained. Reviews affect only their
individual PDF and never lift access restrictions or format exclusions. They can
override an inaccurate non-Tatar source label while preserving the raw source claim.

Discovery records matching reviews. `download` also reapplies current reviews to
already discovered records and writes an observation when evidence changes, so a
full catalog rescan is unnecessary to grant or withdraw a review. A new URL still
needs discovery before acquisition. To withdraw a review, remove it from both
configured and local inputs before invoking discovery/download; deleting a local
override alone leaves the configured review active. Withdrawal holds the file again;
existing original bytes and acquisition history are retained. A changed hash
forces fresh acquisition and validation. A PDF whose bytes differ from its review
hash fails before publication and needs a new manual review. Language uncertainty
is not silently replaced by a title-based guess.

Originals live under `__artifacts/ingestion/kfu_dspace/`; processing state and
observations live in PostgreSQL. Other source state is unaffected. Language inspection samples used during
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

## PostgreSQL, S3 and manual GitHub execution

Set `DATABASE_URL` and initialize the schema once with
`.venv/bin/python cli.py database init`. Processing stores observations, review
evidence, frontier checkpoints, results, errors and S3 receipts in PostgreSQL;
there is no JSON-progress fallback. Review JSON files are explicit inputs, not
queue/checkpoint state. See [database operations](../postgres-migration.md).

`download` is local. `run` downloads and publishes finished original PDFs to S3
after committed checkpoints, retaining local files. Standalone `publish` retries
from local originals and reports missing files:

```bash
.venv/bin/python cli.py --summary-only --config config/sources/kfu_dspace.yaml run --source kfu_dspace --max-pages 2 --limit 1
.venv/bin/python cli.py --summary-only --config config/sources/kfu_dspace.yaml publish --source kfu_dspace --target s3 --limit 1
```

Set `S3_BUCKET` and standard AWS credentials. Shared publication uses deterministic
keys, SHA-256 metadata and PostgreSQL receipts. Fresh runners reacquire missing
unpublished originals while receipts allow published files to be skipped.
Restricted, unsupported and unreviewed-language assets are never admitted by a
review file; matching reviews lift only language holds on otherwise eligible PDFs.

The existing **Ingest kfu_dspace** workflow supports manual dispatch through the
shared runner and `config/scheduled.yaml` limits. No schedule is added. Required
repository secrets: `DATABASE_URL`, `S3_BUCKET`, `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`; optional `AWS_SESSION_TOKEN`. Optional repository
variables: `S3_ENDPOINT_URL`, `AWS_DEFAULT_REGION`. Initialize PostgreSQL before
dispatch. Versioned review inputs arrive through checkout; local originals on
runners are temporary, while PostgreSQL and S3 retain durable state/files. See
[runner operations](../scheduled-ingestion.md).

## Current discovery blocker, 2026-11-07 (Europe/Moscow)

The search remains reachable and advertises 248 candidates. Five search pages
were retained, but the first 40 item parses failed. Sampled HTTP-200 full item
pages omit the required metadata table and file inventories. Short views of two
known records also omit their item/file content. The read-only scan was stopped
after repeated failures; it is incomplete and produced no successful item
observations. Parser version 3 now reports this missing-table condition explicitly.
No empty shell is treated as a valid record or used to infer public access.
Fresh discovery requires restoration of authoritative item metadata/file
inventories, or separate verification of another native source route. This is
independent of the repository's database/storage credential requirements.

The two exact URLs from the existing manual review input still delivered complete
PDFs. They were reacquired using shared HTTP/native guards, exact filename and
sequence checks, declared lengths, PDF structure checks and pinned hashes:

- `net/176943`: `kils2022_480_484.pdf?sequence=-1&isAllowed=y`, 284,735 bytes,
  five pages, SHA-256 `2bc8ca4f2a5cc1f249ef6e39810058dca15d50813ccde100cb04a568c6333341`.
- `net/22102`: `10_179_000944.pdf?sequence=1&isAllowed=y`, 4,891,338 bytes,
  147 pages, SHA-256 `ebc76333771db7ce4969665ffc4d2a300bd658e8823aef0eab89e18369975f50`.

Both match the saved reviews. Rendered article page 3 and textbook pages 18/141
confirm the reviewed Tatar/Tatar-Russian content. An initial article probe used
the wrong `sequence=1` and failed PDF validation; the saved review's exact
`sequence=-1` URL was then used successfully. No guessed route was added to the
adapter or review configuration. The versioned review input preserves the prior
reviewers, inspection evidence and dates; these are not new blanket language
decisions. File availability does not repair the missing discovery metadata.

Evidence is ignored under `__artifacts/kfu-dspace-review-20261107/`: five listing
bodies, blocked summary, two PDF originals and selected renders/hash report.
Full/short-view inspection responses are in
`__artifacts/inspections/2026-11-06T22-17-*` and `2026-11-06T22-19-*` (UTC).
These are review exports, not processing state. Manual configuration checks with
an empty runner artifact root loaded both configured reviews successfully.
Compilation, capability listing, workflow generator equality and
`git diff --check` passed. No automated tests were added. Full database-backed
acquisition, resume, repeat-run and S3 receipts remain unverified because
credentials are unset; no production writes, uploads or GitHub dispatch occurred.
