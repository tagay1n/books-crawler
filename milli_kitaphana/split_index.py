"""Splits pending index entries into N JSON sublists, optionally filtering by criteria."""

import copy
import json
import os

from rich import print

from utils import dump_index, get_list_file_loc, get_lists_dir, get_not_downloaded_docs, load_index_file


def split_lists(parts: int, dest: str = None, prefix: str = None):
    if parts < 1:
        raise ValueError("Parts must be greater than zero")

    index = load_index_file()
    docs = get_not_downloaded_docs(index, limited_only=False)

    filters = _load_filter()
    if filters:
        print(f"Loaded filter.json with {len(filters['download_codes'])} download_code(s) and {len(filters['titles'])} title(s)")
        docs = [
            (card_path, meta)
            for card_path, meta in docs
            if _is_allowed(meta, filters)
        ]

    if not docs:
        print("No pending documents to split, exiting...")
        return

    dest_dir = dest or get_lists_dir()
    os.makedirs(dest_dir, exist_ok=True)

    buckets = [[] for _ in range(parts)]
    for idx, (card_path, meta) in enumerate(docs):
        buckets[idx % parts].append((card_path, copy.deepcopy(meta)))

    total = len(docs)
    for i, bucket in enumerate(buckets, start=1):
        list_path = get_list_file_loc(f"{prefix}-{i}", lists_dir=dest_dir)
        subset = {card_path: meta for card_path, meta in bucket}
        dump_index(subset, index_file=list_path)
        print(f"Wrote {len(bucket)} docs to {list_path}")

    print(f"Split {total} pending doc(s) into {parts} list(s) under {dest_dir}")


def _load_filter():
    """
    Returns dict with 'codes' and 'titles' sets (lowercased), or None if no filter.json or empty filters.
    """
    filter_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "filter.json"))
    if not os.path.exists(filter_path):
        return None
    with open(filter_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    codes = {c.strip() for c in data.get("download_codes", [])}
    titles = {t.strip().lower() for t in data.get("titles", [])}
    if not codes and not titles:
        return None
    return {"download_codes": codes, "titles": titles}


def _is_allowed(meta, filters):
    if not filters:
        return True
    code = meta["download_code"]
    title = meta["title"]
    if code in filters['download_codes']:
        return True
    if title.strip().lower() in filters['titles']:
        return True
    return False
