"""Merges a secondary index file into the main Milli Kitaphana index."""

from utils import load_index_file, dump_index
from rich import print


def merge_indexes(new_index_path):
    old_index = load_index_file()
    new_index = load_index_file(new_index_path)
    merged_index = _merge_indexes(new_index, old_index)
    dump_index(merged_index)
    

def _merge_indexes(new_index, old_index):
    _merged_index = {}
    _new_entries = 0
    for k, v in new_index.items():
        if k not in old_index:
            _new_entries += 1
            _merged_index[k] = v
        else:
            _merged_index[k] = old_index[k]
            _merged_index[k].update(v)
            
    for k, v in old_index.items():
        if k not in _merged_index:
            _merged_index[k] = v

    if _new_entries:
        print(f"[green]Added {_new_entries} new entries to the index.[/green]")

    return _merged_index