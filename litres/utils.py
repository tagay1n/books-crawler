"""Utilities for Litres workflows: config loading, SID authentication, Selenium driver setup, hashing, JSON writes, and workdir path helpers."""

import hashlib
import json
import os
import os.path
from pathlib import Path

import yaml
import requests as native_requests
from contextvars import ContextVar

RUNTIME = ContextVar("litres_runtime", default=None)


class RequestsProxy:
    def __getattr__(self, name):
        runtime = RUNTIME.get()
        if runtime and name == "get":
            return runtime.get
        if runtime and name == "Session":
            return runtime.session
        return getattr(native_requests, name)


requests = RequestsProxy()


def get_in_workdir(file):
    """Return file in the current directory where script file is located"""
    runtime = RUNTIME.get()
    if runtime is not None and file.startswith("../__artifacts/litres"):
        return str(runtime.directory / file.removeprefix("../__artifacts/litres").lstrip("/"))
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
    if RUNTIME.get() is not None:
        return RUNTIME.get().config
    # read config file from the same directory
    with open(get_in_workdir("config.yaml"), "r") as f:
        return yaml.safe_load(f)


def get_sid():
    config = read_config()
    if (sid := config.get('sid')) and sid != "<SET ME>":
        return sid
    raise ValueError("sid is not set in litres/config.yaml")


def create_driver(headless=True):
    runtime = RUNTIME.get()
    if runtime is not None:
        runtime.budget.check()
        if runtime.offline:
            raise ValueError("Browser access is unavailable during offline finalization")
    """
    Create a Selenium driver and preload Litres SID as a browser cookie.
    """
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium import webdriver
    from webdriver_manager.chrome import ChromeDriverManager

    from .consts import domain

    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver_path = _find_cached_chromedriver() or ChromeDriverManager().install()
    driver = webdriver.Chrome(service=ChromeService(driver_path), options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"},
    )
    if runtime is not None:
        driver.set_page_load_timeout(min(runtime.settings.read_timeout_seconds, max(1, runtime.budget.deadline - __import__("time").monotonic())))
        runtime.drivers.append(driver)
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
