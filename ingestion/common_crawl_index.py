"""Merge FinePDFs URL, WARC offset and script evidence into Postgres."""

from .common_crawl_utils import _runtime, _load_index, _dump_index
from .network import BudgetStop

cyrl_sources = [
    'hf://datasets/HuggingFaceFW/finepdfs/data/tat_Cyrl/test',
    'hf://datasets/HuggingFaceFW/finepdfs/data/tat_Cyrl/train',
]
lat_sources = ['hf://datasets/HuggingFaceFW/finepdfs/data/tat_Latn/train']


def index():
    from datatrove.pipeline.readers import ParquetReader

    runtime = _runtime()
    existing = _load_index()
    try:
        for source, script in [(s, 'cyrl') for s in cyrl_sources] + [(s, 'latn') for s in lat_sources]:
            runtime.budget.check()
            if runtime.summary['pages'] >= runtime.settings.max_pages:
                raise BudgetStop('dataset directory cap')
            for doc in ParquetReader(source)():
                runtime.budget.check()
                existing.setdefault(doc.id, {}).update(
                    upstream_metadata=dict(doc.metadata),
                    url=doc.metadata['url'], file_path=doc.metadata['file_path'],
                    offset=doc.metadata['offset'], script=script,
                )
            runtime.summary['pages'] += 1
            _dump_index(existing)
    finally:
        _dump_index(existing)
