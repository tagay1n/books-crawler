"""Credential-free, line-oriented progress for the Milli pipeline."""
import json
import math
from pathlib import Path
import threading
import time
import traceback

from requests import HTTPError

from .state import now


def error_fields(error):
    fields = {'error': type(error).__name__}
    frames = traceback.extract_tb(error.__traceback__)
    if frames:
        fields['stack'] = [f'{Path(frame.filename).name}:{frame.lineno}:{frame.name}'
                           for frame in frames[-5:]]
    response = getattr(error, 'response', None)
    if isinstance(response, dict):
        fields['http_status'] = response.get('ResponseMetadata', {}).get('HTTPStatusCode')
        code = str(response.get('Error', {}).get('Code', ''))
        if code and len(code) <= 64 and code.replace('_', '').isalnum():
            fields['error_code'] = code
    elif response is not None:
        fields['http_status'] = response.status_code
    return {key: value for key, value in fields.items() if value is not None}


def provider_failure(runtime, stage, error, **fields):
    """Keep exhausted provider 5xx requests visible without failing the run."""
    details = error_fields(error)
    deferred = isinstance(error, HTTPError) and 500 <= details.get('http_status', 0) < 600
    failure = {'stage': stage, **fields, **details}
    if deferred:
        failure['retryable'] = True
    runtime.summary.setdefault('warnings' if deferred else 'errors', []).append(failure)
    runtime.event(f"{stage}_{'deferred' if deferred else 'failed'}",
                  **{key: value for key, value in failure.items() if key != 'stage'})


class Progress:
    def __init__(self, log, summary, settings):
        self.log, self.summary, self.settings = log, summary, settings
        self.started = time.monotonic()
        self.stage = 'startup'
        self.stopped = threading.Event()
        self.mutex = threading.Lock()

    def emit(self, event, **fields):
        fields = {key: ('unlimited' if isinstance(value, float) and math.isinf(value) else value)
                  for key, value in fields.items()}
        with self.mutex:
            self.log(json.dumps({'time': now(), 'source': 'milli_kitaphana',
                                 'run_id': self.summary['id'], 'stage': self.stage,
                                 'event': event, **fields}, ensure_ascii=False, allow_nan=False))

    def phase(self, stage):
        self.emit('stage_finished')
        self.stage = stage
        self.emit('stage_started')

    def counters(self):
        return {key: self.summary.get(key, 0) for key in (
            'pages', 'requests', 'network_retries', 'downloaded', 'finalized',
            'limited_skipped', 'duplicates', 's3_published', 'yandex_published',
            'catalog_registered')}

    def heartbeat(self):
        while not self.stopped.wait(30):
            self.emit('heartbeat', elapsed_seconds=round(time.monotonic() - self.started),
                      **self.counters())

    def __enter__(self):
        self.emit('run_started', command=self.summary['command'],
                  max_pages=self.settings.max_pages, max_items=self.settings.max_items,
                  max_download_bytes=self.settings.max_download_bytes,
                  soft_deadline_seconds=self.settings.soft_deadline_seconds)
        self.thread = threading.Thread(target=self.heartbeat, name='milli-progress', daemon=True)
        self.thread.start()
        return self

    def __exit__(self, kind, error, traceback):
        self.stopped.set()
        self.thread.join(timeout=1)
        self.emit('run_finished', elapsed_seconds=round(time.monotonic() - self.started),
                  error_count=len(self.summary['errors']) + int(error is not None),
                  warning_count=len(self.summary.get('warnings', [])),
                  stops=self.summary['stops'], **self.counters(),
                  **(error_fields(error) if error is not None else {}))
