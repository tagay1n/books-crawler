"""Detached metadata projections and incremental updates for native adapters."""
from copy import deepcopy


def records(manifest, keys=None):
    stored = manifest.data['records']
    selected = stored if keys is None else keys
    return {key: deepcopy(stored[key]['observations'][-1]['metadata'])
            for key in selected if key in stored and stored[key].get('observations')}


def update_records(manifest, items, *, url_prefix=None, replace=False):
    """Apply metadata-only native records; the caller owns the checkpoint.

    Whole-index compatibility callers may replace the inventory. Hot paths pass
    only touched keys. Unchanged metadata retains its observation and timestamps.
    """
    stored = manifest.data['records']
    for key, item in items.items():
        metadata = item if url_prefix is None else {**item, 'url': item.get('url') or url_prefix + key}
        history = stored.get(key, {}).get('observations', [])
        if not history or history[-1]['metadata'] != metadata:
            manifest.observe(deepcopy(metadata), [], record_key=key, persist=False)
    if replace:
        for key in stored.keys() - items.keys():
            del stored[key]
