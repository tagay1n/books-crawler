"""Read-only error scoping and preservation of discovery diagnostics."""

from datetime import datetime

from .paging import PageRequest


def partition_discovery_errors(data):
    """Return active and prior diagnostics, including unmodified legacy manifests.

    Errors must concern still-pending work in their recorded scan. Legacy errors
    remain active only when they also do not predate the scan.
    With no scan information, keep errors active rather than hiding uncertainty.
    """
    if not data.get("discovery_errors"):
        return {}, {}
    current, prior = {}, {}
    is_active = discovery_error_classifier(data.get("discovery_scan"))
    for key, error in data.get("discovery_errors", {}).items():
        (current if is_active(key, error) else prior)[key] = error
    return current, prior


def discovery_error_classifier(scan):
    """Build the shared active-error predicate once for a scan or streamed view."""
    if not scan:
        return lambda key, error: True
    active_requests = set(scan.get("pending_records", []))
    active_requests.update(PageRequest(**request).key() for request in scan.get("frontier", []))

    def is_active(key, error):
        if error.get("scan_id"):
            return error["scan_id"] == scan.get("id") and key in active_requests
        active = key in active_requests
        try:
            return active and datetime.fromisoformat(error["at"]) >= datetime.fromisoformat(scan["started_at"])
        except (KeyError, ValueError, TypeError):
            return active  # Unknown dates cannot prove a still-pending error is old.
    return is_active


def discovery_error_counts(data):
    current, prior = partition_discovery_errors(data)
    return {"discovery_errors": len(current),
            "historical_discovery_errors": len(data.get("discovery_error_history", [])) + len(prior)}


def archive_discovery_error(data, key, error, disposition, *, at):
    data.setdefault("discovery_error_history", []).append(
        {**error, "request_key": key, "archived_at": at, "disposition": disposition})
