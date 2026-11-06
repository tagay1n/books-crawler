"""Resolve managed source directories consistently across all lifecycle stages."""
from pathlib import Path


def source_directory(settings, source):
    default = settings.artifacts_root / source
    if source not in {'common_crawl', 'milli_kitaphana'}:
        return default
    value = settings.source_options.get('artifact_dir')
    if not value:
        return default
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path(settings.source_options['_config_dir']) / path
