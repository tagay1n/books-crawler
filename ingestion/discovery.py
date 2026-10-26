"""Bounded catalog traversal with durable requests and record checkpoints."""

import hashlib
import json
from uuid import uuid4

import requests
from urllib3.exceptions import HTTPError as TransportError

from .paging import CatalogChanged, PageRequest
from .state import now


READ_ERRORS = (requests.RequestException, TransportError, ValueError)


def discover(http, manifest, adapter, summary, log):
    root = http.settings.archive_url
    version = getattr(adapter, "PARSER_VERSION", 1)
    scan = manifest.data.get("discovery_scan")
    if (not scan or scan.get("complete") or scan.get("restart_required")
            or scan.get("root") != root or scan.get("adapter_version") != version):
        scan = {"version": 1, "id": uuid4().hex, "root": root, "adapter_version": version,
                "started_at": now(), "complete": False, "frontier": [PageRequest(root).dump()],
                "visited": [], "pending_records": [], "enumerated_urls": [], "checked_urls": [],
                "record_keys": [], "enumerated_entries": 0, "listing_pages": 0, "batch_signatures": {}}
        manifest.data["discovery_scan"] = scan
    scan["verified"] = False
    errors = manifest.data.setdefault("discovery_errors", {})
    attempted = set()

    def coverage():
        return {
            "scan_id": scan["id"], "checked_at": now(), "complete": scan["complete"],
            "pages": scan["listing_pages"], "catalog_entries_enumerated": scan["enumerated_entries"],
            "unique_record_urls_enumerated": len(scan["enumerated_urls"]),
            "record_urls_inspected": len(scan["checked_urls"]), "unique_records_inspected": len(scan["record_keys"]),
            "remaining_listing_requests": len(scan["frontier"]), "remaining_record_urls": len(scan["pending_records"]),
            "advertised_catalog_entries": scan.get("advertised"),
            "count_verified": scan.get("verified", False), "restart_required": scan.get("restart_required", False),
        }

    def checkpoint():
        manifest.data["discovery"] = coverage()
        manifest.save()

    checkpoint()
    try:
        while True:
            http.budget.check()
            url = next((url for url in scan["pending_records"] if url not in attempted), None)
            if url is not None:
                attempted.add(url)
                try:
                    metadata, assets = adapter.record(http.text(url), url)
                    identity = adapter.record_key(metadata) if hasattr(adapter, "record_key") else metadata["url"]
                    changed = manifest.observe(metadata, assets, version, record_key=identity)
                    scan["pending_records"].remove(url)
                    if url not in scan["checked_urls"]:
                        scan["checked_urls"].append(url)
                    if identity not in scan["record_keys"]:
                        scan["record_keys"].append(identity)
                    summary["records"] += 1
                    summary["observations"] += int(changed)
                    errors.pop(url, None)
                    log(f"Discovered: {metadata['title']} ({len(assets)} attachments)")
                except READ_ERRORS as error:
                    errors[url] = {"at": now(), "error": str(error)}
                    summary["errors"].append({"url": url, "stage": "discover", "error": str(error)})
                    log(f"Discovery failed: {url}: {error}")
                checkpoint()
                continue

            if scan["frontier"]:
                if summary["pages"] >= http.settings.max_pages:
                    summary["stops"].append("discovery page cap")
                    break
                request = PageRequest(**scan["frontier"][0])
                key = request.key()
                if key in scan["visited"]:
                    scan["frontier"].pop(0)
                    checkpoint()
                    continue
                try:
                    html = http.text(request.url, method=request.method, data=request.data)
                    page = adapter.parse_listing(html, request, root)
                    summary["pages"] += 1
                    if page.validation:
                        if (page.advertised != scan.get("advertised")
                                or scan["enumerated_entries"] != scan.get("advertised")):
                            scan["restart_required"] = True
                            raise ValueError("Catalog count changed or enumeration disagrees with the advertised count; next discovery starts a fresh scan.")
                        scan["verified"] = True
                    else:
                        payload = page.fingerprint if page.fingerprint is not None else json.dumps(page.records)
                        signature = hashlib.sha256(payload.encode()).hexdigest()
                        check_repeats = request.method == "POST" or page.detect_repeats
                        if check_repeats and signature in scan["batch_signatures"]:
                            raise ValueError("Catalog returned a repeated pagination batch; discovery remains incomplete.")
                        if check_repeats:
                            scan["batch_signatures"][signature] = key
                        if page.advertised is not None:
                            scan["advertised"] = page.advertised
                        scan["listing_pages"] += 1
                        scan["enumerated_entries"] += page.entries if page.advertised is not None else len(page.records)
                        for record_url in page.records:
                            if record_url not in scan["enumerated_urls"]:
                                scan["enumerated_urls"].append(record_url)
                                scan["pending_records"].append(record_url)
                    scan["frontier"].pop(0)
                    scan["visited"].append(key)
                    existing = {PageRequest(**r).key() for r in scan["frontier"]}
                    for following in page.following:
                        if following.key() not in scan["visited"] and following.key() not in existing:
                            scan["frontier"].append(following.dump())
                            existing.add(following.key())
                    errors.pop(key, None)
                except READ_ERRORS as error:
                    if isinstance(error, CatalogChanged):
                        scan["restart_required"] = True
                    errors[key] = {"at": now(), "error": str(error)}
                    summary["errors"].append({"url": request.url, "stage": "discover", "error": str(error)})
                    log(f"Catalog discovery failed: {request.url}: {error}")
                    break
                checkpoint()
                continue

            if hasattr(adapter, "verification_request") and not scan.get("verified"):
                request = adapter.verification_request(root, scan.get("advertised"))
                # A failed record can be retried in a later invocation; verify counts again then.
                key = request.key()
                if key in scan["visited"]:
                    scan["visited"].remove(key)
                scan["frontier"].append(request.dump())
                checkpoint()
                continue
            scan["complete"] = not scan["pending_records"] and not scan.get("restart_required", False)
            break
    finally:
        checkpoint()
        summary["discovery_complete"] = scan["complete"]
        summary["coverage"] = manifest.data["discovery"].copy()
