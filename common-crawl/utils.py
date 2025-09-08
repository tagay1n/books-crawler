import os
import json
import datetime

def _get_index_file_loc(index_file_name = "docs-index.json"):
    index_dir = _get_in_workdir("../__artifacts/common.crawl")
    os.makedirs(index_dir, exist_ok=True)
    return os.path.join(index_dir, index_file_name)

def _get_in_workdir(file):
    """Return file in the current directory where script file is located"""
    return os.path.join(os.path.dirname(__file__), file)

def _load_index():
    index_path = _get_index_file_loc()
    if not os.path.exists(index_path):
        raise ValueError(f"Index file not found by path {index_path}")
    with open(index_path, "r") as f:
        return json.load(f)
    
        
def _dump_index(index, backup=False):
    index_path = _get_index_file_loc()
    if backup:
        current_time = datetime.datetime.now()
        formatted_time = current_time.strftime('%H:%M:%S')
        index_path = f"{index_path}_{formatted_time}.backup"
    with open(index_path, "w") as f:
        return json.dump(index, f, indent=4, ensure_ascii=False)            
    