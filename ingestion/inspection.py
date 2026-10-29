"""Bounded public-page inspection, independent of adapter admission and manifests."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import time
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from bs4 import BeautifulSoup
import requests
from requests.utils import requote_uri
from urllib3.exceptions import HTTPError as TransportError

from .documents import DOCUMENT_EXTENSIONS, canonical, same_origin
from .network import Budget, BudgetStop, HTTP
from .state import atomic_json, now


@dataclass(frozen=True)
class InspectionSettings:
    soft_deadline_seconds: float = 60
    connect_timeout_seconds: float = 10
    read_timeout_seconds: float = 15
    pacing_seconds: float = 1


def public_url(value, base=None):
    url = canonical(value, base) if base else value
    parsed = urlsplit(url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or any(ord(c) < 32 or ord(c) == 127 for c in url)):
        raise ValueError("Inspection requires an HTTP(S) URL without credentials or control characters.")
    parsed.port  # Reject malformed ports before any request.
    return requote_uri(urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, "")))


def _fetch(http, url, path, limit, *, probe=False, origin=None):
    result = {"url": url, "response_body_complete": False}
    data = bytearray()

    def check_redirect(response, *args, **kwargs):
        target = public_url(response.headers["Location"], response.url) if response.is_redirect else public_url(response.url)
        if origin and not same_origin(target, origin):
            response.close()
            raise ValueError("PDF probe redirected outside the allowed origin; use --allow-external explicitly.")
        return response

    http.session.hooks["response"].append(check_redirect)
    try:
        headers = {"Range": f"bytes=0-{limit - 1}"} if probe else None
        # Error/challenge bodies are evidence here; adapter requests still raise.
        with http.request("GET", url, headers=headers, check_status=False) as response:
            result.update(final_url=response.url, status=response.status_code,
                          headers={key: response.headers[key] for key in (
                              "Content-Type", "Content-Length", "Content-Range", "Content-Disposition",
                              "ETag", "Last-Modified") if key in response.headers},
                          redirects=[{"url": r.url, "status": r.status_code,
                                      "location": r.headers.get("Location")} for r in response.history])
            mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            cap = min(limit, 1024) if mime == "application/pdf" else limit
            while len(data) < cap:
                http.budget.check()
                chunk = response.raw.read(min(1024 if not data else 65536, cap - len(data)), decode_content=True)
                if not chunk:
                    result["response_body_complete"] = True
                    break
                data.extend(chunk)
                if b"%PDF-" in data[:1024]:
                    cap = min(cap, 1024)
            length = response.headers.get("Content-Length", "")
            if (length.isdecimal() and int(length) == len(data)
                    and response.headers.get("Content-Encoding", "identity").lower() == "identity"):
                result["response_body_complete"] = True
    except (requests.RequestException, TransportError, BudgetStop, ValueError) as error:
        result["error"] = f"{type(error).__name__}: {error}"[:1000]
    finally:
        http.session.hooks["response"].remove(check_redirect)
    result.update(bytes_read=len(data), pdf_signature=b"%PDF-" in data[:1024])
    if data or "status" in result:
        path.write_bytes(data)
        result.update(body_path=str(path), sha256=hashlib.sha256(data).hexdigest())
    return result, bytes(data)


def _links(body, base):
    soup = BeautifulSoup(body, "html.parser")
    declared_base = soup.select_one("base[href]")
    if declared_base:
        try:
            base = public_url(declared_base["href"], base)
        except ValueError:
            pass
    links = {}
    truncated = False
    for tag in soup.select("a[href], iframe[src], object[data], embed[src], script[src]"):
        raw = tag.get("href") if tag.name == "a" else tag.get("data") if tag.name == "object" else tag.get("src")
        try:
            url = public_url(raw, base)
        except ValueError:
            continue
        if url in links:
            continue
        if len(links) >= 5000:
            truncated = True
            break
        suffix = Path(urlsplit(url).path).suffix.lower()
        label = tag.get_text(" ", strip=True)[:300] if tag.name == "a" else tag.get("title", "")[:300]
        links[url] = {"url": url, "label": label, "kind": tag.name,
                      "document_hint": suffix in DOCUMENT_EXTENSIONS - {".html", ".htm"} or suffix in {".zip", ".rar"},
                      "pdf_hint": suffix == ".pdf" or (tag.name == "a" and "pdf" in label.casefold())}
    title = soup.title.get_text(" ", strip=True)[:300] if soup.title else None
    return title, list(links.values()), truncated


def inspect(url, output_dir, *, max_bytes=2 * 1024 * 1024, max_links=20,
            probe_pdfs=0, allow_external=False):
    """Save evidence and return bounded JSON; never create acquisition records."""
    url = public_url(url)
    if not 1024 <= max_bytes <= 2 * 1024 * 1024:
        raise ValueError("max_bytes must be between 1 KiB and 2 MiB.")
    if not 1 <= max_links <= 200 or not 0 <= probe_pdfs <= 10:
        raise ValueError("max_links must be 1–200 and probe_pdfs 0–10.")
    directory = Path(output_dir) / (now().replace(":", "-") + "-" + uuid4().hex[:8])
    directory.mkdir(parents=True, exist_ok=False)
    settings = InspectionSettings()
    summary = {"requests": 0}
    http = HTTP(settings, Budget(settings), summary)
    http.session.max_redirects = 5

    def validate(method, target, data):
        if method != "GET" or data:
            raise ValueError("Inspection permits only read-only GET requests.")
        public_url(target)

    http.validate_request = validate
    report = {"started_at": now(), "evidence_dir": str(directory),
              "limits": {"page_bytes": max_bytes, "pdf_probe_bytes": 1024,
                         "max_pdf_probes": probe_pdfs, "soft_deadline_seconds": settings.soft_deadline_seconds},
              "pdf_probes": []}
    try:
        page, body = _fetch(http, url, directory / "page.body", max_bytes)
        report["page"] = page
        title, links, truncated = None, [], False
        mime = page.get("headers", {}).get("Content-Type", "").lower()
        if body and not page["pdf_signature"] and ("html" in mime or body.lstrip().startswith(b"<")):
            title, links, truncated = _links(body, page.get("final_url", url))
        atomic_json(directory / "links.json", links)
        hints = [link for link in links if link["document_hint"] or link["pdf_hint"]]
        report.update(title=title, links_saved=len(links), link_inventory_truncated=truncated,
                      links_path=str(directory / "links.json"),
                      links=(hints + [link for link in links if not (link["document_hint"] or link["pdf_hint"])])[:max_links])
        origin = page.get("final_url", url)
        candidates = [link for link in links if link["pdf_hint"]
                      and (allow_external or same_origin(link["url"], origin))]
        if not page.get("error") and 200 <= page.get("status", 0) < 300:
            for index, link in enumerate(candidates[:probe_pdfs], 1):
                if http.budget.deadline <= time.monotonic():
                    report["stop"] = "soft deadline"
                    break
                probe, _ = _fetch(http, link["url"], directory / f"pdf-{index}.prefix", 1024,
                                  probe=True, origin=None if allow_external else origin)
                report["pdf_probes"].append(probe)
                if "BudgetStop" in probe.get("error", ""):
                    report["stop"] = "soft deadline"
                    break
        report["ok"] = not page.get("error") and 200 <= page.get("status", 0) < 300
    finally:
        http.close()
    report.update(finished_at=now(), requests=summary["requests"],
                  note="PDF signatures are prefix evidence only; complete originals, language and account requirements are not inferred.",
                  report_path=str(directory / "report.json"))
    atomic_json(directory / "report.json", report)
    return report
