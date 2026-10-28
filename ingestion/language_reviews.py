"""Optional, auditable file-language reviews shared by source adapters."""

import copy
import json
import re

from .kfu import language_selection
from .network import InvalidDocument


def load(path, validate_url, label):
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("files"), dict):
        raise ValueError(f"{label} language-reviews.json requires version=1 and a files mapping.")
    for url, review in data["files"].items():
        validate_url(url)
        if (not isinstance(review, dict) or not re.fullmatch(r"[a-f0-9]{64}", str(review.get("sha256", "")))
                or not isinstance(review.get("languages"), list)
                or not all(isinstance(value, str) and value.strip() for value in review["languages"])
                or language_selection(review["languages"]) != "selected"
                or not all(isinstance(review.get(key), str) and review[key].strip() for key in ("reviewer", "reason"))):
            raise ValueError(f"Each {label} file review requires SHA-256, Tatar labels, reviewer and reason.")
    return data["files"]


def resolve(http, metadata, assets):
    for asset in assets:
        asset.update(language_review=None, source_version=None,
                     unsupported_code=asset["source_unsupported_code"],
                     unsupported_reason=asset["source_unsupported_reason"])
        review = http.language_reviews.get(asset["url"])
        if review and asset["unsupported_code"] in {"language_unknown", "language_excluded"}:
            asset.update(language_review=review, source_version=review["sha256"],
                         unsupported_code=None, unsupported_reason=None)
    metadata["language_reviews"] = [{**a["language_review"], "url": a["url"]} for a in assets if a.get("language_review")]
    metadata["attachments"] = [{key: a[key] for key in ("url", "label", "unsupported_code")} for a in assets]
    return metadata, assets


def refresh(http, manifest, parser_version, descriptor_keys):
    """Grant/withdraw reviews without a catalog rescan, preserving observations."""
    grouped = {}
    for asset in manifest.data["assets"].values():
        if asset.get("current", True):
            grouped.setdefault(asset.get("record_key", asset["record_url"]), []).append(asset)
    for key, record in list(manifest.data["records"].items()):
        http.budget.check()
        observation = record["observations"][-1]
        metadata = copy.deepcopy(observation["metadata"])
        current = grouped.get(key, [])
        assets = [{field: a[field] for field in descriptor_keys} for a in current]
        metadata, assets = resolve(http, metadata, assets)
        changed = (metadata != observation["metadata"] or observation["parser_version"] != parser_version
                   or any(any(a.get(field) != value for field, value in descriptor.items())
                          for a, descriptor in zip(current, assets)))
        if changed:
            manifest.observe(metadata, assets, parser_version, record_key=key)


def validate_acquisition(http, asset):
    review = asset.get("language_review")
    if review and review != http.language_reviews.get(asset["url"]):
        raise InvalidDocument("File language review changed or was withdrawn; refresh discovery before acquisition.")


def validate_acquired(asset, result):
    review = asset.get("language_review")
    if review and result["sha256"] != review["sha256"]:
        raise InvalidDocument("Downloaded document differs from its language-reviewed SHA-256; manual review is required.")
    return {"language_review_sha256": review["sha256"]} if review else {}
