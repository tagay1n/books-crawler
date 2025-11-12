import os.path
import yaml
import json
import shutil
import requests
import zipfile


def get_in_workdir(file):
    """Return file in the current directory where script file is located"""
    return os.path.join(os.path.dirname(__file__), file)


index_file_name = "books-index.json"
HOST = "https://kitap.tatar.ru"
base_dir = get_in_workdir(os.path.join("../__artifacts/milli.kitaphana"))


def read_config():
    # read config file from the same directory
    with open(get_in_workdir("config.yaml"), "r") as f:
        return yaml.safe_load(f)
    
    
def load_index_file(index_file=None):
    if not index_file:
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
    tmp_file = f"{index_file}.part"
    with open(tmp_file, "w") as f:
        json.dump(idx, f, ensure_ascii=False, indent=4)
    shutil.move(tmp_file, index_file)
    
    
def download_part(context, part):
    work_dir = context["work_dir"]
    part_name, _ = part.split(".")
    enc_zip_path = os.path.join(work_dir, part_name + "_encrypted.zip")
    enc_unzip_dir = os.path.join(work_dir, part_name + "_encrypted")

    url = HOST + context['meta']["format_url"].format(url=part)
    # download the encrypted zip file
    with request(method="GET", url=url, stream=True) as response:
        os.makedirs(work_dir, exist_ok=True)
        # save the encrypted zip file
        with open(enc_zip_path, "wb") as enc_zip:
            task = context["progress"].download(part)
            total_size = 0
            for chunk in response.iter_content(chunk_size=1024):
                enc_zip.write(chunk)
                chunk_len = len(chunk)
                total_size += chunk_len
                context['progress']._aux.update(task, advance=chunk_len)
            context['progress']._aux.update(
                task, description=f"Downloaded {part}")
            context['progress']._aux.stop_task(task)

    # unzip the encrypted zip file
    with zipfile.ZipFile(enc_zip_path, 'r') as enc_zip:
        enc_zip.extractall(enc_unzip_dir)

    return enc_unzip_dir


def request(method, url, params=None, data=None, stream=False, attempts=10):
    resp = requests.request(
        method=method,
        url=url,
        params=params,
        verify=False,
        data=data,
        stream=stream,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
        }
    )
    resp.raise_for_status()
    return resp
