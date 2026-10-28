"""All historical KFU repository collections, with item-level Tatar admission."""

import copy
import json
import os
import re
import shutil
from urllib.parse import urlsplit
from uuid import uuid4

from bs4 import BeautifulSoup

from . import kfu
from .documents import canonical
from .paging import CatalogChanged, ListingPage, PageRequest
from .state import now


ARCHIVE_URL = kfu.ORIGIN + "/jspui/community-list"
PARSER_VERSION = 2
record_key = kfu.record_key


def collections(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("main#content ul.collection-list > li")
    if not rows:
        raise ValueError("KFU collection tree is missing.")
    result = {}
    for row in rows:
        anchor = row.find("a", recursive=False)
        counter = row.find("span", class_="count", recursive=False)
        count = re.fullmatch(r"\s*\((\d+)\)\s*", counter.get_text() if counter else "")
        if anchor is None or not anchor.get("href") or count is None:
            raise ValueError("KFU collection entry lacks its native link or count.")
        url = canonical(anchor["href"], ARCHIVE_URL)
        identity = kfu.handle(url)
        if urlsplit(url).query:
            raise ValueError("Unexpected query in KFU collection tree.")
        parents = []
        for block in row.find_parents("div", class_="item-list"):
            heading = block.find_previous_sibling("div", class_="community-block")
            link = heading.select_one("a.community-heading[href]") if heading else None
            if link is not None:
                parent = canonical(link["href"], ARCHIVE_URL)
                parents.append({"handle": kfu.handle(parent), "title": link.get_text(" ", strip=True)})
        entry = {"collection_url": url, "collection_handle": identity,
                 "collection_title": anchor.get_text(" ", strip=True),
                 "advertised_count": int(count[1]), "communities": list(reversed(parents))}
        if url in result and result[url] != entry:
            raise CatalogChanged("KFU tree repeats a collection with inconsistent metadata.")
        result[url] = entry
    return result


def collection_request(entry, remaining, tree):
    return PageRequest(entry["collection_url"], context={"collection": entry,
                       "count": entry["advertised_count"], "seen": [],
                       "remaining": remaining, "tree": tree,
                       "_request_identity": {"collection": entry["collection_handle"], "verify": False}})


def next_collection(context):
    remaining = context["remaining"]
    if remaining:
        return [collection_request(remaining[0], remaining[1:], context["tree"])]
    return [PageRequest(ARCHIVE_URL, context={"verify_tree": True, "tree": context["tree"],
                                             "_request_identity": {"verify_tree": True}})]


def parse_listing(html, request, root):
    if request.url == ARCHIVE_URL:
        tree = collections(html)
        if request.context.get("verify_tree"):
            if tree != request.context["tree"]:
                raise CatalogChanged("KFU collection tree changed; restart repository enumeration.")
            return ListingPage([], [])
        # Start with existing Tatar-focused slices; the rest of the tree is still traversed.
        preferred = ["27528", "27744", "28060", "25046", "27574", "18503", "86"]
        order = {"net/" + value: index for index, value in enumerate(preferred)}
        entries = sorted(tree.values(), key=lambda e: (order.get(e["collection_handle"], len(order)), e["collection_url"]))
        following = [collection_request(entries[0], entries[1:], tree)]
        return ListingPage([], following, fingerprint=json.dumps(tree, sort_keys=True))
    entry = request.context["collection"]
    collection_root = entry["collection_url"]
    if entry["advertised_count"] == 0:
        soup = BeautifulSoup(html, "html.parser")
        main = soup.select_one("main#content")
        if main is None or "В этой коллекции нет ресурсов" not in main.get_text(" ", strip=True):
            raise ValueError("Expected an explicitly empty KFU collection.")
        return ListingPage([], next_collection(request.context))
    page = kfu.parse_listing(html, request, collection_root)
    seen = request.context.get("seen", [])
    if page.validation:
        if len(seen) != page.advertised:
            raise CatalogChanged("KFU collection enumeration does not match its final count.")
        # Counts are checked per collection; shared discovery has no single global item count.
        return ListingPage([], next_collection(request.context))
    if set(seen).intersection(page.records):
        raise CatalogChanged("KFU collection repeated a record across pagination batches.")
    seen = seen + page.records
    following = page.following or [kfu.verification_request(collection_root, page.advertised)]
    for next_page in following:
        next_page.context.update(collection=entry, seen=seen,
                                 remaining=request.context["remaining"], tree=request.context["tree"],
                                 _request_identity={"collection": entry["collection_handle"],
                                                    "verify": bool(next_page.context.get("verify"))})
    page.following = following
    page.advertised = None
    page.detect_repeats = False  # Records can legitimately belong to multiple collections.
    page.record_context = {url: entry for url in page.records}
    return page


def record(html, page_url):
    metadata, assets = kfu.record(html, page_url)
    rows = metadata["bibliography_raw"]
    metadata["publication"] = {
        "series_raw": [r["value_raw"] for r in rows if "dc_relation_ispartofseries" in r["field_classes"]],
        "publication_dates_raw": [r["value_raw"] for r in rows if "dc_date_issued" in r["field_classes"]],
        "type_raw": [r["content"] for r in metadata["dc_metadata"] if r["name"] == "DC.type"],
        "issue_title_raw": metadata["title_raw"],
    }
    metadata, assets = kfu.select_tatar(metadata, assets, publication="KFU repository")
    metadata["admission_reason"] = "Repository-wide acquisition requires an explicit Tatar item-language label; source claims remain unverified."
    return metadata, assets


def prepare_http(http, session_file):
    def tree_route(url):
        if url != ARCHIVE_URL:
            raise ValueError("Unexpected KFU collection-tree URL.")
        return "tree"
    kfu.prepare_http(http, session_file, listing_route=tree_route, all_collections=True)


def resolve_record(http, metadata, assets):
    # Context is attached by shared discovery before reader resolution.
    metadata["collections"] = metadata.get("catalog_context", [])
    return kfu.resolve_record(http, metadata, assets)


def reuse_originals(http, manifest, summary):
    """Adopt matching verified originals from existing KFU source manifests."""
    from .core import check_space, valid_local

    wanted = {a["url"]: a for a in manifest.data["assets"].values()
              if a.get("current", True) and a["status"] != "unsupported"
              and not (a["status"] == "downloaded" and a.get("results")
                       and valid_local(manifest.directory, a["results"][-1]))}
    summary["imported_originals"] = 0
    for path in sorted(http.settings.artifacts_root.glob("kfu_*/manifest.json")):
        if not wanted:
            break
        http.budget.check()
        if path.parent == manifest.directory:
            continue
        # Read snapshots only; existing sources are never modified.
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as error:
            summary["errors"].append({"url": str(path), "stage": "local_reuse", "error": str(error)})
            continue
        if (not isinstance(data, dict) or data.get("schema_version") != 1
                or not str(data.get("source", "")).startswith("kfu_")):
            continue
        for previous in data.get("assets", {}).values():
            http.budget.check()
            asset = wanted.get(previous.get("url"))
            if (asset is None or not previous.get("results")
                    or asset.get("extension") != previous.get("extension")
                    or asset.get("source_version") != previous.get("source_version")):
                continue
            result = previous["results"][-1]
            if "source_version" in asset and result.get("source_version") != asset["source_version"]:
                continue
            if not valid_local(path.parent, result):
                continue
            source = path.parent / result["path"]
            target = manifest.directory / "files" / (result["sha256"] + asset["extension"])
            target.parent.mkdir(parents=True, exist_ok=True)
            check_space(manifest.directory, http.settings.disk_reserve_bytes, result["size"])
            temporary = target.with_name(uuid4().hex + ".part")
            try:
                try:
                    os.link(source, temporary)
                except OSError:
                    shutil.copyfile(source, temporary)
                if not valid_local(manifest.directory, {**result, "path": str(temporary.relative_to(manifest.directory))}):
                    raise ValueError("KFU original changed during local reuse.")
                with temporary.open("rb") as handle:
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            imported = copy.deepcopy(result)
            imported.update(id=uuid4().hex, observation_id=asset["observation_id"],
                            path=target.relative_to(manifest.directory).as_posix(),
                            imported_at=now(), imported_from={"source": data["source"],
                            "asset_id": previous["id"], "result_id": result["id"],
                            "observation_id": result["observation_id"]})
            asset["results"].append(imported)
            asset.update(status="downloaded", last_checked=now())
            if "source_version" in asset:
                asset["verified_source_version"] = asset["source_version"]
            asset.pop("last_error", None)
            summary["imported_originals"] += 1
            manifest.save()
            wanted.pop(asset["url"], None)


def download(http, manifest, summary, log, recheck):
    reuse_originals(http, manifest, summary)
    return kfu.download(http, manifest, summary, log, recheck, unit="file_or_publication")
