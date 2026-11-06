"""Litres implementation of the shared local and publication stages."""
import contextlib
import hashlib
import os
import json
import shutil
from pathlib import Path
from urllib.parse import urlsplit, urljoin
from uuid import uuid4

from .network import Budget, BudgetStop, HTTP, SourceAccessError
from .state import Manifest, atomic_json, now, source_lock
from .core import check_space, file_digests

ARCHIVE_URL = 'https://www.litres.ru/new/?art_types=text_book&languages=tt&only_litres_subscription_arts=true'
SUPPORTED_COMMANDS = {'discover', 'download', 'run', 'status', 'finalize', 'metadata', 'review', 'publish', 'import-state'}


class Session:
    def __init__(self, runtime):
        self.runtime = runtime
        self.headers = {}
    def get(self, url, **kwargs):
        kwargs['headers'] = {**self.headers, **kwargs.get('headers', {})}
        return self.runtime.get(url, **kwargs)
    def close(self):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()


class Runtime:
    def __init__(self, settings, manifest, summary):
        self.settings, self.manifest, self.summary = settings, manifest, summary
        self.directory = manifest.directory
        self.config = settings.source_options
        self.budget = Budget(settings)
        self.http = HTTP(settings, self.budget, summary)
        def guard(response, *args, **kwargs):
            if response.is_redirect and urlsplit(urljoin(response.url, response.headers.get("Location", ""))).hostname not in {"www.litres.ru", "litres.ru"}:
                response.close()
                raise SourceAccessError("Litres redirected outside its supported origin")
            return response
        self.http.session.hooks["response"].append(guard)
        self.drivers = []
        self.offline = False
    def session(self):
        return Session(self)
    def get(self, url, **kwargs):
        if self.offline:
            raise ValueError('Finalization requires a missing input; run download first')
        if urlsplit(url).hostname not in {'www.litres.ru', 'litres.ru'}:
            raise ValueError('Litres resource is outside the supported origin')
        sid = self.config.get('sid')
        if not isinstance(sid, str) or not sid.strip() or sid == '<SET ME>':
            raise ValueError('Set sources.litres.sid in the selected operational YAML')
        def fetch():
            response = self.http.request('GET', url, headers={**kwargs.get('headers', {}), 'Cookie': f'SID={sid};'}, check_status=False)
            try:
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
                if '/auth/login/' in response.url:
                    raise SourceAccessError('Litres rejected SID; update sources.litres.sid')
                if response.status_code in {408, 429, 500, 502, 503, 504}:
                    response.raise_for_status()
                return response
            finally:
                response.close()
        return self.http.retry(fetch)
    def close(self):
        for driver in self.drivers:
            with contextlib.suppress(Exception):
                driver.quit()
        self.http.close()


def books(manifest):
    return {key: dict(record['observations'][-1]['metadata']) for key, record in manifest.data['records'].items() if record.get('observations')}


def commit(runtime, items):
    for key, book in items.items():
        runtime.manifest.observe(book, [], record_key=key, persist=False)
    runtime.manifest.save()
    atomic_json(runtime.directory / 'books-index.json', items)


def discover(runtime, items):
    from . import litres_index as index
    mode = runtime.config.get('_mode', 'catalog')
    if mode in {'catalog', 'all'}:
        scan = runtime.manifest.data.setdefault('litres_catalog', {'next_page': 1, 'complete': False})
        if scan['complete']:
            scan.update(next_page=1, complete=False, batches=[])
        resolver = index._ReaderContentTypeResolver()
        try:
            for _ in range(runtime.settings.max_pages):
                page = scan['next_page']
                url = f'{ARCHIVE_URL}&page={page}'
                response = runtime.get(url)
                response.raise_for_status()
                index._raise_if_blocked(response.text, url)
                parsed = index._parse_books(index.bs.BeautifulSoup(response.text, 'html.parser'))
                if not parsed:
                    raise ValueError('Catalog cards missing; cannot establish catalog completion')
                fingerprint = hashlib.sha256(json.dumps([b['url'] for b in parsed]).encode()).hexdigest()
                if fingerprint in scan.setdefault('batches', []):
                    raise ValueError('Repeated Litres catalog page')
                for book in parsed:
                    key = index.get_hash(book['url'])
                    items[key] = index._merge_book_details(items.get(key, {}), book, resolver)
                    commit(runtime, items)
                scan['batches'].append(fingerprint)
                scan['next_page'] += 1
                # Use explicit native next-page evidence, never the legacy fixed page count.
                soup = index.bs.BeautifulSoup(response.text, 'html.parser')
                next_page = any(f'page={page + 1}' in a.get('href', '') for a in soup.select('a[href]'))
                scan['complete'] = not next_page
                runtime.summary['pages'] += 1
                runtime.manifest.save()
                if scan['complete']:
                    break
            if not scan['complete']:
                runtime.summary['stops'].append('discovery page cap')
        finally:
            resolver.close()
    if mode in {'candidates', 'all'}:
        from .litres_discover import discover_candidates
        discover_candidates()


