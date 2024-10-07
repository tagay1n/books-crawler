import os.path

import requests
import yaml
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from seleniumwire import webdriver
import hashlib

def get_in_workdir(file):
    """Return file in the current directory where script file is located"""
    return os.path.join(os.path.dirname(__file__), file)


def read_config():
    # read config file from the same directory
    with open(get_in_workdir("config.yaml"), "r") as f:
        return yaml.safe_load(f)


def get_sid():
    config = read_config()
    if sid := config.get('sid'):
        return sid
    auth_url = "https://api.litres.ru/foundation/api/auth/login"
    data = {
        "login": "rkharisov.main@gmail.com",
        "password": "wfh4d4x9",
    }
    if not (app_id := config['app-id']):
        raise ValueError("app-id is not set in config")
    auth_headers = {
        "app-id": app_id,
    }
    with requests.post(auth_url, json=data, headers=auth_headers) as r:
        r.raise_for_status()
        sid = r.json()['payload']['data']['sid']
        print(f"Requested new SID: {sid}, consider updating config")
        return sid

def create_driver():
    """
    Create a new Selenium driver instance with request interceptor
    """

    def _interceptor(request):
        # add the missing headers
        request.headers['Cookie'] = f"SID={get_sid()};"

    options = webdriver.ChromeOptions()
    options.headless = True
    options.add_argument("--headless")

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options
    )
    driver.request_interceptor = _interceptor
    return driver

def get_hash(src):
    """
    get MD5 hash of the source text
    :param src: bytes to calculate hash
    :return: hex digest of the hash
    """
    return hashlib.md5(src.encode()).hexdigest()