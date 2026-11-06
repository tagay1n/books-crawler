"""Helpers for locating, loading, and writing the Common Crawl index."""

import os

def _get_in_workdir(file):
    """Return file in the current directory where script file is located"""
    return os.path.join(os.path.dirname(__file__), file)

def _repository():
    import sys
    from pathlib import Path
    root = str(Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)
    from ingestion.postgres_state import Repository
    return Repository('common_crawl')


def _load_index():
    return _repository().load()['records']


def _dump_index(index):
    repository = _repository()
    data = repository.load()
    data['records'] = index
    repository.save(data)
