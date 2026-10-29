# Bounded source inspection

Use this before writing an adapter or repeating a custom website probe:

```bash
.venv/bin/python cli.py inspect https://tuganzhir.org/archive/ --max-links 8
.venv/bin/python cli.py inspect https://tuganzhir.org/archive/ --probe-pdfs 1 --max-links 8
```

No operational YAML or session export is needed. Inspection makes public GET
requests with the shared HTTP pacing, timeouts and soft-deadline machinery.
It does not modify acquisition manifests or select documents for ingestion.

Each run creates a separate directory under `__artifacts/inspections/` containing:

- `page.body`: bounded response bytes, including HTTP error/challenge HTML when
  returned. PDF responses retain only a prefix of at most 1,024 bytes.
- `links.json`: up to 5,000 unique HTTP(S) links from anchors, embedded readers,
  objects and script references. Labels and document/PDF hints are retained.
- `pdf-N.prefix`: optional PDF-header probe bytes, at most 1,024 each.
- `report.json`: retrieval status, final URL, redirect chain, selected headers,
  byte counts, response-body completeness, hashes, link inventory and probe results.

Stdout is one JSON object, prioritizing document hints and showing at most
`--max-links` links (default 20, maximum 200). Read `links.json` only when that
summary identifies a useful follow-up. `--output-dir PATH` selects the parent
evidence directory; it does not overwrite a previous inspection.

The page byte cap defaults to 2 MiB and can be lowered with `--max-bytes` (minimum
1 KiB). The command has a 60-second soft deadline, one-second request pacing,
10-second connect and 15-second read timeouts, and a five-redirect limit.
An in-flight read can delay observation of the soft deadline. Byte counts describe
retained response bodies, not exact network traffic. There are no automatic retries.
The request count tracks logical fetches; redirect hops are listed separately.

PDF probing is off by default. `--probe-pdfs N` inspects up to N advertised PDF
leads (maximum ten) using a byte-range GET and a bounded read even when the server
ignores Range. By default both the probe target and redirects must remain on the
inspected page's final origin. `--allow-external` explicitly permits advertised
cross-origin PDF leads and their HTTP(S) redirects. Initial page redirects may
change origin, with every target validated as an HTTP(S) URL without credentials.
Non-web links and credential-bearing URLs are excluded.

The exit code is nonzero for a failed initial retrieval, invalid arguments or a
storage failure. A successfully reached page can contain broken PDF leads;
their individual HTTP/transport failures appear in `pdf_probes`. Capped pages
remain marked incomplete. A complete range-response body is not a complete PDF:
`pdf_signature` establishes only that the retained prefix contains `%PDF-`.
The command does not infer document language, printed completeness, registration
requirements or download eligibility, execute page scripts, or submit forms.

For acquisition and admission rules, use the [source-specific guides](local-ingestion.md).
