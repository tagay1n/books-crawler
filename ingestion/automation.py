"""Credential preflight and credential-free Actions reporting for the shared CLI."""
import os
from datetime import datetime
from pathlib import Path


def require_access(settings, source):
    if source == 'litres':
        values = [settings.source_options.get('sid')]
    elif source == 'milli_kitaphana':
        config = settings.source_options
        values = [config.get('priv_key'), config.get('sig_prefix')]
        values.extend(config['aes'].get(key) for key in ('raw_key', 'default_iv', 'salt'))
    else:
        return
    if any(not isinstance(value, str) or not value.strip() or value == '<SET ME>' for value in values):
        raise ValueError(f'Missing access credentials for {source}')


def job_summary(result, source, command):
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if not path:
        return
    # Do not render upstream URLs, error messages, metadata or session values.
    from .registry import SOURCES
    if source not in SOURCES:
        source = 'unknown'
    def count(value):
        return value if type(value) in (int, float, bool) else 'unavailable'
    failed = bool(result.get('errors'))
    lines = [f'## Ingestion: {source}', '',
             f"Outcome: {'FAILED' if failed else 'partial (budget stop)' if result.get('stops') else 'completed'}", '',
             '| Metric | Value |', '| --- | --- |']
    for key in ('pages', 'records', 'downloaded', 'finalized', 'pdf_assembled', 'skipped',
                's3_published', 's3_skipped', 'attempted_download_bytes'):
        lines.append(f'| {key} | {count(result.get(key, 0))} |')
    lines.append(f"| failures | {len(result.get('errors', []))} |")
    start, end = result.get('started_at'), result.get('finished_at')
    if start and end:
        seconds = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
        lines.append(f'| duration seconds | {seconds:.1f} |')
    for section in ('backlog', 'discovery', 's3'):
        for key, value in result.get(section, {}).items():
            if type(value) in (int, float, bool) and key.replace('_', '').isalnum():
                lines.append(f'| {section}.{key} | {value} |')
    for section in ('current_assets', 'pdf_books', 'pdf_issues', 'package_books', 'image_pages'):
        for key, value in result.get('backlog', {}).get(section, {}).items():
            if type(value) in (int, float, bool) and key.replace('_', '').isalnum():
                lines.append(f'| backlog.{section}.{key} | {value} |')
    allowed = {'soft deadline', 'discovery time cap', 'download item cap', 'download byte cap',
               'discovery page cap', 'S3 item cap', 'finalization item cap', 'page cap'}
    stops = [s if s in allowed else 'other configured limit' for s in result.get('stops', [])]
    lines.extend(['', 'Stop reasons: ' + (', '.join(dict.fromkeys(stops)) or 'none'), ''])
    with Path(path).open('a', encoding='utf-8') as handle:
        handle.write('\n'.join(lines))
