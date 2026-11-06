"""Shared runtime and Postgres index access for Common Crawl helpers."""

from pathlib import Path

RUNTIME = None


def _runtime():
    if RUNTIME is None:
        raise RuntimeError('Run Common Crawl through the unified CLI')
    return RUNTIME


def _get_in_workdir(file):
    """Resolve temporary files under the selected artifact directory."""
    return str(_runtime().directory / file)


def _load_index():
    return _runtime().data['records']


def _dump_index(index):
    runtime = _runtime()
    runtime.data['records'] = index
    runtime.checkpoint(runtime.repository, runtime.data)


def configured_path(name):
    runtime = _runtime()
    path = Path(runtime.settings.source_options[name]).expanduser()
    return path if path.is_absolute() else Path(runtime.settings.source_options['_config_dir']) / path


def write_stream(stream, output_file):
    """Bound each local input and account for bytes, deadline and free disk."""
    from .core import check_space
    from .network import BudgetStop

    runtime = _runtime()
    size = 0
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb') as handle:
        while True:
            runtime.budget.check()
            chunk = stream.read(65536)
            if not chunk:
                break
            size += len(chunk)
            runtime.budget.bytes += len(chunk)
            if runtime.budget.bytes > runtime.settings.max_download_bytes:
                raise BudgetStop('download byte cap')
            if size > runtime.settings.max_file_bytes:
                raise ValueError('Common Crawl input exceeds max_file_bytes')
            check_space(path.parent, runtime.settings.disk_reserve_bytes, len(chunk))
            handle.write(chunk)
    return size
