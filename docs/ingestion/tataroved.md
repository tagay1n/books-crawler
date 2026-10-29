# Tataroved publication archive

`tataroved` selects `https://tataroved.ru/publication/`. Add its source entry from
`ingestion.example.yaml` to the operational YAML. The Latin-domain publication
archive is distinct from the separately supplied Cyrillic `татаровед.рф` library
address; this adapter covers only `tataroved.ru` and its `www` alias.

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source tataroved --max-pages 2
.venv/bin/python cli.py --config ingestion.yaml download --source tataroved --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source tataroved --max-pages 2 --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source tataroved
```

The root catalog exposes a flattened native link hierarchy. Initial inspection
found 389 entries in the main catalog region, including categories, books,
chapters, and other publication pages. This is not a count of downloadable books
or an independently advertised numerical total. Discovery inspects every linked
entry once and preserves catalog titles/descriptions and native publication paths.
The final catalog fetch checks both the link count and the complete set of
identities. A changed catalog requires a fresh scan. Durable record checkpoints
allow interrupted discovery to resume; bounded runs stay incomplete while any
record or verification request remains. `--max-pages` counts catalog requests,
not individual publication records; time limits also bound record inspection.

The source's UTF-8 content is decoded explicitly by the shared HTTP layer. Old
absolute HTTP links and `www` aliases normalize to stable publication/file IDs.
The legacy site redirects public metadata pages and originals to HTTP, including
metadata rewrite routes with equivalent `url`/`bso_rewrite_url` parameters. Requests
start from normalized HTTPS URLs; native HTTP redirects are accepted only when
the resource identity is unchanged. Actual final transfer URLs are retained in
results. No authenticated sessions or credentials are used. Requests and redirects stay on the
two native aliases. Unrelated query parameters, rewrite-path changes, unsafe paths,
external download origins, and resource-changing redirects are rejected.

Per-entry titles, bibliographic subtitles, body descriptions, HTML references and
file inventories are retained. HTML-only pages, including books rendered as web
text, remain metadata; HTML is not converted to PDF. Direct supported document
originals include PDF, DjVu, EPUB, text and office formats. ZIP/RAR/7z packages
remain unsupported inventory, without expansion. External file references remain
metadata and are not fetched. Original bytes, colours and resolution are retained;
no image assembly, OCR, resampling, or content-language classifier is introduced.
The shared file, transfer, item, deadline and disk limits apply, along with atomic
publication, SHA-256/MD5 hashes, local integrity checks and conditional rechecks.

Language admission uses explicit statements in the entry's own bibliographic
subtitle, such as `(на татарском языке)` or a declared multilingual-language list.
Tatar titles, the site interface, topic categories, and bibliography references
are insufficient by themselves. The matched source statement is retained as
`language_evidence`; it is a source claim, not independent content verification.
Recognized other-language claims are excluded, and unknown/missing claims remain
held. A bibliographic claim about a web-text edition does not invent a file asset.

For an individually inspected multilingual original, use
`<artifacts_root>/tataroved/language-reviews.json` with the same version-1 schema
as the academic KFU adapter. Keys must be exact normalized original URLs from the
manifest. A review requires SHA-256, Tatar-containing language labels, reviewer
and reason. Example for the inspected 240-page conference volume:

```json
{
  "version": 1,
  "files": {
    "https://tataroved.ru/publicat/new/Gasprin_sbornik.pdf": {
      "sha256": "dab17261171565340e2f2d3777421386e35e3408e3e91e1bbd45ce76443efbe6",
      "languages": ["tt", "ru"],
      "reviewer": "Codex manual PDF text inspection",
      "reason": "Russian title/front matter and substantive Tatar articles on PDF pages 106, 130 and 139."
    }
  }
}
```

These are individual byte-pinned reviews, not collection-level language overrides.
A changed PDF hash fails before publication. Reviews cannot admit external URLs,
unsupported packages or formats. Discovery records applicable reviews; download
also refreshes them for existing records without requiring a catalog rescan.
Withdrawn reviews restore the source's language hold, retaining previous bytes and
observation/result history. New file URLs still require discovery. Review parsing,
refresh and pin enforcement are shared with the academic KFU adapter; its existing
review behavior remains in place.

Artifacts live under `__artifacts/ingestion/tataroved/`. The previously requested
Belem deferral note remains unchanged below; Belem is not part of this adapter.

Manual CLI verification inspected all 389 native catalog entries and verified
both their count and final identities, with no discovery errors. Of those records,
9 had recognized Tatar claims in their own subtitles, 2 had other-language claims,
and 378 required review; those counts include HTML-only pages. The scan inventoried
116 file references, with 111 held for missing language evidence and 4 external
references excluded. One multilingual PDF had an individual content review.

The reviewed `Gasprin_sbornik.pdf` downloaded as 1,762,258 original bytes and opened
as 240 pages. Its SHA-256 matched the review above; MD5 was
`a6592804280a068fa80d84292087da01`. Repeat download reused the verified original
with zero requests. In isolated CLI checks, withdrawing its review held the file
without requests while retaining its bytes/history; an incorrect review hash
rejected the transfer and published no original. A same-count changed catalog
identity triggered `restart_required`. The academic KFU adapter also reused both
of its existing reviewed PDFs with zero requests after the shared-review refactor.
Compilation and diff checks passed; no automated tests were added.
