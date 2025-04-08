import os.path
import yaml
import json


index_file_name = "books-index.json"

def get_in_workdir(file):
    """Return file in the current directory where script file is located"""
    return os.path.join(os.path.dirname(__file__), file)


def read_config():
    # read config file from the same directory
    with open(get_in_workdir("config.yaml"), "r") as f:
        return yaml.safe_load(f)
    
def load_index_file():
    index_file = get_index_file_loc()
    if os.path.exists(index_file):
        with open(index_file, "r") as f:
            books = json.load(f)
    else:
        books = {}
    return books
        
def get_index_file_loc():
    index_dir = get_in_workdir("../__artifacts/milli.kitaphana")
    os.makedirs(index_dir, exist_ok=True)
    return os.path.join(index_dir, index_file_name)


def dump_index(idx):
    index_file = get_index_file_loc()
    with open(index_file, "w") as f:
        json.dump(idx, f, ensure_ascii=False, indent=4)
    