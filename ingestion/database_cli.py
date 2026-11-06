"""Explicit schema setup, read-only inventory and repeatable legacy imports."""
import copy
import hashlib
import json
from pathlib import Path
from typing import Annotated
import typer
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from .database import transaction, source_lock
from .postgres_state import Repository, bookkeeping, initialize
from .state import now

app = typer.Typer(help=__doc__, pretty_exceptions_show_locals=False)


@app.command('init')
def init_command():
    initialize()
    typer.echo('Postgres ingestion schema version 1 initialized')


@app.command('status')
def status_command():
    with transaction() as conn:
        rows = conn.execute(text("SELECT relname, pg_total_relation_size(relid) AS bytes FROM pg_catalog.pg_statio_user_tables WHERE schemaname='ingestion' ORDER BY relname")).mappings().all()
        size = conn.scalar(text('SELECT pg_database_size(current_database())'))
    typer.echo(json.dumps({'database_bytes':size, 'tables':[dict(r) for r in rows]}))


def read_import(source, paths, processing_dir=None):
    data = {'schema_version':1, 'source':source, 'records':{}, 'assets':{}}
    digests = []
    conflicts = []
    for path in paths:
        raw = path.read_bytes()
        digests.append(hashlib.sha256(raw).hexdigest())
        incoming = json.loads(raw.decode('utf-8-sig'))
        if not isinstance(incoming, dict):
            raise ValueError('Import must be a JSON object')
        if 'schema_version' in incoming:
            if incoming.get('source') != source or incoming['schema_version'] != 1:
                raise ValueError('Manifest source/schema mismatch')
            groups = {k:incoming.get(k,{}) for k in ('records','assets')}
            if source != 'tatkniga':
                for key,value in incoming.items():
                    if key not in {'schema_version','source','records','assets'}:
                        data.setdefault(key,value)
        elif path.name == 'candidates-index.json' and source == 'litres':
            data['candidates'] = incoming
            continue
        elif source == 'common_crawl':
            groups = {'records':incoming, 'assets':{}}
        else:
            records = {}
            for key, value in incoming.items():
                metadata = dict(value)
                metadata.setdefault('url', metadata.get('doc_url') or metadata.get('doc_card_url') or 'https://kitap.tatar.ru' + key)
                fingerprint = hashlib.sha256(json.dumps(metadata, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                records[key] = {'observations':[{'id':fingerprint, 'observed_at':now(), 'fingerprint':fingerprint, 'parser_version':1, 'metadata':metadata}], 'attachment_count':0, 'first_seen':now(), 'last_seen':now()}
            groups = {'records':records, 'assets':{}}
        for group, values in groups.items():
            for key,value in values.items():
                old = data[group].get(key)
                if old and old != value:
                    # Union immutable evidence; incompatible current values require explicit input selection.
                    merged = copy.deepcopy(old)
                    for field in ('observations','results'):
                        if field in value:
                            seen = {json.dumps(v,sort_keys=True) for v in merged.get(field,[])}
                            merged[field] = merged.get(field,[]) + [v for v in value[field] if json.dumps(v,sort_keys=True) not in seen]
                    incompatible = {k for k in old.keys() | value.keys() if k not in {'observations','results','first_seen','last_seen','last_checked'} and old.get(k)!=value.get(k)}
                    if group == 'records' and source == 'tatkniga' and incompatible <= {'attachment_count','pdf'}:
                        # A reader pilot adds pages/output evidence to the catalog record.
                        merged['attachment_count'] = max(old.get('attachment_count',0),value.get('attachment_count',0))
                        states = [v['pdf'] for v in (old,value) if v.get('pdf')]
                        if states:
                            merged['pdf'] = copy.deepcopy(next((v for v in states if v.get('status')=='complete'),states[-1]))
                        incompatible = set()
                    if incompatible:
                        if group == 'assets' and old.get('status') != value.get('status') and (old.get('status')=='downloaded' or value.get('status')=='downloaded'):
                            merged = copy.deepcopy(old if old.get('status')=='downloaded' else value)
                        else:
                            conflicts.append({'group':group,'key':key,'fields':sorted(incompatible)})
                    value = merged
                data[group][key] = value
    if processing_dir is not None:
        if source != 'milli_kitaphana':
            raise ValueError('--processing-dir is supported only for Milli Kitaphana')
        root = Path(processing_dir)
        for path in sorted((root / 'subindexes').glob('*.json')):
            raw = path.read_bytes()
            selection = json.loads(raw.decode('utf-8-sig'))
            if not isinstance(selection, dict):
                raise ValueError('Legacy worker selection must be a JSON object')
            key = 'selection:' + path.stem
            data[key] = list(selection)
            digests.append(hashlib.sha256(key.encode() + raw).hexdigest())
        for path in sorted((root / '_recovery').glob('*.json')):
            raw = path.read_bytes()
            report = json.loads(raw.decode('utf-8-sig'))
            if not isinstance(report, dict) or not isinstance(report.get('records'), dict):
                key = 'recovery_evidence:' + path.stem
                data[key] = report
                digests.append(hashlib.sha256(key.encode() + raw).hexdigest())
                continue
            name = 'default' if path.stem == 'report' else path.stem
            data.setdefault('recovery_reports', {})[name] = report
            digests.append(hashlib.sha256(('recovery:' + name).encode() + raw).hexdigest())
    # Completion is durable acquisition evidence, independent of old filesystem paths.
    if source in {'litres','milli_kitaphana'}:
        for record in data['records'].values():
            for observation in record.get('observations',[]):
                item = observation['metadata']
                complete = item.get('downloaded') == 'full' if source=='milli_kitaphana' else bool(item.get('pdf_file') or item.get('markdown_file') or item.get('acquired'))
                if complete:
                    item['imported_acquisition_complete'] = True
    if source == 'tatkniga':
        for record in data['records'].values():
            if record.get('pdf',{}).get('status') == 'complete':
                record['imported_acquisition_complete'] = True
        for asset in data['assets'].values():
            if asset.get('status')=='downloaded' and asset.get('results'):
                asset['imported_acquisition_complete'] = True
    fingerprint = hashlib.sha256(json.dumps([source,sorted(digests)]).encode()).hexdigest()
    return data, fingerprint, conflicts


@app.command('import')
def import_command(source: str = typer.Option(...,'--source'), paths: list[Path] = typer.Argument(...), apply: bool = typer.Option(False,'--apply'), processing_dir: Annotated[Path | None, typer.Option('--processing-dir', exists=True, file_okay=False)] = None):
    if source not in {'litres','milli_kitaphana','tatkniga','common_crawl'}:
        raise typer.BadParameter('Only the four established sources may be imported')
    data, fingerprint, conflicts = read_import(source,paths,processing_dir)
    report = {'source':source,'records':len(data['records']),'assets':len(data['assets']), 'payload_bytes':len(json.dumps(data).encode()),'conflicts':conflicts,'applied':False}
    metadata = [r['observations'][-1]['metadata'] if r.get('observations') else r for r in data['records'].values()]
    report['completion'] = {
        'records_acquired':sum(bool(r.get('imported_acquisition_complete') or (source == 'common_crawl' and (r.get('path_to_file') or r.get('uploaded')))) for r in metadata),
        'assets_acquired':sum(bool(a.get('imported_acquisition_complete')) for a in data['assets'].values()),
        'limited':sum(r.get('downloaded') == 'limited' for r in metadata),
        'uploaded':sum(bool(r.get('uploaded')) for r in metadata),
    }

    report['worker_selections'] = {k:len(v) for k,v in data.items() if k.startswith('selection:')}
    report['recovery_journals'] = {k:len(v['records']) for k,v in data.get('recovery_reports',{}).items()}
    if apply:
        if conflicts:
            raise typer.BadParameter('Resolve preview conflicts by selecting authoritative input files before applying')
        with source_lock(source):
            repository = Repository(source)
            current = repository.load()
            receipt_key = 'import:' + fingerprint
            with transaction() as conn:
                if conn.scalar(select(bookkeeping.c.key).where(bookkeeping.c.key==receipt_key)):
                    report['already_imported'] = True
                else:
                    # Existing database rows always win: re-import cannot regress newer work.
                    for group in ('records','assets'):
                        for key,value in data[group].items():
                            current[group].setdefault(key,value)
                    for key,value in data.items():
                        if key not in {'records','assets','source','schema_version'}:
                            if key == 'recovery_reports':
                                for name,journal in value.items():
                                    current.setdefault(key,{}).setdefault(name,journal)
                            else:
                                current.setdefault(key,value)
                    repository.save(current,connection=conn)
                    conn.execute(insert(bookkeeping).values(key=receipt_key,payload={'source':source,'fingerprint':fingerprint,'at':now()}))
                    report['applied'] = True
                report['database_bytes'] = conn.scalar(text('SELECT pg_database_size(current_database())'))
                report['source_bytes'] = sum(conn.scalar(text('SELECT pg_total_relation_size(to_regclass(:name))'), {'name':'ingestion.'+source+'_'+suffix}) or 0 for suffix in ('records','assets','state'))
    typer.echo(json.dumps(report,ensure_ascii=False))


def inspection_result(operation):
    try:
        typer.echo(json.dumps(operation(), ensure_ascii=False, separators=(',', ':')))
    except (ValueError, RuntimeError) as error:
        typer.echo(json.dumps({'error': str(error)[:500]}))
        raise typer.Exit(1)


@app.command('record')
def record_command(source: str = typer.Option(..., '--source'), key: str = typer.Option(..., '--key'),
                   assets: int = typer.Option(0, '--assets', min=0, max=100),
                   field: list[str] = typer.Option([], '--field', help='Select metadata fields; repeatable.')):
    """Inspect one record without observation/result histories; optional asset preview."""
    from .state_inspection import record
    inspection_result(lambda: record(source, key, assets, field))


@app.command('errors')
def errors_command(source: str = typer.Option(..., '--source'), limit: int = typer.Option(10, '--limit', min=1, max=100)):
    """Inspect bounded active, historical and last-run diagnostics."""
    from .state_inspection import errors
    inspection_result(lambda: errors(source, limit))


@app.command('last-run')
def last_run_command(source: str = typer.Option(..., '--source')):
    """Read the compact last-run summary."""
    from .state_inspection import last_run
    inspection_result(lambda: last_run(source))


@app.command('records')
def records_command(source: str = typer.Option(..., '--source'),
                    limit: int = typer.Option(10, '--limit', min=1, max=100),
                    after: str | None = typer.Option(None, '--after', help='Continue after a returned record key.')):
    """List record keys, titles and completion hints without loading histories."""
    from .state_inspection import records
    inspection_result(lambda: records(source, limit, after))
