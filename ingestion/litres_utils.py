"""Utilities for Litres workflows: config loading, SID authentication, Selenium driver setup, hashing, JSON writes, and workdir path helpers."""

import hashlib
from pathlib import Path

import requests as native_requests
from contextvars import ContextVar

RUNTIME = ContextVar("litres_runtime", default=None)


class RequestsProxy:
    def __getattr__(self, name):
        runtime = require_runtime()
        if name == "get":
            return runtime.get
        if name == "Session":
            return runtime.session
        return getattr(native_requests, name)


requests = RequestsProxy()


def require_runtime():
    runtime = RUNTIME.get()
    if runtime is None:
        raise RuntimeError("Litres helpers require the unified ingestion runtime")
    return runtime


def get_in_workdir(file):
    """Resolve a provider artifact path beneath the selected source directory."""
    directory = require_runtime().directory.resolve()
    path = (directory / file).resolve()
    if not path.is_relative_to(directory):
        raise ValueError("Litres artifact path escapes the selected source directory")
    return str(path)


def dump_json_atomic(data, path):
    """Reuse the shared atomic checkpoint writer."""
    from .state import atomic_json
    atomic_json(Path(path), data)


def read_config():
    return require_runtime().config


def get_sid():
    config = read_config()
    if (sid := config.get('sid')) and sid != "<SET ME>":
        return sid
    raise ValueError("sid is not set in sources.litres in the selected operational YAML")


def create_driver(headless=True):
    """Create a Selenium driver using the active shared runtime and SID."""
    runtime = require_runtime()
    if runtime is not None:
        runtime.budget.check()
        if runtime.offline:
            raise ValueError("Browser access is unavailable during offline finalization")
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium import webdriver
    from webdriver_manager.chrome import ChromeDriverManager

    from .litres_consts import domain

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
