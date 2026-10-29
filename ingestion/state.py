import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


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


@contextmanager
def source_lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".lock").open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("Another command is already writing this source's artifacts.") from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class Manifest:
    def __init__(self, directory: Path, source="magarif"):
        self.directory = directory
        self.path = directory / "manifest.json"
        self.data = {"schema_version": 1, "source": source, "records": {}, "assets": {}}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(self.data, dict) or self.data.get("schema_version") != 1
                    or self.data.get("source") != source
                    or not isinstance(self.data.get("records"), dict)
                    or not isinstance(self.data.get("assets"), dict)):
                raise ValueError("Invalid or unsupported local manifest; refusing to overwrite it.")

    def save(self):
        # Large page inventories otherwise spend much of each checkpoint on
        # whitespace. Keep the schema and atomic replacement behavior unchanged.
        compact = len(self.data["assets"]) >= 1000 or len(self.data["records"]) >= 500
        atomic_json(self.path, self.data, compact=compact)

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
            history.append({"id": uuid4().hex, "observed_at": now(), "fingerprint": fingerprint,
                            "parser_version": parser_version, "metadata": metadata})
            if "pdf" in record:
                record["pdf"]["status"] = "incomplete"
            if "package_pdf" in record:
                record["package_pdf"]["status"] = "incomplete"
        record["last_seen"] = now()
        record["attachment_count"] = len(assets)
        for asset in self.data["assets"].values():
            if asset.get("record_key", asset["record_url"]) == record_key:
                asset["current"] = False
        for descriptor in assets:
            key = hashlib.sha256((record_key + "\n" + descriptor.get("source_asset_key", descriptor["url"])).encode()).hexdigest()
            asset = self.data["assets"].setdefault(key, {
                "id": key, "record_url": record_url, "status": "pending", "results": [],
            })
            asset.update(descriptor, current=True, observation_id=history[-1]["id"])
            if record_key != record_url:
                asset.update(record_key=record_key, record_url=record_url)
            if descriptor.get("unsupported_reason"):
                asset["status"] = "unsupported"
                asset["last_error"] = descriptor["unsupported_reason"]
            elif asset["status"] == "unsupported":
                asset["status"] = "pending"
                asset.pop("last_error", None)
        if persist:
            self.save()
        return changed

    def status(self):
        counts = {name: 0 for name in ("pending", "downloaded", "failed", "unsupported")}
        for asset in self.data["assets"].values():
            if asset.get("current", True):
                counts[asset["status"]] = counts.get(asset["status"], 0) + 1
        result = {"source": self.data["source"], "records": len(self.data["records"]),
                "records_without_attachments": sum(r.get("attachment_count") == 0 for r in self.data["records"].values()),
                "current_assets": counts, "historical_results": sum(len(a["results"]) for a in self.data["assets"].values())}
        if "discovery" in self.data:
            result["discovery"] = self.data["discovery"].copy()
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
