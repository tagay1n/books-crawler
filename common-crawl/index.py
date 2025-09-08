import json
from datatrove.pipeline.readers import ParquetReader
import os
from utils import _get_index_file_loc, _load_index
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
        
    index_path = _get_index_file_loc()
    if os.path.exists(index_path):
        existing_index = _load_index()
    else:
        existing_index = {}
        
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
            
    with open(index_path, "w") as f:
        json.dump(existing_index, f, indent=4, ensure_ascii=False)    
          
    print(f"There are {len(existing_index)} docs in the index")
    
    
def _get_urls_to_sources(source, script):
    print(f"Reading file '{source}'")
    index = {}
    data_reader = ParquetReader(source) 
    for doc in data_reader():
        print(doc)
        index[doc.id] = {
            'url': doc.metadata['url'],
            'file_path': doc.metadata['file_path'],
            'offset': doc.metadata['offset'],
            'script': script
        }
        
    return index
