"""Milli Kitaphana stages, reusing the original provider helpers."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from .state import Manifest, source_lock, now
from .network import HTTP, Budget, BudgetStop
from .core import file_digests, check_space

ARCHIVE_URL = 'https://kitap.tatar.ru/tt/ssearch/ecollection/'
SUPPORTED_COMMANDS = {'discover', 'download', 'finalize', 'run', 'status', 'publish', 'import-state', 'split', 'merge-index', 'recover', 'mark-existing-limited'}


def directory_for(settings):
    value = settings.source_options.get('artifact_dir')
    if not value:
        return settings.artifacts_root / 'milli_kitaphana'
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path(settings.source_options['_config_dir']) / path


class Runtime:
    def __init__(self, settings, manifest, summary):
        self.settings, self.manifest, self.summary = settings, manifest, summary
        self.directory = manifest.directory
        self.config = settings.source_options
        self.budget = Budget(settings)
        self.http = HTTP(settings, self.budget, summary)
        def guard(response, *args, **kwargs):
            from urllib.parse import urljoin, urlsplit
            if response.is_redirect and urlsplit(urljoin(response.url, response.headers['Location'])).hostname != 'kitap.tatar.ru':
                response.close()
                raise ValueError('Milli redirected outside its supported origin')
            return response
        self.http.session.hooks['response'].append(guard)
        self.offline = False
        self.selected = set()
        import threading
        self.network_lock = threading.RLock()
        self.state_lock = threading.RLock()

    def request(self, method, url, params=None, data=None, stream=False, headers=None, proxies=None, **kwargs):
        from urllib.parse import urlsplit
        import requests
        if self.offline:
            raise ValueError('Missing local input; run download before finalize')
        if urlsplit(url).hostname != 'kitap.tatar.ru':
            raise ValueError('Unsupported Milli resource origin')
        # Serialize provider worker requests so shared budgets and HTTP session remain coherent.
        with self.network_lock:
            if params:
                url = requests.Request('GET', url, params=params).prepare().url
            def fetch():
                with self.http.request(method, url, headers=headers, data=data) as response:
                    chunks, size = [], 0
                    for chunk in response.iter_content(65536):
                        self.budget.check()
                        size += len(chunk)
                        self.budget.bytes += len(chunk)
                        if size > self.settings.max_file_bytes or self.budget.bytes > self.settings.max_download_bytes:
                            raise BudgetStop('download byte cap')
                        check_space(self.directory, self.settings.disk_reserve_bytes, size)
                        chunks.append(chunk)
                    response._content = b''.join(chunks)
                    response._content_consumed = True
                    return response
            return self.http.retry(fetch)


def records(manifest):
    return {key: dict(r['observations'][-1]['metadata']) for key, r in manifest.data['records'].items() if r.get('observations')}


def execute(settings, command, *, recheck=False, log=print):
    if command not in SUPPORTED_COMMANDS:
        raise ValueError('Unsupported Milli stage')
    directory = directory_for(settings)
    manifest = Manifest(directory, 'milli_kitaphana')
    if command == 'status':
        items = records(manifest)
        return {**manifest.status(), 'acquired': sum(v.get('downloaded') == 'full' for v in items.values()),
                'finalized': sum(bool(v.get('finalized')) for v in items.values()),
                'publications': manifest.data.get('publications', {}), 'catalog': manifest.data.get('milli_catalog', {})}
    summary = dict(source='milli_kitaphana', command=command, id=uuid4().hex, started_at=now(), pages=0, downloaded=0, finalized=0, skipped=0, requests=0, network_retries=0, errors=[], stops=[])
    with source_lock(directory, 'milli_kitaphana'):
        manifest = Manifest(directory, 'milli_kitaphana')
        runtime = Runtime(settings, manifest, summary)
        from . import milli_kitaphana_utils as utils
        utils.RUNTIME = runtime
        items = records(manifest)
        def commit():
            for key, item in items.items():
                manifest.observe({**item, 'url': item.get('url') or 'https://kitap.tatar.ru' + key}, [], record_key=key, persist=False)
            manifest.save()
        started = False
        try:
            from . import milli_kitaphana_download as downloader, milli_kitaphana_decrypt as decrypt
            from . import milli_kitaphana_recover as recovery, milli_kitaphana_index as index
            with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                if command == 'import-state':
                    started = True
                    origin = Path(settings.source_options['_from'])
                    from .database_cli import read_import
                    imported, _, conflicts = read_import('milli_kitaphana', [origin / '_index/books-index.json'], processing_dir=origin)
                    if conflicts:
                        raise ValueError('Resolve import conflicts using database import preview')
                    incoming = {key:record['observations'][-1]['metadata'] for key,record in imported['records'].items()}
                    for name,value in imported.items():
                        if name.startswith(('selection:', 'recovery_evidence:')):
                            manifest.data.setdefault(name,value)
                    for name,value in imported.get('recovery_reports',{}).items():
                        manifest.data.setdefault('recovery_reports',{}).setdefault(name,value)
                    for key, item in incoming.items():
                        # Existing database state wins on repeat import.
                        items.setdefault(key, item)
                        current = items[key]
                        if current.get('decrypted') and not current.get('finalized') and current.get('download_code'):
                            candidates = list((origin / current['download_code']).glob('*.pdf'))
                            if len(candidates) == 1:
                                import pymupdf
                                try:
                                    with pymupdf.open(candidates[0]) as pdf:
                                        if pdf.page_count > 0:
                                            current['finalized'] = {'path': str(candidates[0]), 'sha256': file_digests(candidates[0])[0], 'legacy': True}
                                except (OSError, ValueError, RuntimeError):
                                    summary['skipped'] += 1
                    commit()
                else:
                    started = True
                    commit()
                    if command in {'discover', 'run'}:
                        try:
                            index.index()
                        except BudgetStop as error:
                            if command != 'run':
                                raise
                            summary['stops'].append(str(error))
                        items = utils.load_index_file()
                        commit()
                    if command in {'download', 'run'}:
                        try:
                            downloader.download(settings.source_options.get('_limited', False), settings.source_options.get('_index_name'), recheck=recheck)
                        except BudgetStop as error:
                            if command != 'run':
                                raise
                            summary['stops'].append(str(error))
                        items = utils.load_index_file()
                        commit()
                    if command in {'finalize', 'run'}:
                        runtime.offline = True
                        for key, item in items.items():
                            if (item.get('decrypted') or item.get('finalized')) and not recheck:
                                summary['skipped'] += 1
                                continue
                            if not item.get('enc_part_paths'):
                                if item.get('downloaded') == 'full' and not item.get('decrypted'):
                                    summary['awaiting_inputs'] = summary.get('awaiting_inputs', 0) + 1
                                previous = item.get('finalized', {})
                                if previous.get('path') and Path(previous['path']).is_file() and file_digests(Path(previous['path']))[0] == previous['sha256']:
                                    summary['skipped'] += 1
                                continue
                            inputs = []
                            for part in item['enc_part_paths']:
                                inputs.append(Path(part['enc_unzip_dir']) / 'enc.dat')
                            inputs.append(directory / item['download_code'] / 'part0_encrypted/enc.dat')
                            if not all(p.is_file() for p in inputs):
                                summary['awaiting_inputs'] = summary.get('awaiting_inputs', 0) + 1
                                continue
                            fingerprint = hashlib.sha256(json.dumps({'recipe': 1, 'inputs': [(str(p), file_digests(p)[0]) for p in inputs], 'title': item.get('title'), 'author': item.get('author')}, sort_keys=True).encode()).hexdigest()
                            previous = item.get('finalized', {})
                            if not recheck and previous.get('inputs') == fingerprint and Path(previous['path']).is_file() and file_digests(Path(previous['path']))[0] == previous['sha256']:
                                summary['skipped'] += 1
                                continue
                            if command != 'run' or key not in runtime.selected:
                                runtime.budget.start_item()
                            runtime.budget.check()
                            context = {'meta': item, 'config': runtime.config, 'work_dir': str(directory / item['download_code'])}
                            from .milli_kitaphana_progress_wrapper import ProgressWrapper
                            with ProgressWrapper(context, key):
                                output = Path(decrypt.decrypt_doc_parts(context))
                            if output.stat().st_size > settings.max_derived_pdf_bytes:
                                raise ValueError('Derived PDF exceeds configured size limit')
                            item['finalized'] = {'path': str(output), 'sha256': file_digests(output)[0], 'inputs': fingerprint}
                            summary['finalized'] += 1
                            commit()
                        runtime.offline = False
                    if command == 'publish':
                        if runtime.config.get('_target') != 'yandex':
                            raise ValueError('Milli supports only --target yandex')
                        from .milli_kitaphana_upload_docs import upload_doc, persist_upstream_metadata
                        if runtime.config.get('database_url') in (None, '', '<SET ME>') or runtime.config.get('yandex', {}).get('disk', {}).get('oauth_token') in (None, '', '<SET ME>'):
                            raise ValueError('Configure Milli database_url and yandex.disk.oauth_token')
                        publication = manifest.data.setdefault('publications', {})
                        for key, item in items.items():
                            output = item.get('finalized')
                            if not output or not Path(output['path']).is_file() or file_digests(Path(output['path']))[0] != output['sha256']:
                                continue
                            runtime.budget.start_item()
                            steps = publication.setdefault(key, {})
                            if steps.get('sha256') != output['sha256']:
                                steps.clear(); steps['sha256'] = output['sha256']
                            if not steps.get('yandex'):
                                upload_doc(output['path'], runtime.config, item.get('downloaded') == 'limited')
                                steps['yandex'] = now(); manifest.save()
                            if not steps.get('metadata'):
                                persist_upstream_metadata(decrypt._calculate_md5(output['path']), decrypt._upstream_metadata(item), runtime.config['database_url'])
                                steps['metadata'] = now(); manifest.save()
                            item['decrypted'] = True
                            commit()
                    options = runtime.config.get('_maintenance', {})
                    if command == 'split':
                        from .milli_kitaphana_split_index import split_lists
                        split_lists(**options)
                    elif command == 'merge-index':
                        from .milli_kitaphana_merge_index import merge_indexes
                        merge_indexes(options['path']); items = utils.load_index_file()
                    elif command == 'recover':
                        recovery.recover(**options); items = utils.load_index_file()
                    elif command == 'mark-existing-limited':
                        from .milli_kitaphana_mark_existing_limited import mark_existing_limited
                        mark_existing_limited(); items = utils.load_index_file()
        except BudgetStop as error:
            summary['stops'].append(str(error))
        except Exception as error:
            message = str(error)
            for value in (runtime.config.get('database_url'), runtime.config.get('priv_key'), runtime.config.get('yandex', {}).get('disk', {}).get('oauth_token')):
                if value: message = message.replace(str(value), '[redacted]')
            summary['errors'].append({'stage': command, 'error': message})
        finally:
            # Helpers checkpoint their own updates, including partial progress.
            if started and command in {'discover', 'download', 'run', 'recover', 'merge-index', 'mark-existing-limited'}:
                items = utils.load_index_file()
            if started:
                commit()
            runtime.http.close()
            utils.RUNTIME = None
            summary.update(records=len(items), finished_at=now(), attempted_download_bytes=runtime.budget.bytes, started_items=runtime.budget.items)
            summary['state_key'] = 'last_run'
            if started:
                manifest.data['last_run'] = summary
                manifest.save()
    return summary
