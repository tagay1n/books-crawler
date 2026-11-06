"""Read-only, compact manifest inventory for operators and coding agents."""

import argparse
import json
from pathlib import Path
import sys

# Keep the standalone repository command while sharing CLI error scoping.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion.overview import database_overview, snapshot_overview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", type=Path,
                        help="Artifact roots, source directories, or individual manifest.json files.")
    parser.add_argument("--details", action="store_true",
                        help="Include scan counts, asset formats and grouped discovery errors without dumping records.")
    parser.add_argument("--database", action="store_true", help="Read authoritative Postgres state instead of local snapshots.")
    parser.add_argument("--source", action="append", help="Select database sources (repeatable).")
    args = parser.parse_args()
    paths = set()
    for root in args.roots:
        if root.is_file():
            paths.add(root)
        elif (root / "manifest.json").is_file():
            paths.add(root / "manifest.json")
        else:
            paths.update(root.glob("*/manifest.json"))
    if args.database:
        from ingestion.registry import SOURCES
        paths = {Path("postgres") / source for source in args.source or SOURCES}
    if not paths:
        parser.error("No manifests found at the selected paths.")
    failed = False
    for path in sorted(paths):
        try:
            if args.database:
                result = database_overview(path.name, details=args.details)
            else:
                result = snapshot_overview(json.loads(path.read_text(encoding="utf-8")), details=args.details)
            result = {"manifest": str(path), **result}
        except (RuntimeError, OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            result = {"manifest": str(path), "error": str(error)}
            failed = True
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
