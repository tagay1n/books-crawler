import os.path

import yaml
import requests

def get_in_workdir(file):
    """Return file in the current directory where script file is located"""
    return os.path.join(os.path.dirname(__file__), file)

def read_config():
    # read config file from the same directory
    with open(get_in_workdir("config.yaml"), "r") as f:
        return yaml.safe_load(f)

def get_sid():
    config = read_config()
    if 'sid' in config:
        return config['sid']
    auth_url = "https://api.litres.ru/foundation/api/auth/login"
    data = {
        "login": "rkharisov.main@gmail.com",
        "password": "wfh4d4x9",
    }
    auth_headers = {
        "app-id": read_config()['app-id'],
    }
    with requests.post(auth_url, json=data, headers=auth_headers) as r:
        r.raise_for_status()
        sid = r.json()['payload']['data']['sid']
        print(f"Requested new SID: {sid}, consider updating config")
        return sid
