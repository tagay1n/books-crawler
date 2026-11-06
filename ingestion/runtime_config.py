"""Invocation-local operational configuration shared by adapter helpers."""
from contextvars import ContextVar
from functools import wraps
import time
from contextlib import contextmanager

_settings = ContextVar('ingestion_settings')
_deadlines = ContextVar('ingestion_deadlines', default=None)
_discovery_deadline = ContextVar('discovery_deadline', default=None)


def configured(function):
    @wraps(function)
    def invoke(settings, *args, **kwargs):
        token = _settings.set(settings)
        started = time.monotonic()
        deadline_token = _deadlines.set((started + settings.soft_deadline_seconds,
                                        started + settings.soft_deadline_seconds + settings.publication_grace_seconds))
        try:
            return function(settings, *args, **kwargs)
        finally:
            _settings.reset(token)
            _deadlines.reset(deadline_token)
    return invoke


@contextmanager
def discovery_window(settings):
    """Leave time for acquisition even when the catalog scan cannot finish."""
    deadline = (time.monotonic() + settings.discovery_deadline_seconds
                if settings.discovery_deadline_seconds is not None else None)
    token = _discovery_deadline.set(deadline)
    try:
        yield
    finally:
        _discovery_deadline.reset(token)


def option(module, key):
    try:
        settings = _settings.get()
    except LookupError:
        raise ValueError(f'Operational setting {module}.{key} requires an ingestion runtime') from None
    source = settings.source_options['_source']
    if key == 'archive_url' and module == source:
        return settings.archive_url
    try:
        return settings.source_options['operational'][module][key]
    except KeyError:
        raise ValueError(f'Missing sources.{source}.operational.{module}.{key} configuration') from None


def context_call(function, *args, **kwargs):
    """Capture the submitting invocation for work executed on a helper thread."""
    from contextvars import copy_context
    from functools import partial
    return partial(copy_context().run, function, *args, **kwargs)


from concurrent.futures import ThreadPoolExecutor


class ConfiguredThreadPoolExecutor(ThreadPoolExecutor):
    def submit(self, function, /, *args, **kwargs):
        return super().submit(context_call(function, *args, **kwargs))
