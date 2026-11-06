"""Builds or refreshes the Common Crawl PDF index by reading parquet datasets and merging URL, offset, and script metadata into a local JSON file."""

from datatrove.pipeline.readers import ParquetReader
from utils import _load_index, _dump_index
from rich import print

cyrl_sources = [
    "hf://datasets/HuggingFaceFW/finepdfs/data/tat_Cyrl/test",
    "hf://datasets/HuggingFaceFW/finepdfs/data/tat_Cyrl/train"
]

lat_sources = [
    "hf://datasets/HuggingFaceFW/finepdfs/data/tat_Latn/train"
]

def index(): 
    print("Indexing")
    index = {}
    for s in cyrl_sources:
        index.update(_get_urls_to_sources(s, "cyrl"))
        
    for s in lat_sources:
        index.update(_get_urls_to_sources(s, "latn"))
        
    existing_index = _load_index()

    for id, value in index.items():
        if id in existing_index:
            _existing_value =  existing_index[id]
            _existing_value['url'] = value['url']
            _existing_value['file_path'] = value['file_path']
            _existing_value['script'] = value['script']
            _existing_value['offset'] = value['offset']
            
            existing_index[id] = _existing_value
        else:
            existing_index[id] = value
            
    _dump_index(existing_index)

    print(f"There are {len(existing_index)} docs in the index")
    
    
def _get_urls_to_sources(source, script):
    print(f"Reading file '{source}'")
    index = {}
    data_reader = ParquetReader(source) 
    for doc in data_reader():
        index[doc.id] = {
            'url': doc.metadata['url'],
            'file_path': doc.metadata['file_path'],
            'offset': doc.metadata['offset'],
            'script': script
        }
        
    return index
