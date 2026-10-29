# Kazan Utları archive

Kazan Utları follows every linked year listing across Казан утлары, Яңалиф,
Совет әдәбияты, Атака, and Безнең юл. Native year URLs are preserved even when
their slugs differ from their visible labels. Duplicate navigation links are
collapsed. Issue article-index pages and unrelated footer PDFs are excluded.
Issue metadata retains headings, descriptions when supplied, journal/year listing
context, and the literal reader configuration. Listing context is checkpointed
and appended as source evidence when an issue appears in another listing.

The reader's `count` is interpreted as the total image count: indices `000`
through `count - 1`, including the first reader image. Four inspected issues exposed this many
images while their reader's inclusive loop requested an additional nonexistent
image. This indexing discrepancy is preserved in metadata. Unrecognized reader
structures fail discovery instead of producing guessed image sequences. Catalog
completion means traversal of linked listings; no site-wide total is advertised.

For `kazanutlary`, `--limit` and `max_items` count **issues**, including their image
downloads and assembly. See the [Tatkniga guide](tatkniga.md) for its mixed file/book
units and each other source's guide for its download units. Byte, file-size, deadline, pacing,
and disk-reserve controls still apply. Interrupted
issues resume from verified image files on the next invocation. A failed page
does not discard the other pages, and an issue remains incomplete until every
expected page is available. No partial PDF is published.

JPEGs are retained as upstream originals in `files/`. PyMuPDF embeds them in
numeric order, preserving image quality, proportions, and orientation. Generated
PDFs live in `__artifacts/ingestion/kazanutlary/derived/<sha256>.pdf`; they are
derived artifacts, not upstream PDFs. The manifest records PDF hashes, size,
page count, assembler version, source observation, input fingerprint, and ordered
image asset/result IDs and hashes. Assembly enforces the configured file-size cap
and publishes atomically after reopening and checking the page count. There is
no OCR or text extraction.

`download` verifies local images and PDFs, reuses unchanged complete issues, and
rebuilds missing, damaged, or outdated PDFs. `--recheck` revalidates image URLs;
changed inputs create another retained PDF result. Failed rechecks leave the
issue unresolved while preserving historical files. Status includes recorded
image progress and complete/incomplete/failed PDF issue counts; it remains a
read-only manifest view rather than an integrity audit.
