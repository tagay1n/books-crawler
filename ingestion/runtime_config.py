"""Invocation-local operational configuration shared by adapter helpers."""
from contextvars import ContextVar
from functools import wraps

_settings = ContextVar('ingestion_settings')


def configured(function):
    @wraps(function)
    def invoke(settings, *args, **kwargs):
        token = _settings.set(settings)
        try:
            return function(settings, *args, **kwargs)
        finally:
            _settings.reset(token)
    return invoke


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
