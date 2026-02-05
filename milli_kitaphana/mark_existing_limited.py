"""
Mark index entries that already exist as limited docs in the monocorpus database.

Why this exists:
- The DB already contains limited versions of some docs from other sources.
- We want to avoid re-downloading those from Milli Kitaphana.
- We match DB rows (Document.full == False) to index entries using upstream metadata.

How matching works:
1) Ensure upstream metadata is available locally (download zip if missing).
2) Read metadata.json and try to match index entries by fields in this order:
   doc_url -> download_code -> doc_card_url -> title
3) If a single match is found, mark the index entry with a flag.
4) If upstream_meta_url is missing, fall back to matching by DB title.
5) If a title match is found, clear downloaded/decrypted to force a full download.
6) If no match is found, raise an error (or log for the title fallback).

How to run:
python milli_kitaphana/mark_existing_limited.py
"""

import json
import os
import zipfile
from pathlib import Path

import requests
from sqlalchemy import create_engine, text
from utils import dump_index, load_index_file


DEFAULT_METADATA_ROOT = Path(os.path.expanduser("~/.monocorpus/misc/upstream_metadata"))
DEFAULT_FLAG_NAME = "needs_full_download"
DB_URL = "postgresql+psycopg://tans1q:tans1q@localhost:5432/monocorpus"
MIN_TITLE_PREFIX = 8


def _norm_url(value: str | None) -> str | None:
    """Normalize a URL for lookup by stripping whitespace and trailing slash."""
    if not value:
        return None
    return value.strip().rstrip("/")


def _norm_title(value: str | None) -> str | None:
    """Normalize a title for lookup by collapsing whitespace."""
    if not value:
        return None
    return " ".join(value.split())


def _download_zip(url: str, dest_path: Path) -> None:
    """Download an upstream metadata zip to the given path."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def _ensure_metadata(md5: str, upstream_url: str, metadata_root: Path) -> Path:
    """
    Return the path to metadata.json for md5, downloading and extracting if needed.
    Expected zip layout: {md5}.zip contains a single folder named {md5}/metadata.json.
    """
    md5_dir = metadata_root / md5
    meta_path = md5_dir / "metadata.json"
    if meta_path.exists():
        return meta_path

    zip_path = metadata_root / f"{md5}.zip"
    if not zip_path.exists():
        _download_zip(upstream_url, zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(metadata_root)

    if not meta_path.exists():
        raise FileNotFoundError(f"metadata.json not found for md5={md5} after extracting {zip_path}")
    return meta_path


def _load_upstream_metadata(md5: str, upstream_url: str, metadata_root: Path) -> dict | None:
    """Load upstream metadata.json for the given md5, downloading if missing."""
    if not upstream_url:
        return None
    meta_path = _ensure_metadata(md5, upstream_url, metadata_root)
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_lookups(index: dict) -> dict[str, dict[str, list[str]]]:
    """Build lookup tables from the index for fast matching by multiple fields."""
    lookups = {
        "doc_url": {},
        "download_code": {},
        "doc_card_url": {},
        "title": {},
    }

    def _add(mapping: dict, key: str | None, card_path: str) -> None:
        if not key:
            return
        mapping.setdefault(key, []).append(card_path)

    for card_path, meta in index.items():
        _add(lookups["doc_url"], _norm_url(meta.get("doc_url")), card_path)
        _add(lookups["download_code"], meta.get("download_code"), card_path)
        _add(lookups["doc_card_url"], _norm_url(meta.get("doc_card_url")), card_path)
        _add(lookups["title"], _norm_title(meta.get("title")), card_path)

    return lookups


def _match_index_entry(meta: dict, lookups: dict[str, dict[str, list[str]]]) -> tuple[str, str]:
    """
    Match an upstream metadata record to a single index entry.
    Returns (card_path, matched_by_field) or raises if no unique match is found.
    """
    candidates = [
        ("doc_url", _norm_url(meta.get("doc_url"))),
        ("download_code", meta.get("download_code")),
        ("doc_card_url", _norm_url(meta.get("doc_card_url"))),
        ("title", _norm_title(meta.get("title"))),
    ]

    for field, key in candidates:
        if not key:
            continue
        matches = lookups[field].get(key, [])
        if len(matches) == 1:
            return matches[0], field

    raise ValueError(
        "Could not match upstream metadata to index entry using doc_url, download_code, doc_card_url, or title."
    )


def _match_index_entry_by_title(title: str | None, lookups: dict[str, dict[str, list[str]]]) -> str | None:
    """Match an index entry by title prefix; return card_path if a single match is found."""
    key = _norm_title(title)
    if not key:
        return None

    key_len = len(key)
    if key_len < MIN_TITLE_PREFIX:
        return None

    matches = []
    for idx_title, card_paths in lookups["title"].items():
        if not idx_title:
            continue
        if idx_title.startswith(key):
            matches.extend(card_paths)

    if len(matches) == 1:
        return matches[0]
    return None


def mark_existing_limited(
    metadata_root: Path = DEFAULT_METADATA_ROOT,
    flag_name: str = DEFAULT_FLAG_NAME,
) -> None:
    """
    Mark index entries that already exist in the DB as limited (Document.full == False).

    The marker is stored in the index as `flag_name` and can be used later
    to skip downloads or produce a targeted subset.
    """
    index = load_index_file()
    lookups = _build_lookups(index)

    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        rows = conn.execute(
            text('SELECT md5, "full", upstream_meta_url, title FROM document WHERE "full" = false')
        ).all()

    updated = 0
    for md5, _full, upstream_url, db_title in rows:
        if not upstream_url:
            card_path = _match_index_entry_by_title(db_title, lookups)
            if not card_path:
                print(f"[warn] No title match for md5={md5!r} title={db_title!r}")
                continue
            index[card_path].pop("downloaded", None)
            index[card_path].pop("decrypted", None)
            index[card_path]["matched_by"] = "title"
            updated += 1
            continue

        meta = _load_upstream_metadata(md5, upstream_url, metadata_root)
        if not meta:
            print(f"[warn] Missing upstream_meta_url for md5={md5}; skipping.")
            continue
        card_path, matched_by = _match_index_entry(meta, lookups)
        index[card_path][flag_name] = True
        index[card_path]["matched_by"] = matched_by
        updated += 1

    dump_index(index)
    print(f"Marked {updated} index entries with '{flag_name}'.")


if __name__ == "__main__":
    mark_existing_limited()
