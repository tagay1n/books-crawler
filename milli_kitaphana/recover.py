"""Audit unfinished records and recover server-validated download links.

The report is a resumable journal. Limited documents are inspected but their
index state is preserved. Only complete, successfully downloaded documents are
marked full. Run with --download after reviewing the audit to fetch full docs.
"""

import argparse
import copy
import json
import os
import re
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import bs4
import requests

import download as downloader
from decrypt import _decrypt_file, decrypt_doc_parts
from utils import (HOST, base_dir, backup_index_snapshot, download_part,
                   dump_index, load_index_file, open_lock, get_index_file_loc,
                   read_config, request, request_session)


_locks = {}
_locks_guard = threading.Lock()

# Specific repairs supported by title-page evidence or known indexed inventory
# identifiers. Every candidate must still pass live document validation.
VERIFIED_CODE_REPAIRS = {
    "nbrt_tatarica_Inv_F_1631965": ("nbrt_tatarica_Inv_T_1631965", "Matching title, publisher, year (2006), and ISBN 5-298-03920-0"),
    "nbrt_tatarica_Inv_1510497": ("nbrt_tatarica_Inv_T_1510497", "Missing inventory letter T; same inventory in canonical card /tt/ssearch/detail/vqjkndtxuz"),
    "nbrt_tatarica_Inv_T_1650862_0": ("nbrt_tatarica_Inv_T_1650862", "Extraneous suffix; same inventory in canonical card /tt/ssearch/detail/xvbrnmxpwr"),
    "nbrt_tatarica_Inv_4252_51": ("nbrt_MAdab_Inv_4252_51", "Wrong collection prefix; same inventory/year in canonical card /tt/ssearch/detail/xlozzmcrue"),
}


@contextmanager
def _code_lock(code):
    with _locks_guard:
        lock = _locks.setdefault(code, threading.Lock())
    with lock:
        yield


class QuietProgress:
    """The existing download helpers can run without a shared terminal UI."""

    def __init__(self):
        self._aux = self

    def main(self, *args, **kwargs): pass
    def download(self, *args, **kwargs): return 0
    def decrypt(self, *args, **kwargs): return 0
    def update(self, *args, **kwargs): pass
    def stop_task(self, *args, **kwargs): pass


def code_from_url(url):
    path = unquote(urlparse(url.strip()).path)
    match = re.search(r"(?:^|/)dl/(.+)", path, re.I)
    if not match:
        return None
    return match[1].strip("/ .\t\r\n").replace("-", "_")


def code_candidates(code):
    """Keep the original first, then try bounded, explainable typo repairs."""
    if not code:
        return []
    candidates = [code]
    repaired = unquote(code).strip().replace("-", "_")
    repaired = re.sub(r"[/\\\s]+", "", repaired)
    repaired = repaired.translate(str.maketrans({"Т": "T", "т": "t", "М": "M", "А": "A", "а": "a", "с": "c", "С": "C", "о": "o", "О": "O", "р": "p", "Р": "P", "е": "e", "Е": "E"}))
    repaired = repaired.replace("tatrica", "tatarica")
    repaired = re.sub(r"_+", "_", repaired)
    repaired = re.sub(r"(^|_)([^_]+)_\2(?=_|$)", r"\1\2", repaired)
    candidates.append(repaired)
    if repaired.startswith("nbrt_Madab_"):
        candidates.extend(repaired.replace("nbrt_Madab_", prefix, 1)
                          for prefix in ("nbrt_MAdab_", "nbrt_mAdab_"))
    elif repaired.startswith("nbrt_MAdab_"):
        candidates.append(repaired.replace("nbrt_MAdab_", "nbrt_mAdab_", 1))
    elif repaired.startswith("nbrt_mAdab_"):
        candidates.append(repaired.replace("nbrt_mAdab_", "nbrt_MAdab_", 1))
    if re.match(r"nbrt_tatarica_(?:T_)?\d", repaired):
        candidates.append(repaired.replace("nbrt_tatarica_", "nbrt_tatarica_Inv_", 1))
    if "Pioner kalame" in code:
        candidates.append(code.replace("Pioner kalame", "PionerKalame"))
    if code in VERIFIED_CODE_REPAIRS:
        candidates.append(VERIFIED_CODE_REPAIRS[code][0])
    return list(dict.fromkeys(candidates))


