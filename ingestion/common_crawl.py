"""Common Crawl/FinePDFs stages backed by the existing Postgres index."""

import contextlib
import os
from pathlib import Path
from uuid import uuid4

from .database import source_lock
from .network import Budget, BudgetStop, HTTP
from .postgres_state import Repository
from .state import now

ARCHIVE_URL = 'https://huggingface.co/datasets/HuggingFaceFW/finepdfs'
SUPPORTED_COMMANDS = {'discover', 'download', 'run', 'status', 'publish'}


def counts(data):
    records = list(data['records'].values())
    return dict(records=len(records), acquired=sum(bool(r.get('path_to_file') or r.get('uploaded')) for r in records),
                publications=sum(bool(r.get('uploaded')) for r in records))


class Runtime:
    def __init__(self, settings, repository, data, summary, options, checkpoint):
        self.options, self.checkpoint = options, checkpoint
        self.settings, self.repository, self.data, self.summary = settings, repository, data, summary
        value = Path(settings.source_options.get('artifact_dir', settings.artifacts_root / 'common_crawl')).expanduser()
        self.directory = value if value.is_absolute() else Path(settings.source_options['_config_dir']) / value
        self.budget = Budget(settings)
        self.http = HTTP(settings, self.budget, summary)


def execute(settings, command, *, recheck=False, log=print, options=None, checkpoint=None):
    from .commands import CommandOptions, validate
    options = options or CommandOptions(recheck=recheck)
    validate("common_crawl", command, options)
    if recheck:
        raise ValueError('Common Crawl does not support --recheck')
    from .checkpoints import Checkpoint
    checkpoint = checkpoint or Checkpoint()
    config = settings.source_options
    if command == 'publish':
        if options.target != 'yandex':
            raise ValueError('Common Crawl supports only --target yandex')
        if config.get('yandex', {}).get('disk', {}).get('oauth_token') in (None, '', '<SET ME>', '<<set me>>'):
            raise ValueError('Configure sources.common_crawl.yandex.disk.oauth_token')
    if command == 'status':
        data = Repository('common_crawl').load()
        return dict(source='common_crawl', **counts(data), last_run=data.get('last_run'))
    summary = dict(source='common_crawl', command=command, id=uuid4().hex, started_at=now(),
                   pages=0, downloaded=0, published=0, skipped=0, requests=0, network_retries=0, errors=[], stops=[])
    with source_lock('common_crawl'):
        repository = Repository('common_crawl')
        data = repository.load()
        runtime = Runtime(settings, repository, data, summary, options, checkpoint)
        from . import common_crawl_utils as utils
        utils.RUNTIME = runtime
        try:
            runtime.directory.mkdir(parents=True, exist_ok=True)
            # Provider libraries print progress; the shared CLI emits the structured result.
            with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                if command in {'discover', 'run'}:
                    from .common_crawl_index import index
                    index()
                if command in {'download', 'run'}:
                    from .common_crawl_download import download
                    download()
                if command == 'publish':
                    from .common_crawl_upload import upload
                    upload()
        except BudgetStop as error:
            summary['stops'].append(str(error))
        except Exception as error:
            message = str(error)
            token = config.get('yandex', {}).get('disk', {}).get('oauth_token')
            if token:
                message = message.replace(str(token), '[redacted]')
            summary['errors'].append({'stage': command, 'error': message})
        finally:
            runtime.http.close()
            utils.RUNTIME = None
            summary.update(counts(data), finished_at=now(), attempted_download_bytes=runtime.budget.bytes,
                           started_items=runtime.budget.items, state_key='last_run')
            data['last_run'] = summary
            checkpoint(repository, data)
    return summary
