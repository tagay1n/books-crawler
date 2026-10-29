"""Compact command views; detailed run summaries remain the evidence authority."""


def compact_result(result, command, source=None):
    brief = {"command": command}
    if source or result.get("source"):
        brief["source"] = source or result["source"]
    for key in ("success", "ok", "pages", "records", "observations", "requests", "network_retries",
                "downloaded", "skipped", "reused_blobs", "imported_originals", "not_modified",
                "unchanged_downloads", "attempted_download_bytes", "started_items", "pdf_assembled",
                "pdf_reused", "stops", "stop", "summary_path", "report_path", "sources"):
        if key in result:
            brief[key] = result[key]
    brief["error_count"] = len(result.get("errors", []))
    if "sources" in result:
        brief["source_count"] = len(result["sources"])
    if result.get("error"):
        brief.update(error_count=1, error=str(result["error"])[:500])
    backlog = result.get("backlog", result)
    if "backlog" in result and "records" in backlog:
        brief["backlog_records"] = backlog["records"]
    for key in ("current_assets", "discovery_errors", "historical_discovery_errors"):
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
            brief["error"] = page["error"][:500]
    return brief