def _error(exc):
    # Do not put server tokens or configuration secrets in the journal.
    if isinstance(exc, requests.HTTPError):
        return f"HTTP {exc.response.status_code}"
    return f"{type(exc).__name__}: {exc}".split("?token")[0]


def catalog_cover_candidates(card_path, original):
    """Search cards can expose inventory codes when detail rendering fails."""
    if not original.get("title"):
        return []
    with request("GET", HOST + "/tt/ssearch/ecollection/",
                 params={"attr": "text_t", "q": original["title"]}) as response:
        soup = bs4.BeautifulSoup(response.text, "html.parser")
    candidates = []
    for item in soup.select(".list__item"):
        link = item.select_one("a.list__title-link[href]")
        cover = item.select_one("img.list__img[src]")
        if not link or not cover or urlparse(link["href"]).path.rstrip("/") != card_path.rstrip("/"):
            continue
        filename = Path(urlparse(cover["src"]).path).stem
        if filename.startswith("nbrt_") and re.fullmatch(r"[\w ]+", filename):
            candidates.append((filename, cover["src"]))
    return candidates


def unfinished(meta):
    if meta.get("record_type") == "collection":
        return False
    return meta.get("downloaded") != "full" or not meta.get("decrypted")


def classify_collections(report):
    with open_lock(get_index_file_loc()):
        index = load_index_file()
        changed = False
        for key, result in report["records"].items():
            if "collections" in (result.get("catalog_record_id") or "").split("\\"):
                result["status"] = "collection"
                if key in index:
                    index[key]["record_type"] = "collection"
                    changed = True
        if changed:
            dump_index(index)


def apply_link_repairs(report):
    """Persist confirmed URL corrections without promoting limited downloads."""
    with open_lock(get_index_file_loc()):
        index = load_index_file()
        changed = False
        for key, result in report["records"].items():
            if result["status"] not in ("limited", "available_full"):
                continue
            meta = index.get(key)
            if meta is None or not unfinished(meta):
                continue
            old_code = meta.get("download_code")
            if not result.get("link_repaired") and not (old_code and old_code != result["code"]):
                continue
            meta["download_code"] = result["code"]
            meta["doc_url"] = HOST + "/dl/" + result["code"]
            for field in ("title", "author", "publish_year", "lang", "collection", "tags", "integrated_description"):
                if not meta.get(field) and result.get("metadata", {}).get(field):
                    meta[field] = copy.deepcopy(result["metadata"][field])
            meta.pop("broken", None)
            result["link_fix_applied"] = True
            changed = True
        if changed:
            dump_index(index)


def resolve_completed_duplicates(report):
    """Resolve a validated exact code or one exact completed edition match."""
    fields = ("title", "publish_year", "author", "lang", "collection")
    with open_lock(get_index_file_loc()):
        index = load_index_file()
        identities = {}
        codes = {}
        for key, meta in index.items():
            if meta.get("downloaded") == "full" and meta.get("decrypted") and not meta.get("broken") and not meta.get("duplicate_of"):
                if meta.get("download_code"):
                    codes.setdefault(meta["download_code"], []).append((key, meta))
                if all(meta.get(f) for f in fields):
                    identities.setdefault(tuple(meta[f] for f in fields), []).append((key, meta))
        changed = False
        for key, result in report["records"].items():
            if result["status"] not in ("no_download_link", "link_unavailable", "available_full"):
                continue
            original = index.get(key, {})
            identity_meta = original
            if result.get("original_code") in VERIFIED_CODE_REPAIRS and not original.get("title"):
                identity_meta = result.get("metadata", original)
            matches = codes.get(result.get("code"), []) if result["status"] == "available_full" else []
            method = "download_code"
            if len(matches) != 1:
                matches = identities.get(tuple(identity_meta.get(f) for f in fields), [])
                method = "bibliographic_identity"
            if len(matches) != 1 or matches[0][0] == key:
                continue
            canonical_key, canonical = matches[0]
            old_code = result.get("code") or original.get("download_code")
            if old_code and canonical.get("download_code") not in code_candidates(old_code):
                continue
            original.update(copy.deepcopy(canonical))
            original.pop("broken", None)
            original["duplicate_of"] = canonical_key
            result.update(status="duplicate_completed", duplicate_of=canonical_key,
                          code=canonical["download_code"], match_method=method)
            changed = True
        if changed:
            dump_index(index)


