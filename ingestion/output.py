"""Compact command views; detailed run summaries remain the evidence authority."""
import json

from .views import preview

SUMMARY_BYTES = 8192
DIAGNOSTICS = {
    'error': ('stage', 'record', 'error', 'http_status'),
    'warning': ('stage', 'record', 'scan', 'page', 'error', 'http_status', 'retryable'),
}
REQUIRED = {'command', 'source', 'success', 'ok', 'error', 'error_count', 'warning_count',
            'error_preview', 'warning_preview', '_truncation'}


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode(
        'utf-8', errors='backslashreplace').decode('utf-8')


def _fit_summary(brief):
    def over_budget():
        return len(compact_json(brief).encode('utf-8')) > SUMMARY_BYTES

    if not over_budget():
        return brief
    brief['_truncation'] = {'$': 'content omitted: byte budget'}
    for key in reversed(tuple(brief)):
        if not over_budget():
            return brief
        if key not in REQUIRED and type(brief[key]) not in (bool, int, float):
            del brief[key]
    for severity in DIAGNOSTICS:
        samples = brief.get(f'{severity}_preview', [])
        while len(samples) > 1 and over_budget():
            samples.pop()
    if over_budget():
        # At most two samples and the identifier/error strings remain. Even JSON
        # escapes fit at this length.
        for key in ('command', 'source', 'error'):
            if isinstance(brief.get(key), str):
                brief[key] = brief[key][:64]
        for severity in DIAGNOSTICS:
            for sample in brief.get(f'{severity}_preview', []):
                sample.update({key: value[:64] for key, value in sample.items()})
    for key in reversed(tuple(brief)):
        if not over_budget():
            break
        if key not in REQUIRED:
            del brief[key]
    return brief


def compact_result(result, command, source=None, *, diagnostic_counts=None):
    brief = {"command": command}
    if source or result.get("source"):
        brief["source"] = source or result["source"]
    for severity, keys in DIAGNOSTICS.items():
        field = severity + 's'
        if severity == 'warning' and field not in result:
            continue
        entries = result.get(field) or []
        brief[f'{severity}_count'] = (diagnostic_counts or {}).get(severity, len(entries))
        if entries:
            brief[f'{severity}_preview'] = [
                {key: str(entry[key]) for key in keys if key in entry}
                if isinstance(entry, dict) else {'error': str(entry)} for entry in entries[:3]]
    for key in ("success", "ok", "pages", "records", "observations", "requests", "network_retries",
                "yandex_published", "upstream_metadata_saved", "duplicates", "catalog_registered", "catalog_reconciled", "publication_counts", "limited_skipped", "not_full_skipped", "awaiting_full_verification",
                "s3_attempted", "s3_published", "s3_skipped", "s3", "downloaded", "published", "skipped", "finalized", "acquired", "reused_blobs", "imported_originals", "not_modified",
                "unchanged_downloads", "attempted_download_bytes", "started_items", "pdf_assembled",
                "pdf_reused", "review_counts", "stops", "stop", "summary_path", "report_path", "state_key", "awaiting_inputs", "sources"):
        if key in result:
            brief[key] = result[key]
    catalog = result.get('catalog')
    if brief.get('source') == 'litres':
        catalog = result.get('discovery') if catalog is None else catalog
        if isinstance(catalog, dict):
            brief['catalog'] = {key: catalog[key] for key in ('next_page', 'complete') if key in catalog}
    elif brief.get('source') == 'milli_kitaphana' and isinstance(catalog, dict):
        brief['catalog'] = {'scans': len(catalog), 'complete_scans': sum(
            isinstance(scan, dict) and scan.get('complete') is True for scan in catalog.values())}
    publications = result.get('publications')
    if 'publication_counts' not in brief and isinstance(publications, (int, dict)):
        brief['publications'] = len(publications) if isinstance(publications, dict) else publications
    if "sources" in result:
        brief["source_count"] = len(result["sources"])
    if result.get("error"):
        brief.update(error_count=1, error=str(result["error"]))
    backlog = result.get("backlog", result)
    if "backlog" in result and "records" in backlog:
        brief["backlog_records"] = backlog["records"]
    for key in ("current_assets", "discovery_errors", "historical_discovery_errors", "pdf_books", "pdf_issues", "package_books", "package_pdfs", "image_pages"):
        if key in backlog:
            brief[key] = backlog[key]
    if "discovery" in backlog:
        brief["discovery"] = {key: backlog["discovery"][key] for key in (
            "complete", "remaining_listing_requests", "remaining_record_urls", "restart_required")
            if key in backlog["discovery"]}
    if command == "inspect" and "page" in result:
        page = result["page"]
        brief["page"] = {key: page[key] for key in (
            "status", "bytes_read", "response_body_complete", "pdf_signature") if key in page}
        brief["links_saved"] = result["links_saved"]
        brief["pdf_probes"] = len(result["pdf_probes"])
        brief["pdf_probe_errors"] = sum(bool(p.get("error")) or not 200 <= p.get("status", 0) < 300
                                         for p in result["pdf_probes"])
        brief["error_count"] = int(not result["ok"])
        if page.get("error"):
            brief["error"] = page["error"]
    sources = brief.pop('sources', None)
    # Reserve the structural preview budget for diagnostics and scalars first.
    brief = {**{k: v for k, v in brief.items() if k in REQUIRED or not isinstance(v, (dict, list))},
             **{k: v for k, v in brief.items() if k not in REQUIRED and isinstance(v, (dict, list))}}
    brief = preview(brief)
    if sources is not None:
        brief['sources'] = sources
    return _fit_summary(brief)
