import os

def _get_index_file_loc(index_file_name = "docs-index.json"):
    index_dir = _get_in_workdir("../__artifacts/common.crawl")
    os.makedirs(index_dir, exist_ok=True)
    return os.path.join(index_dir, index_file_name)

def _get_in_workdir(file):
    """Return file in the current directory where script file is located"""
    return os.path.join(os.path.dirname(__file__), file)