def write_summary(report, path):
    def cell(value):
        return str(value or "").replace("|", "\\|").replace("\n", " ")

    rows = ["# Milli Kitaphana recovery", "",
            f"Checked {len(report['records'])} of {report['target_count']} unfinished records.", "",
            "| Result | Records |", "| --- | ---: |"]
    rows.extend(f"| {status} | {count} |" for status, count in report["counts"].items())
    pdfs = {r["pdf_path"]: r["pages"] for r in report["records"].values() if r["status"] == "recovered"}
    if pdfs:
        rows.extend(["", f"Recovered {len(pdfs)} distinct PDFs containing {sum(pdfs.values())} pages."])
    rows.extend(["", f"[Full per-record audit]({Path(path).with_suffix('.json').name})"])
    rows.extend(["", "The JSON journal contains the result for every record. Limited records have missing full-text parts on the server; their download status was preserved.",
                 "Recovered PDFs are local. The existing upload/database workflow remains pending (`decrypted: false`).", "",
                 "## Corrected links", "", "| Original code | Working code | Result |", "| --- | --- | --- |"])
    for result in report["records"].values():
        if result.get("link_repaired") and result.get("code"):
            rows.append(f"| {cell(result.get('original_code') or (result.get('catalog_links') or ['Not stored; recovered from cover'])[0])} | {cell(result['code'])} | {result['status']} |")
    marked_full = [r for r in report["records"].values() if r["status"] == "limited" and r.get("original_downloaded") == "full"]
    if marked_full:
        rows.extend(["", "## Previously full-marked records that remain unfinished", "",
                     "These existing flags were preserved, but the current server offers only a preview and a complete local download could not be restored.", ""])
        for result in marked_full:
            rows.append(f"- {cell(result.get('title'))} (`{result['code']}`): {result['available_pages']} of {result['pages']} pages available.")
    rows.extend(["", "## Recovered documents", "", "| Title | Code | Pages | PDF |", "| --- | --- | ---: | --- |"])
    for result in report["records"].values():
        if result["status"] == "recovered":
            rows.append(f"| {cell(result.get('title') or result.get('metadata', {}).get('title'))} | {result['code']} | {result['pages']} | [PDF]({result['pdf_path']}) |")
    rows.extend(["", "## Obsolete cards matched to completed documents", "",
                 "These match a single completed record by a live-validated download code, or exactly by title, publication year, author, language, and collection. Their index state now points to that record.", "",
                 "| Old card | Completed card | Code |", "| --- | --- | --- |"])
    for key, result in report["records"].items():
        if result["status"] == "duplicate_completed":
            rows.append(f"| {key} | {result['duplicate_of']} | {result['code']} |")
    rows.extend(["", "## Unresolved links and server errors", "", "| Card | Code | Result | Error |", "| --- | --- | --- | --- |"])
    for key, result in report["records"].items():
        if result["status"] not in ("limited", "recovered", "already_full", "available_full", "duplicate_completed", "collection"):
            errors = result.get("error") or result.get("card_error") or "; ".join(a["code"] + ": " + a["error"] for a in result.get("attempts", []))
            rows.append(f"| [Catalog]({HOST}{key}) | {cell(result.get('code') or result.get('original_code'))} | {result['status']} | {cell(errors)} |")
    Path(path).write_text("\n".join(rows) + "\n", encoding="utf-8")


def audit_one(card_path, original, config):
    # Duplicate catalog entries can share a local document directory.
    with _code_lock(original.get("download_code") or card_path), request_session():
        return _audit_one(card_path, original, config)


