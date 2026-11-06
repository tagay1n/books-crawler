import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .diagnostics import discovery_error_counts


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value, *, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".manifest-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            formatting = {"separators": (",", ":")} if compact else {"indent": 2}
            json.dump(value, handle, ensure_ascii=False, allow_nan=False, **formatting)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


_directory_sources = {}


@contextmanager
def source_lock(directory: Path, source=None):
    from .database import source_lock as postgres_lock
    source = source or _directory_sources.get(str(directory.resolve()), directory.name.replace('.', '_'))
    with postgres_lock(source):
        yield


class Manifest:
    def __init__(self, directory: Path, source="magarif", *, checkpoint=None, data=None):
        from .checkpoints import Checkpoint
        self.coordinator = checkpoint or Checkpoint()
        self.directory = directory
        self.path = directory / "manifest.json"
        from .postgres_state import Repository
        _directory_sources[str(directory.resolve())] = source
        self.repository = Repository(source)
        self.data = self.repository.load() if data is None else data
        self._assets_by_record = None

    def _record_asset_index(self):
        if self._assets_by_record is None:
            self._assets_by_record = {}
            for key, asset in self.data["assets"].items():
                owner = asset.get("record_key", asset["record_url"])
                self._assets_by_record.setdefault(owner, set()).add(key)
        return self._assets_by_record

    def save(self):
        self.repository.save(self.data)

    def checkpoint(self):
        self.coordinator(self.repository, self.data)

    def observe(self, metadata, assets, parser_version=1, *, record_key=None, persist=True):
        """Observe a record; callers deferring persistence must save their checkpoint.

        Discovery defers this save so the observation and its completed frontier
        work are published together. Other callers retain immediate persistence.
        """
        record_url = metadata["url"]
        record_key = record_key or record_url
        fingerprint = hashlib.sha256(json.dumps(metadata, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        record = self.data["records"].setdefault(record_key, {"observations": [], "first_seen": now()})
        if record_key != record_url:
            origins = record.setdefault("origin_urls", [])
            if record_url not in origins:
                origins.append(record_url)
        history = record["observations"]
        changed = (not history or history[-1]["fingerprint"] != fingerprint
                   or history[-1]["parser_version"] != parser_version)
        if changed:
            record.pop("imported_acquisition_complete", None)
            history.append({"id": uuid4().hex, "observed_at": now(), "fingerprint": fingerprint,
                            "parser_version": parser_version, "metadata": metadata})
            if "pdf" in record:
                record["pdf"]["status"] = "incomplete"
            if "package_pdf" in record:
                record["package_pdf"]["status"] = "incomplete"
        record["last_seen"] = now()
        record["attachment_count"] = len(assets)
        indexed = self._record_asset_index()
        for key in indexed.get(record_key, ()):
            self.data["assets"][key]["current"] = False
        for descriptor in assets:
            key = hashlib.sha256((record_key + "\n" + descriptor.get("source_asset_key", descriptor["url"])).encode()).hexdigest()
            asset = self.data["assets"].setdefault(key, {
                "id": key, "record_url": record_url, "status": "pending", "results": [],
            })
            previous_owner = asset.get("record_key", asset["record_url"])
            if any(asset.get(field) != descriptor.get(field) for field in ("url", "source_version")):
                asset.pop("imported_acquisition_complete", None)
            asset.update(descriptor, current=True, observation_id=history[-1]["id"])
            if record_key != record_url:
                asset.update(record_key=record_key, record_url=record_url)
            owner = asset.get("record_key", asset["record_url"])
            if previous_owner != owner:
                indexed.get(previous_owner, set()).discard(key)
            indexed.setdefault(owner, set()).add(key)
            if descriptor.get("unsupported_reason"):
                asset["status"] = "unsupported"
                asset["last_error"] = descriptor["unsupported_reason"]
            elif asset["status"] == "unsupported":
                asset["status"] = "pending"
                asset.pop("last_error", None)
        if persist:
            self.checkpoint()
        return changed

    def status(self):
        counts = {name: 0 for name in ("pending", "downloaded", "failed", "unsupported")}
        for asset in self.data["assets"].values():
            if asset.get("current", True):
                counts[asset["status"]] = counts.get(asset["status"], 0) + 1
        result = {"source": self.data["source"], "records": len(self.data["records"]),
                "records_without_attachments": sum(r.get("attachment_count") == 0 for r in self.data["records"].values()),
                "current_assets": counts, "historical_results": self.data.get("_historical_results", sum(len(a["results"]) for a in self.data["assets"].values()))}
        if "discovery" in self.data:
            result["discovery"] = self.data["discovery"].copy()
        result.update(discovery_error_counts(self.data))
        reasons = {}
        for asset in self.data["assets"].values():
            code = asset.get("unsupported_code")
            if asset.get("current", True) and asset["status"] == "unsupported" and code:
                reasons[code] = reasons.get(code, 0) + 1
        if reasons:
            result["unsupported_reasons"] = reasons
        packages = [r for r in self.data["records"].values() if "package_pdf" in r]
        if packages:
            result["package_books"] = {
                state: sum(r["package_pdf"].get("status") == state for r in packages)
                for state in ("complete", "incomplete", "failed")}
            result["package_pdfs"] = sum(len(r["package_pdf"].get("current_results", []))
                                          for r in packages if r["package_pdf"].get("status") == "complete")
        issues = [r for r in self.data["records"].values()
                  if r["observations"][-1]["metadata"].get("expected_pages") is not None]
        if issues:
            pdf_key = "pdf_books" if self.data["source"] in {"tatkniga", "kfu_books", "kfu_manuscripts"} else "pdf_issues"
            result[pdf_key] = {
                state: sum(r.get("pdf", {}).get("status", "incomplete") == state for r in issues)
                for state in ("complete", "incomplete", "failed")}
            result["image_pages"] = {"expected": sum(r["observations"][-1]["metadata"]["expected_pages"] for r in issues),
                                     "downloaded": sum(a.get("current", True) and a.get("kind") == "page_image"
                                                       and a["status"] == "downloaded" for a in self.data["assets"].values())}
        return result
