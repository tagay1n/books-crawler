"""Miras-only HTTP access using cookies exported from a verified browser."""

import json
from pathlib import Path
import tempfile
import time
from uuid import uuid4

from .core import acquire
from .discovery import READ_ERRORS
from .miras_probe import SAMPLE_RECORD, book, catalog, validate_pdf
from .network import Budget, BudgetStop, HTTP
from .state import Manifest, atomic_json, now, source_lock


def read_json(path):
    path = path.expanduser().resolve()
    with path.open("rb") as handle:
        data = handle.read(256 * 1024 + 1)
    if len(data) > 256 * 1024:
        raise ValueError("Session export exceeds the 256 KiB limit.")
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError):
        raise ValueError("Invalid session export JSON.") from None
    if not isinstance(value, dict):
        raise ValueError("Session export must be a JSON object.")
    return path, value


def load_session(http, value):
    if value.get("format") != "miras-session-v1" or value.get("origin") != "https://miras.info":
        raise ValueError("Expected a Miras-only session JSON with format miras-session-v1.")
    agent, cookies = value.get("user_agent"), value.get("cookies")
    if not isinstance(agent, str) or not agent or len(agent) > 1024 or any(ord(c) < 32 for c in agent):
        raise ValueError("Invalid browser user agent in session export.")
    if not isinstance(cookies, list) or len(cookies) > 128:
        raise ValueError("Invalid Miras cookie list.")
    count = 0
    for cookie in cookies:
        if not isinstance(cookie, dict):
            raise ValueError("Invalid cookie descriptor.")
        domain = cookie.get("domain", "")
        if domain not in ("miras.info", ".miras.info"):
            raise ValueError("Session export contains a cookie outside Miras.")
        name, text, path = cookie.get("name"), cookie.get("value"), cookie.get("path", "/")
        if (not isinstance(name, str) or not name or not isinstance(text, str) or len(name) + len(text) > 32768
                or not isinstance(path, str) or not path.startswith("/")
                or any(ord(c) < 32 or ord(c) == 127 for c in name + text + path)):
            raise ValueError("Invalid cookie fields.")
        expires = cookie.get("expirationDate")
        if expires is not None and (type(expires) not in (int, float) or not 0 < expires < float("inf")):
            raise ValueError("Invalid cookie expiry.")
        if expires is not None and expires <= time.time():
            continue
        http.session.cookies.set(name, text, domain=domain, path=path,
                                 secure=bool(cookie.get("secure")), expires=int(expires) if expires else None)
        count += 1
    if not count:
        raise ValueError("No unexpired Miras cookies in the export. Verify in your browser and export again.")
    http.session.headers.update({"User-Agent": agent, "Referer": SAMPLE_RECORD})
    return count


def summary_for(command):
    return {"id": uuid4().hex, "source": "miras", "command": command, "started_at": now(),
            "success": False, "checks": {}, "requests": 0, "network_retries": 0, "downloaded": 0,
            "reused_blobs": 0, "not_modified": 0, "unchanged_downloads": 0, "errors": [], "stops": []}


def finish(summary, manifest, http):
    http.close()
    summary.update(finished_at=now(), attempted_download_bytes=http.budget.bytes,
                   started_items=http.budget.items,
                   summary_path=str(manifest.directory / "summaries" / (summary["id"] + ".json")))
    manifest.data["last_probe"] = summary
    manifest.save()
    atomic_json(Path(summary["summary_path"]), summary)


def observe_sample(manifest, metadata):
    manifest.observe(metadata, [{"url": metadata["pdf_url"], "label": metadata["title"],
                                 "extension": ".pdf", "unsupported_reason": None}], record_key="book:889")
    return next(a for a in manifest.data["assets"].values() if a.get("current", True))


def run_cookie_probe(settings, session_file, *, log=print):
    _, session = read_json(session_file)
    summary = summary_for("probe-cookies")
    summary["acquisition_method"] = "http_cookie_export"
    directory = settings.artifacts_root / "miras"
    with source_lock(directory):
        manifest = Manifest(directory / "pilot", "miras")
        http = HTTP(settings, Budget(settings), summary)
        workspace = manifest.directory / ".tmp"
        workspace.mkdir(parents=True, exist_ok=True)
        try:
            summary["cookie_count"] = load_session(http, session)
            log("Trying the exported Miras session with the HTTP downloader; cookie values are not logged.")
            metadata = None
            for url, parser, name in ((settings.archive_url.rstrip("/") + "/", catalog, "http_catalog"),
                                       (SAMPLE_RECORD, book, "http_record")):
                try:
                    result = parser(http.text(url))
                    summary["checks"][name] = {"ok": True, "url": url}
                    if name == "http_record":
                        metadata = result
                except READ_ERRORS as error:
                    response = getattr(error, "response", None)
                    summary["checks"][name] = {"ok": False, "url": url,
                                               "status": response.status_code if response is not None else None}
            if metadata:
                asset = observe_sample(manifest, metadata)
                http.budget.start_item()
                with tempfile.TemporaryDirectory(prefix="cookies-", dir=workspace) as temporary:
                    count = len(asset["results"])
                    acquire(http, manifest, asset, Path(temporary), summary, validate_file=validate_pdf)
                    if len(asset["results"]) > count:
                        result = asset["results"][-1]
                        result.update(acquisition_method="http_cookie_export",
                                      pages=validate_pdf(manifest.directory / result["path"]))
                asset["last_probe_method"] = "http_cookie_export"
                summary["checks"]["http_pdf"] = {"ok": True}
                summary["sample_result"] = asset["results"][-1]
            summary["success"] = all(summary["checks"].get(key, {}).get("ok")
                                      for key in ("http_catalog", "http_record", "http_pdf"))
            if not summary["success"]:
                summary["errors"].append({"stage": "access", "error": "Exported cookies did not establish complete HTTP access. Verify Miras in your ordinary browser and refresh the session export."})
        except BudgetStop as error:
            summary["stops"].append(str(error))
        except ValueError as error:
            summary["errors"].append({"stage": "validation", "error": str(error)})
        except READ_ERRORS:
            summary["errors"].append({"stage": "download", "error": "HTTP did not acquire a valid sample PDF."})
        except (OSError, KeyboardInterrupt):
            summary["errors"].append({"stage": "probe", "error": "Local I/O failure or cancelled."})
        finally:
            session.clear()
            finish(summary, manifest, http)
    return summary