def _audit_one(card_path, original, config):
    result = {"card_path": card_path, "title": original.get("title"),
              "original_code": original.get("download_code"),
              "original_downloaded": original.get("downloaded"), "attempts": []}
    meta = copy.deepcopy(original)
    codes = []
    try:
        with request("GET", HOST + card_path) as response:
            soup = bs4.BeautifulSoup(response.text, "html.parser")
            record = soup.select_one(".record")
            if record is None:
                raise ValueError("Catalog page has no .record")
            result["catalog_record_id"] = record.get("id")
            if "collections" in (record.get("id") or "").split("\\"):
                result["status"] = "collection"
                return result
            for anchor in record.select("a[href]"):
                code = code_from_url(anchor["href"])
                if code:
                    codes.append(code)
                    result.setdefault("catalog_links", []).append(anchor["href"])
            # Refresh descriptive metadata without retaining a stale code.
            fresh = {}
            downloader._scrap_doc_card(card_path, fresh, proxies=None)
            for field in ("integrated_description", "classification", "doc_card_url", "doc_url"):
                if field in fresh:
                    meta[field] = fresh[field]
    except Exception as exc:
        result["card_error"] = _error(exc)
    codes.extend([original.get("download_code"), code_from_url(original.get("doc_url", ""))])
    if not any(codes):
        try:
            covers = catalog_cover_candidates(card_path, original)
            codes.extend(code for code, _ in covers)
            if covers:
                result["cover_links"] = [url for _, url in covers]
                result["repair_evidence"] = "Inventory code from the cover image on the exact catalog search result"
        except Exception as exc:
            result["search_error"] = _error(exc)
    candidates = list(dict.fromkeys(c for code in codes for c in code_candidates(code)))
    if not candidates:
        card_error = result.get("card_error", "")
        result["status"] = "audit_failed" if card_error and not card_error.startswith(("HTTP 404", "ValueError:")) else "no_download_link"
        return result
    for code in candidates:
        if not re.fullmatch(r"[\w ]+", code):
            result["attempts"].append({"code": code, "error": "Malformed code; trying normalized candidate"})
            continue
        meta["download_code"] = code
        context = {"meta": meta, "config": config, "progress": QuietProgress()}
        try:
            downloader._get_details(context)
        except Exception as exc:
            result["attempts"].append({"code": code, "error": _error(exc)})
            continue
        result["code"] = code
        result["link_repaired"] = code != (codes[0] if codes else None)
        if result.get("cover_links"):
            result["link_repaired"] = True
        if codes[0] in VERIFIED_CODE_REPAIRS and VERIFIED_CODE_REPAIRS[codes[0]][0] == code:
            result["repair_evidence"] = VERIFIED_CODE_REPAIRS[codes[0]][1]
            if not meta.get("title"):
                known = [m for m in load_index_file().values() if m.get("download_code") == code and m.get("title")]
                if known:
                    for field in ("title", "author", "publish_year", "lang", "collection", "tags", "integrated_description"):
                        if not meta.get(field) and known[0].get(field):
                            meta[field] = copy.deepcopy(known[0][field])
                    result["title"] = meta.get("title")
        try:
            downloader._get_dh_params(context)
            downloader._dh_key_exchange(context)
            enc_dir = download_part(context, "part0.zip")
            meta_dir = _decrypt_file(context, "part0.zip", enc_dir)
            with open(os.path.join(meta_dir, "source.json"), encoding="utf-8") as file:
                source = json.load(file)
            parts = source["parts"]
            if not parts:
                raise ValueError("Document metadata contains no parts")
            result["parts"] = len(parts)
            result["available_parts"] = sum(bool(p.get("url")) for p in parts)
            result["pages"] = sum(p.get("pagesCount", 0) for p in parts)
            result["available_pages"] = sum(p.get("pagesCount", 0) for p in parts if p.get("url"))
            result["status"] = "available_full" if all(p.get("url") for p in parts) else "limited"
            # No key material in reports; refresh key exchange before downloading.
            result["metadata"] = {k: v for k, v in meta.items() if k not in (
                "decryption_key", "decryption_key_iv", "enc_part_paths", "format_url")}
        except Exception as exc:
            result["status"] = "metadata_failed"
            result["error"] = _error(exc)
        return result
    result["status"] = "link_unavailable"
    return result


def fetch_full(meta, config):
    context = {"meta": meta, "config": config, "progress": QuietProgress()}
    with request_session():
        downloader._get_details(context)
        downloader._get_dh_params(context)
        downloader._dh_key_exchange(context)
        downloader._download_by_code(context)
    if meta.get("access") != "open" or not meta.get("enc_part_paths"):
        raise ValueError("Document no longer has all parts available")
    return context