def media_nodes(value):
    if isinstance(value, dict):
        if value.get('t') == 'img':
            yield value
        for child in value.values():
            yield from media_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from media_nodes(child)


def acquire(runtime, items, recheck):
    from . import litres_pdf as pdf, litres_text as text, litres_utils as utils
    selected = []
    for key, book in items.items():
        if runtime.config.get('_format', 'all') not in {'all', book.get('content_type')}:
            continue
        if book.get('acquired') and not recheck and inputs_valid(book):
            runtime.summary['skipped'] += 1
            if len(selected) < runtime.settings.max_items:
                selected.append(key)
            continue
        runtime.budget.start_item()
        try:
            if book['content_type'] == 'pdf':
                if recheck:
                    shutil.rmtree(runtime.directory / 'images' / str(book.get('file_id', 'missing')), ignore_errors=True)
                with utils.create_driver(headless=pdf._get_pdf_browser_headless()) as driver:
                    session = runtime.session()
                    book['file_id'] = pdf._get_file_id(book['url'], session=session, driver=driver)
                    book['ext'] = pdf._get_page_extensions(book['file_id'], session=session, driver=driver)
                    pdf.download_page_images(book['file_id'], book['ext'], session=session, driver=driver, book_page_url=book['url'])
                paths = list((runtime.directory / 'images' / str(book['file_id'])).glob('*.png'))
                if len(paths) != len(book['ext']['pages'][0]['p']):
                    raise ValueError('PDF image inventory is incomplete')
            elif book['content_type'] == 'text':
                if recheck:
                    shutil.rmtree(runtime.directory / 'js' / key, ignore_errors=True)
                with utils.create_driver() as driver:
                    folder = Path(text._download_page_descriptions(book, driver))
                    decoded = []
                    for path in sorted(folder.glob('*.js')):
                        decoded.append(driver.execute_script('let c = ' + path.read_text() + '; return c;'))
                if not decoded:
                    raise ValueError('Empty text input')
                output = runtime.directory / 'markdown' / text._markdown_output_name(book)
                for node in media_nodes(decoded):
                    relative = Path(node['s'])
                    if relative.is_absolute() or '..' in relative.parts:
                        raise ValueError('Unsafe media filename')
                    target = output / 'media' / relative
                    response = runtime.get(book['resource_url'] + node['s'])
                    response.raise_for_status()
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(response.content)
                decoded_path = folder / 'decoded.json'
                atomic_json(decoded_path, decoded)
                book['decoded_file'] = str(decoded_path)
                paths = list(folder.glob('*')) + list((output / 'media').rglob('*'))
            else:
                raise ValueError('Unknown Litres content type')
            book['inputs'] = [{'path': str(p), 'sha256': file_digests(p)[0]} for p in paths if p.is_file()]
            book['acquired'] = True
            book.pop('download_error', None)
            selected.append(key)
            runtime.summary['downloaded'] += 1
        except (BudgetStop, SourceAccessError):
            raise
        except Exception as error:
            book['download_error'] = str(error)
            runtime.summary['errors'].append({'stage': 'download', 'error': str(error)})
        finally:
            commit(runtime, items)
    return selected


def inputs_valid(book):
    return bool(book.get('inputs')) and all(Path(v['path']).is_file() and file_digests(Path(v['path']))[0] == v['sha256'] for v in book['inputs'])


