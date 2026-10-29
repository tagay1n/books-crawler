"""Read-only, compact manifest inventory for operators and coding agents."""

import argparse
from collections import Counter
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path,
                        help="Artifact roots, source directories, or individual manifest.json files.")
    parser.add_argument("--details", action="store_true",
                        help="Include scan counts, asset formats and grouped discovery errors without dumping records.")
    args = parser.parse_args()
    paths = set()
    for root in args.roots:
        if root.is_file():
            paths.add(root)
        elif (root / "manifest.json").is_file():
            paths.add(root / "manifest.json")
        else:
            paths.update(root.glob("*/manifest.json"))
    if not paths:
        parser.error("No manifests found at the selected paths.")
    failed = False
    for path in sorted(paths):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            records, assets = data["records"], data["assets"]
            coverage = data.get("discovery", {})
            states = Counter(a.get("status", "unknown") for a in assets.values() if a.get("current", True))
            result = {"manifest": str(path), "source": data["source"], "records": len(records),
                      "current_assets": dict(sorted(states.items())),
                      "discovery_complete": coverage.get("complete"),
                      "pages": coverage.get("pages"),
                      "remaining_listings": coverage.get("remaining_listing_requests"),
                      "remaining_records": coverage.get("remaining_record_urls"),
                      "discovery_errors": len(data.get("discovery_errors", {}))}
            if args.details:
                result["scan"] = {key: coverage.get(key) for key in (
                    "catalog_entries_enumerated", "unique_records_inspected",
                    "advertised_catalog_entries", "count_verified", "restart_required")}
                result["asset_formats"] = dict(sorted(Counter(
                    a.get("extension") or "unknown" for a in assets.values()
                    if a.get("current", True)).items()))
                result["discovery_error_messages"] = dict(Counter(
                    error.get("error", "unknown") for error in data.get("discovery_errors", {}).values()))
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            result = {"manifest": str(path), "error": str(error)}
            failed = True
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
