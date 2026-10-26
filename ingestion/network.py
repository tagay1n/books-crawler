import time

import requests
from urllib3.exceptions import HTTPError as TransportError


class BudgetStop(Exception):
    """An intentional boundary; unstarted or incomplete work stays eligible."""


class InvalidDocument(ValueError):
    pass


class Budget:
    def __init__(self, settings):
        self.settings = settings
        self.deadline = time.monotonic() + settings.soft_deadline_seconds
        self.bytes = 0
        self.items = 0

    def check(self):
        if time.monotonic() >= self.deadline:
            raise BudgetStop("soft deadline")

    def wait(self, seconds):
        self.check()
        if seconds >= self.deadline - time.monotonic():
            raise BudgetStop("soft deadline")
        time.sleep(seconds)

    def start_item(self):
        self.check()
        if self.items >= self.settings.max_items:
            raise BudgetStop("download item cap")
        if self.bytes >= self.settings.max_download_bytes:
            raise BudgetStop("download byte cap")
        self.items += 1


class HTTP:
    def __init__(self, settings, budget, summary):
        self.settings, self.budget, self.summary = settings, budget, summary
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "BooksCrawler/1.0 (local document acquisition)",
                                     "Accept-Encoding": "identity"})
        self.last_request = None

    def close(self):
        self.session.close()

    def get(self, url, headers=None):
        self.budget.check()
        if self.last_request is not None:
            self.budget.wait(max(0, self.settings.pacing_seconds - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        remaining = max(0.001, self.budget.deadline - self.last_request)
        self.summary["requests"] += 1
        response = self.session.get(url, stream=True, headers=headers or {}, timeout=(
            min(remaining, self.settings.connect_timeout_seconds), min(remaining, self.settings.read_timeout_seconds)))
        try:
            response.raise_for_status()
        except requests.RequestException:
            response.close()
            raise
        return response

    def retry(self, operation):
        for attempt in range(self.settings.retry_attempts):
            self.budget.check()
            try:
                return operation()
            except (requests.RequestException, TransportError) as error:
                response = getattr(error, "response", None)
                status = response.status_code if response is not None else None
                retryable = status is None or status in {408, 429, 500, 502, 503, 504}
                if not retryable or attempt + 1 == self.settings.retry_attempts:
                    raise
                delay = 2 ** attempt
                if response is not None:
                    hint = response.headers.get("Retry-After", "")
                    if hint.isdecimal():
                        delay = max(delay, min(int(hint), 60))
                self.summary["network_retries"] += 1
                self.budget.wait(delay)

    def text(self, url):
        def fetch():
            with self.get(url) as response:
                chunks, size = [], 0
                while True:
                    self.budget.check()
                    chunk = response.raw.read(min(65536, 2 * 1024 * 1024 + 1 - size), decode_content=True)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > 2 * 1024 * 1024:
                        raise ValueError(f"HTML page exceeds the 2 MiB inspection limit: {url}")
                    chunks.append(chunk)
                return b"".join(chunks).decode("utf-8", errors="replace")
        return self.retry(fetch)