def finalize(runtime, items, selected=None):
    from . import litres_pdf as pdf, litres_text as text
    runtime.offline = True
    try:
        for key, book in items.items():
            if selected is not None and key not in selected:
                continue
            if not book.get('acquired') or not inputs_valid(book):
                continue
            if selected is None:
                runtime.budget.start_item()
            runtime.budget.check()
            fingerprint = hashlib.sha256(json.dumps([book['inputs'], runtime.config.get('pdf', {})], sort_keys=True).encode()).hexdigest()
            result = book.get('finalized', {})
            if result.get('fingerprint') == fingerprint and Path(result['path']).is_file() and file_digests(Path(result['path']))[0] == result['sha256']:
                runtime.summary['skipped'] += 1
                continue
            book.pop('pdf_file', None)
            if book['content_type'] == 'pdf':
                book['full_name'] = Path(book['full_name']).name.replace('..', '_')
                target = runtime.directory / 'docs' / f"{book['full_name']}.pdf"
                target.unlink(missing_ok=True)
                path = Path(pdf._create_pdf(book))
                book['pdf_file'] = str(path)
            else:
                decoded = json.loads(Path(book['decoded_file']).read_text())
                folder = runtime.directory / 'markdown' / text._markdown_output_name(book)
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / (folder.name + '.md')
                context = {'f': [], 'book': book, 'workdir': str(folder), 'footn_counter': 1}
                content = '\n\n'.join(text.textify(item, context) for fragment in decoded for item in fragment)
                content += '\n\n' + '\n\n'.join(context['f'])
                partial = path.with_suffix('.part')
                partial.write_text(content, encoding='utf-8')
                text._raise_if_preview_markdown(str(partial), book)
                partial.replace(path)
                book['markdown_file'] = str(path)
            if path.stat().st_size > runtime.settings.max_derived_pdf_bytes:
                path.unlink()
                raise ValueError('Derived output exceeds configured limit')
            book['finalized'] = {'path': str(path), 'sha256': file_digests(path)[0], 'fingerprint': fingerprint}
            runtime.summary['finalized'] = runtime.summary.get('finalized', 0) + 1
            commit(runtime, items)
    finally:
        runtime.offline = False


def import_state(runtime, items):
    origin = Path(runtime.config['_from']).resolve()
    if origin == runtime.directory.resolve():
        raise ValueError('Import source and destination must differ')
    review = origin / 'candidates-review.tsv'
    if review.exists() and not (runtime.directory / review.name).exists():
        shutil.copy2(review, runtime.directory / review.name)
    for name in ('books-index.json', 'candidates-index.json'):
        path = origin / name
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        if name.startswith('books'):
            for key, book in data.items():
                if key not in items:
                    items[key] = book
        else:
            target = runtime.directory / name
            current = json.loads(target.read_text()) if target.exists() else {}
            atomic_json(target, {**data, **current})
    for book in items.values():
        for field in ('pdf_file', 'markdown_file'):
            if book.get(field):
                source = Path(book[field])
                if not source.is_absolute():
                    source = origin / source
                if source.is_file():
                    target = runtime.directory / ('docs' if field == 'pdf_file' else 'markdown') / source.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if field == 'pdf_file':
                        from .litres_pdf import _is_valid_pdf_file
                        if not _is_valid_pdf_file(str(source)):
                            book.pop(field, None)
                            continue
                    else:
                        from .litres_text import _contains_preview_marker
                        if _contains_preview_marker(str(source)):
                            book.pop(field, None)
                            continue
                        target = runtime.directory / 'markdown' / source.parent.name / source.name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if (source.parent / 'media').exists():
                            shutil.copytree(source.parent / 'media', target.parent / 'media', dirs_exist_ok=True)
                    if source.resolve() != target.resolve():
                        shutil.copy2(source, target)
                    book.setdefault('imported_outputs', {})[field] = {'path': str(target), 'sha256': file_digests(target)[0]}
                    book[field] = str(target)
                else:
                    book.pop(field, None)
    commit(runtime, items)


