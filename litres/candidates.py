"""Review and import helpers for Litres discovery candidates."""

import csv
import json
import os

from utils import dump_json_atomic, get_hash, get_in_workdir


CANDIDATES_INDEX = "../__artifacts/litres/candidates-index.json"
BOOKS_INDEX = "../__artifacts/litres/books-index.json"
REVIEW_TSV = "../__artifacts/litres/candidates-review.tsv"
VALID_REVIEW_STATUSES = {"candidate", "accepted", "rejected", "maybe"}
REVIEW_COLUMNS = (
    "id",
    "status",
    "score",
    "content_type",
    "litres_language",
    "title",
    "author",
    "signals",
    "url",
)


def export_review():
    """Export candidates-index.json to an editable TSV review file."""
    candidates = _load_json(get_in_workdir(CANDIDATES_INDEX))
    review_path = get_in_workdir(REVIEW_TSV)
    os.makedirs(os.path.dirname(review_path), exist_ok=True)

    rows = [_review_row(key, candidate) for key, candidate in candidates.items()]
    rows.sort(key=lambda row: (-_int(row["score"]), row["content_type"], row["title"]))
    with open(review_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} candidate(s) to {review_path}")


def sync_review():
    """Sync edited statuses from candidates-review.tsv back into candidates-index.json."""
    candidates_path = get_in_workdir(CANDIDATES_INDEX)
    review_path = get_in_workdir(REVIEW_TSV)
    candidates = _load_json(candidates_path)
    rows = _load_review_rows(review_path)

    updated = 0
    unchanged = 0
    skipped_unknown = 0
    for row in rows:
        key = row["id"]
        if key not in candidates:
            skipped_unknown += 1
            continue
        status = _normalize_status(row["status"], row_number=row["_row_number"])
        if candidates[key].get("status", "candidate") == status:
            unchanged += 1
            continue
        candidates[key]["status"] = status
        updated += 1

    dump_json_atomic(candidates, candidates_path)
    print(f"Synced review statuses from {review_path}")
    print(f"Updated {updated}, unchanged {unchanged}, skipped unknown {skipped_unknown}")


def import_accepted():
    """Import accepted discovery candidates into books-index.json."""
    candidates = _load_json(get_in_workdir(CANDIDATES_INDEX))
    books_path = get_in_workdir(BOOKS_INDEX)
    books = _load_json(books_path)
    existing_urls = {book.get("url") for book in books.values() if book.get("url")}

    accepted = 0
    imported = 0
    skipped_existing = 0
    skipped_invalid = 0
    for candidate in candidates.values():
        if candidate.get("status") != "accepted":
            continue
        accepted += 1
        if not _is_importable(candidate):
            skipped_invalid += 1
            continue
        if candidate["url"] in existing_urls:
            skipped_existing += 1
            continue
        key = get_hash(candidate["url"])
        books[key] = _book_from_candidate(candidate)
        existing_urls.add(candidate["url"])
        imported += 1

    dump_json_atomic(books, books_path)
    print(f"Accepted candidates: {accepted}")
    print(f"Imported {imported} into {books_path}")
    print(f"Skipped existing {skipped_existing}, skipped invalid {skipped_invalid}")
    print(f"Index contains {len(books)} books")


def _load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _review_row(key, candidate):
    return {
        "id": key,
        "status": candidate.get("status", "candidate"),
        "score": str(candidate.get("score", "")),
        "content_type": candidate.get("content_type") or "",
        "litres_language": candidate.get("litres_language") or "",
        "title": candidate.get("title") or "",
        "author": candidate.get("author") or "",
        "signals": ",".join(candidate.get("signals") or []),
        "url": candidate.get("url") or "",
    }


def _load_review_rows(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Review TSV does not exist: {path}")
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        missing = [column for column in ("id", "status") if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Review TSV is missing required column(s): {', '.join(missing)}")
        rows = []
        for row_number, row in enumerate(reader, start=2):
            row["_row_number"] = row_number
            rows.append(row)
        return rows


def _normalize_status(value, row_number=None):
    status = (value or "candidate").strip().lower()
    if status not in VALID_REVIEW_STATUSES:
        location = f" on row {row_number}" if row_number else ""
        raise ValueError(
            f"Invalid review status{location}: {value!r}. "
            f"Expected one of: {', '.join(sorted(VALID_REVIEW_STATUSES))}"
        )
    return status


def _is_importable(candidate):
    return bool(candidate.get("url") and candidate.get("title") and candidate.get("content_type") in {"pdf", "text"})


def _book_from_candidate(candidate):
    book = {
        "title": candidate["title"],
        "url": candidate["url"],
        "subscription": bool(candidate.get("subscription", True)),
        "content_type": candidate["content_type"],
        "downloaded": False,
    }
    for key in ("author", "full_name", "summary", "litres_language"):
        if candidate.get(key):
            book[key] = candidate[key]
    if not book.get("full_name"):
        book["full_name"] = (
            f"{book['title']} - {book['author']}" if book.get("author") else book["title"]
        )
    return book


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