def recover(report_path, workers=4, download=False, retry_failed=False, download_workers=4):
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = json.loads(report_path.read_text()) if report_path.exists() else {
        "started_at": datetime.now(timezone.utc).isoformat(), "records": {}}
    index = load_index_file()
    config = read_config()
    targets = {k: v for k, v in index.items() if unfinished(v)}
    report["target_count"] = len(set(targets) | set(report["records"]))
    if retry_failed:
        for key, result in list(report["records"].items()):
            failed_card = result["status"] == "no_download_link" and result.get("card_error", "").startswith(("HTTP 5", "ConnectionError:", "ReadTimeout:"))
            if (result["status"] in ("audit_failed", "metadata_failed", "link_unavailable") or failed_card) and key in targets:
                report.setdefault("previous_failures", []).append({
                    "card_path": key, "status": result["status"],
                    "error": result.get("error"), "attempts": result.get("attempts", [])})
                del report["records"][key]
            elif result["status"] == "download_failed":
                result["status"] = "available_full"

    def save():
        report["counts"] = dict(Counter(r["status"] for r in report["records"].values()))
        temp = report_path.with_suffix(".tmp")
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(report_path)

    pending = [(k, v) for k, v in targets.items() if k not in report["records"]]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(audit_one, k, v, config): k for k, v in pending}
        for future in as_completed(jobs):
            key = jobs[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"card_path": key, "status": "audit_failed", "error": _error(exc)}
            report["records"][key] = result
            save()
            count = len(report["records"])
            if count % 25 == 0 or result.get("link_repaired") or result["status"] == "available_full":
                print(f"Audited {count}/{report['target_count']}: {result['status']} {result.get('code', key)}; {report['counts']}", flush=True)
    if not download:
        save()
        write_summary(report, report_path.with_suffix(".md"))
        return report
    if "index_backup" not in report:
        report["index_backup"] = backup_index_snapshot()
    classify_collections(report)
    resolve_completed_duplicates(report)
    apply_link_repairs(report)
    save()
    groups = {}
    current_index = load_index_file()
    for key, result in report["records"].items():
        if result["status"] != "available_full":
            continue
        current = current_index.get(key, {})
        if current.get("downloaded") == "full" and current.get("decrypted"):
            result["status"] = "already_full"
            save()
            continue
        meta = copy.deepcopy(current)
        meta.update(result["metadata"])
        meta["download_code"] = result["code"]
        meta.setdefault("title", result.get("title") or result["code"])
        meta.setdefault("integrated_description", [])
        groups.setdefault(result["code"], []).append((key, result, meta))
    # Network transfers can overlap. Keep all PyMuPDF operations on this thread;
    # PyMuPDF does not support concurrent use from Python threads.
    with ThreadPoolExecutor(max_workers=download_workers) as pool:
        jobs = {}
        for group in groups.values():
            representative = next((m for _, r, m in group if r.get("title")), group[0][2])
            jobs[pool.submit(fetch_full, representative, config)] = group
        for future in as_completed(jobs):
            group = jobs[future]
            try:
                context = future.result()
                meta = context["meta"]
                pdf_path = decrypt_doc_parts(context)
                import pymupdf
                with pymupdf.open(pdf_path) as pdf:
                    expected = group[0][1]["pages"]
                    if pdf.page_count != expected:
                        raise ValueError(f"PDF has {pdf.page_count} pages; expected {expected}")
                meta.update(downloaded="full", decrypted=False)
                meta.pop("broken", None)
                with open_lock(get_index_file_loc()):
                    latest = load_index_file()
                    for key, result, _ in group:
                        updated = copy.deepcopy(meta)
                        if result.get("link_repaired"):
                            updated["doc_url"] = HOST + "/dl/" + result["code"]
                        if unfinished(latest.get(key, {})):
                            latest[key] = updated
                    dump_index(latest)
                for _, result, _ in group:
                    result.update(status="recovered", pdf_path=pdf_path)
                print(f"RECOVERED {meta['download_code']}: {expected} pages -> {pdf_path}", flush=True)
            except Exception as exc:
                for _, result, _ in group:
                    result.update(status="download_failed", error=_error(exc))
                print(f"DOWNLOAD FAILED {group[0][1]['code']}: {_error(exc)}", flush=True)
            save()
    save()
    write_summary(report, report_path.with_suffix(".md"))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default=os.path.join(base_dir, "_recovery", "report.json"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--download-workers", type=int, default=4)
    args = parser.parse_args()
    recover(args.report, args.workers, args.download, args.retry_failed, args.download_workers)