def execute(settings, command, *, recheck=False, log=print):
    if command not in SUPPORTED_COMMANDS:
        raise ValueError('Unsupported Litres stage')
    directory = settings.artifacts_root / 'litres'
    if command == 'status':
        manifest = Manifest(directory, 'litres')
        result = manifest.status()
        records = books(manifest)
        result['acquired'] = sum(bool(b.get('acquired')) for b in records.values())
        result['finalized'] = sum(bool(b.get('finalized') or b.get('imported_outputs')) for b in records.values())
        candidates_path = directory / 'candidates-index.json'
        if candidates_path.exists():
            from collections import Counter
            candidates = json.loads(candidates_path.read_text())
            result['review_counts'] = dict(Counter(c.get('status', 'candidate') for c in candidates.values()))
        result['catalog'] = manifest.data.get('litres_catalog', {})
        result['publications'] = manifest.data.get('publications', {})
        return result
    if command in {'discover', 'download', 'run', 'metadata'}:
        sid = settings.source_options.get('sid')
        if not isinstance(sid, str) or not sid.strip() or sid == '<SET ME>':
            raise ValueError('Set sources.litres.sid in the selected operational YAML')
    summary = {'source': 'litres', 'command': command, 'id': uuid4().hex, 'started_at': now(), 'pages': 0, 'downloaded': 0, 'skipped': 0, 'requests': 0, 'network_retries': 0, 'errors': [], 'stops': []}
    with source_lock(directory):
        manifest = Manifest(directory, 'litres')
        runtime = Runtime(settings, manifest, summary)
        from .litres_utils import RUNTIME
        token = RUNTIME.set(runtime)
        items = books(manifest)
        try:
            with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                commit(runtime, items)
                if command == 'import-state':
                    import_state(runtime, items)
                if command in {'discover', 'run'}:
                    discover(runtime, items)
                if command in {'download', 'run'}:
                    selected = acquire(runtime, items, recheck)
                if command in {'finalize', 'run'}:
                    finalize(runtime, items, selected if command == 'run' else None)
                if command == 'review':
                    from . import litres_candidates as candidates
                    action = runtime.config['_action']
                    {'export': candidates.export_review, 'sync': candidates.sync_review, 'import': candidates.import_accepted}[action]()
                    if action == 'import':
                        items = json.loads((directory / 'books-index.json').read_text())
                if command == 'metadata':
                    from .litres_metadata import scrap_metadata
                    scrap_metadata()
                    items = json.loads((directory / 'books-index.json').read_text())
                if command == 'publish':
                    eligible = {}
                    for key, book in items.items():
                        outputs = list(book.get('imported_outputs', {}).values()) + ([book['finalized']] if book.get('finalized') else [])
                        if any(Path(v['path']).is_file() and file_digests(Path(v['path']))[0] == v['sha256'] for v in outputs):
                            eligible[key] = book
                    if not eligible:
                        raise ValueError('No verified finalized outputs to publish')
                    atomic_json(directory / 'books-index.json', eligible)
                    target = runtime.config['_target']
                    if target == 'yandex':
                        from .litres_upload_books import upload_pdfs
                        upload_pdfs()
                    elif target == 'hf':
                        from .litres_hf import upload_to_hf
                        upload_to_hf()
                    else:
                        from .litres_s3_media import upload_media_to_s3
                        upload_media_to_s3()
                    manifest.data.setdefault('publications', {})[target] = {'completed_at': now()}
        except BudgetStop as error:
            summary['stops'].append(str(error))
        except Exception as error:
            summary['errors'].append({'stage': command, 'error': str(error).replace(str(settings.source_options.get('sid') or '\0'), '[redacted]')})
        finally:
            if command == 'metadata' and (directory / 'books-index.json').exists():
                items = json.loads((directory / 'books-index.json').read_text())
            commit(runtime, items)
            runtime.close()
            RUNTIME.reset(token)
            summary.update(records=len(items), attempted_download_bytes=runtime.budget.bytes, started_items=runtime.budget.items, finished_at=now())
            summary['summary_path'] = str(directory / 'summaries' / (summary['id'] + '.json'))
            manifest.data['last_run'] = summary
            manifest.save()
            atomic_json(Path(summary['summary_path']), summary)
    return summary
