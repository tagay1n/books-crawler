"""Utilities for Litres workflows: config loading, SID authentication, Selenium driver setup, hashing, JSON writes, and workdir path helpers."""

import hashlib
import json
import os
import os.path
from pathlib import Path

import requests
import yaml


def get_in_workdir(file):
    """Return file in the current directory where script file is located"""
    return os.path.join(os.path.dirname(__file__), file)


def dump_json_atomic(data, path):
    """Write JSON through a temporary file so Ctrl+C cannot leave the target truncated."""
    tmp_path = f"{path}.tmp.{os.getpid()}"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


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
        "login": "REDACTED_LITRES_LOGIN",
        "password": "REDACTED_LITRES_PASSWORD",
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
    Create a Selenium driver and preload Litres SID as a browser cookie.
    """
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium import webdriver
    from webdriver_manager.chrome import ChromeDriverManager

    from consts import domain

    options = webdriver.ChromeOptions()
    options.headless = True
    options.add_argument("--headless")

    driver_path = _find_cached_chromedriver() or ChromeDriverManager().install()
    driver = webdriver.Chrome(service=ChromeService(driver_path), options=options)
    driver.get(domain)
    driver.add_cookie({"name": "SID", "value": get_sid(), "domain": ".litres.ru", "path": "/"})
    return driver


def _find_cached_chromedriver():
    candidates = sorted(Path.home().glob(".wdm/drivers/chromedriver/linux64/*/chromedriver-linux64/chromedriver"))
    if not candidates:
        return None
    return str(candidates[-1])


def get_hash(src):
    """
    get MD5 hash of the source text
    :param src: bytes to calculate hash
    :return: hex digest of the hash
    """
    return hashlib.md5(src.encode()).hexdigest()
