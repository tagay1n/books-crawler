"""Bounded catalog traversal with durable requests and record checkpoints."""

import hashlib
import json
from collections import deque
from uuid import uuid4

import requests
from urllib3.exceptions import HTTPError as TransportError

from .paging import CatalogChanged, PageRequest
from .state import now
from .diagnostics import archive_discovery_error, partition_discovery_errors


READ_ERRORS = (requests.RequestException, TransportError, ValueError)


def discover(http, manifest, adapter, summary, log):
    root = http.settings.archive_url
    version = getattr(adapter, "PARSER_VERSION", 1)
    scan = manifest.data.get("discovery_scan")
    errors = manifest.data.setdefault("discovery_errors", {})
    if (not scan or scan.get("complete") or scan.get("restart_required")
            or scan.get("root") != root or scan.get("adapter_version") != version):
        initial = adapter.initial_request(root) if hasattr(adapter, "initial_request") else PageRequest(root)
        for key, error in list(errors.items()):
            archive_discovery_error(manifest.data, key, error, "scan_replaced", at=now())
            del errors[key]
        scan = {"version": 1, "id": uuid4().hex, "root": root, "adapter_version": version,
                "started_at": now(), "complete": False, "frontier": [initial.dump()],
                "visited": [], "pending_records": [], "enumerated_urls": [], "checked_urls": [],
                "record_keys": [], "enumerated_entries": 0, "listing_pages": 0, "batch_signatures": {}}
        manifest.data["discovery_scan"] = scan
    scan["verified"] = False
    _, prior_errors = partition_discovery_errors(manifest.data)
    for key, error in prior_errors.items():
        archive_discovery_error(manifest.data, key, error, "inactive", at=now())
        del errors[key]
    # Ordered lists remain the persisted format; indexes are invocation-local.
    visited = set(scan["visited"])
    enumerated = set(scan["enumerated_urls"])
    checked = set(scan["checked_urls"])
    record_keys = set(scan["record_keys"])
    pending = set(scan["pending_records"])
    pending_queue = deque(scan["pending_records"])
    frontier_keys = {PageRequest(**request).key() for request in scan["frontier"]}
    attempted = set()

    def queue_record(url):
        if url not in pending:
            scan["pending_records"].append(url)
            pending.add(url)
            pending_queue.append(url)

    def resolve_error(key):
        error = errors.pop(key, None)
        if error is not None:
            archive_discovery_error(manifest.data, key, error, "resolved", at=now())

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
            while pending_queue and pending_queue[0] in attempted:
                pending_queue.popleft()
            url = pending_queue.popleft() if pending_queue else None
            if url is not None:
                attempted.add(url)
                try:
                    metadata, assets = adapter.record(http.text(url), url)
                    contexts = scan.get("record_context", {}).get(url)
                    if contexts:
                        metadata["catalog_context"] = contexts
                    if hasattr(adapter, "resolve_record"):
                        metadata, assets = adapter.resolve_record(http, metadata, assets)
                    identity = adapter.record_key(metadata) if hasattr(adapter, "record_key") else metadata["url"]
                    changed = manifest.observe(metadata, assets, version, record_key=identity, persist=False)
                    scan["pending_records"].remove(url)
                    pending.discard(url)
                    if url not in checked:
                        scan["checked_urls"].append(url)
                        checked.add(url)
                    if identity not in record_keys:
                        scan["record_keys"].append(identity)
                        record_keys.add(identity)
                    summary["records"] += 1
                    summary["observations"] += int(changed)
                    resolve_error(url)
                    log(f"Discovered: {metadata['title']} ({len(assets)} attachments)")
                except READ_ERRORS as error:
                    errors[url] = {"at": now(), "error": str(error), "scan_id": scan["id"], "stage": "record"}
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
                if key in visited:
                    scan["frontier"].pop(0)
                    frontier_keys.discard(key)
                    checkpoint()
                    continue
                try:
                    html = http.text(request.url, method=request.method, data=request.data)
                    page = adapter.parse_listing(html, request, root)
                    summary["pages"] += 1
                    if page.validation:
                        if page.records and set(page.records) != enumerated:
                            raise CatalogChanged("Catalog identities changed during enumeration; next discovery starts a fresh scan.")
                        if (page.advertised != scan.get("advertised")
                                or scan["enumerated_entries"] != scan.get("advertised")
                                or (getattr(adapter, "UNIQUE_RECORDS", False)
                                    and len(scan["enumerated_urls"]) != page.advertised)):
                            scan["restart_required"] = True
                            raise ValueError("Catalog count changed or enumeration disagrees with the advertised count; next discovery starts a fresh scan.")
                        scan["verified"] = True
                    else:
                        if getattr(adapter, "UNIQUE_RECORDS", False):
                            if (len(set(page.records)) != len(page.records)
                                    or enumerated.intersection(page.records)):
                                raise CatalogChanged("Catalog repeated item identities; next discovery starts a fresh scan.")
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
                            context = page.record_context.get(record_url)
                            if context:
                                contexts = scan.setdefault("record_context", {}).setdefault(record_url, [])
                                if context not in contexts:
                                    contexts.append(context)
                                    # A newly found listing relationship is upstream evidence too.
                                    if record_url in checked:
                                        scan["checked_urls"].remove(record_url)
                                        checked.remove(record_url)
                                        attempted.discard(record_url)
                                        queue_record(record_url)
                            if record_url not in enumerated:
                                scan["enumerated_urls"].append(record_url)
                                enumerated.add(record_url)
                                queue_record(record_url)
                    scan["frontier"].pop(0)
                    frontier_keys.discard(key)
                    scan["visited"].append(key)
                    visited.add(key)
                    for following in page.following:
                        following_key = following.key()
                        if following_key not in visited and following_key not in frontier_keys:
                            scan["frontier"].append(following.dump())
                            frontier_keys.add(following_key)
                    resolve_error(key)
                except READ_ERRORS as error:
                    if isinstance(error, CatalogChanged):
                        scan["restart_required"] = True
                    errors[key] = {"at": now(), "error": str(error), "scan_id": scan["id"], "stage": "listing"}
                    summary["errors"].append({"url": request.url, "stage": "discover", "error": str(error)})
                    log(f"Catalog discovery failed: {request.url}: {error}")
                    break
                checkpoint()
                continue

            if hasattr(adapter, "verification_request") and not scan.get("verified"):
                request = adapter.verification_request(root, scan.get("advertised"))
                # A failed record can be retried in a later invocation; verify counts again then.
                key = request.key()
                if key in visited:
                    scan["visited"].remove(key)
                    visited.remove(key)
                scan["frontier"].append(request.dump())
                frontier_keys.add(key)
                checkpoint()
                continue
            scan["complete"] = not scan["pending_records"] and not scan.get("restart_required", False)
            break
    finally:
        checkpoint()
        summary["discovery_complete"] = scan["complete"]
        summary["coverage"] = manifest.data["discovery"].copy()
