"""Store pending record IDs in named Postgres worker selections."""

import copy

from rich import print

from .milli_kitaphana_utils import dump_index, get_list_file_loc, read_config, get_not_downloaded_docs, load_index_file


def split_lists(parts: int, dest: str = None, prefix: str = None):
    if parts < 1:
        raise ValueError("Parts must be greater than zero")

    index = load_index_file()
    docs = get_not_downloaded_docs(index, limited=False)

    filters = _load_filter()
    if filters:
        print(f"Loaded configured filter with {len(filters['download_codes'])} download_code(s) and {len(filters['titles'])} title(s)")
        docs = [
            (card_path, meta)
            for card_path, meta in docs
            if _is_allowed(meta, filters)
        ]

    if not docs:
        print("No pending documents to split, exiting...")
        return

    buckets = [[] for _ in range(parts)]
    for idx, (card_path, meta) in enumerate(docs):
        buckets[idx % parts].append((card_path, copy.deepcopy(meta)))

    total = len(docs)
    for i, bucket in enumerate(buckets, start=1):
        list_path = get_list_file_loc(f"{prefix or 'index-part'}-{i}")
        subset = {card_path: meta for card_path, meta in bucket}
        dump_index(subset, index_file=list_path)
        if dest:
            from pathlib import Path
            from .state import atomic_json
            atomic_json(Path(dest) / (list_path.removeprefix('selection:') + '.json'), subset)
        print(f"Stored {len(bucket)} docs in Postgres {list_path}")

    print(f"Split {total} pending doc(s) into {parts} Postgres selections")


def _load_filter():
    """
    Read an optional selection filter from the selected operational source settings.
    """
    data = read_config().get('split_filter', {})
    codes = {c.strip() for c in data.get("download_codes", [])}
    titles = {t.strip().lower() for t in data.get("titles", [])}
    if not codes and not titles:
        return None
    return {"download_codes": codes, "titles": titles}


def _is_allowed(meta, filters):
    if not filters:
        return True
    code = meta.get("download_code")
    title = meta.get("title")
    if code and code in filters['download_codes']:
        return True
    if isinstance(title, str) and title.strip().lower() in filters['titles']:
        return True
    return False
