from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from .registry import PILOT_SOURCES, SOURCES


@dataclass(frozen=True)
class Settings:
    artifacts_root: Path
    archive_url: str
    max_pages: int
    max_items: int
    max_download_bytes: int
    max_file_bytes: int
    disk_reserve_bytes: int
    soft_deadline_seconds: float
    connect_timeout_seconds: float
    read_timeout_seconds: float
    pacing_seconds: float
    retry_attempts: int


def load_settings(path: Path | None, source: str = "magarif") -> Settings:
    if source not in SOURCES and source not in PILOT_SOURCES:
        raise ValueError(f"Unknown source: {source}")
    expected_url = SOURCES[source].ARCHIVE_URL if source in SOURCES else PILOT_SOURCES[source]
    if path is None:
        raise ValueError("Select an operational YAML file with --config; examples are never loaded automatically.")
    path = path.expanduser().resolve()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML configuration: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a YAML mapping.")

    def section(name):
        value = data.get(name)
        if not isinstance(value, dict):
            raise ValueError(f"Missing configuration mapping: {name}")
        return value

    limits, network, sources = section("limits"), section("network"), section("sources")
    selected = sources.get(source)
    if not isinstance(selected, dict):
        raise ValueError(f"Missing sources.{source} configuration.")
    archive_url = selected.get("archive_url")
    if not isinstance(archive_url, str):
        raise ValueError(f"sources.{source}.archive_url must be a URL.")
    parsed = urlsplit(archive_url)
    if (archive_url.rstrip("/") != expected_url or parsed.query or parsed.fragment):
        raise ValueError(f"{source}.archive_url must be {expected_url}")
    root = data.get("artifacts_root")
    if not isinstance(root, str) or not root.strip():
        raise ValueError("artifacts_root must be a nonempty path.")
    root = Path(root).expanduser()
    if not root.is_absolute():
        root = path.parent / root

    def number(mapping, key, integer=False):
        value = mapping.get(key)
        valid = type(value) is int if integer else type(value) in (int, float)
        if not valid or not 0 < value < float("inf"):
            raise ValueError(f"{key} must be a positive {'integer' if integer else 'finite number'}.")
        return value

    return Settings(
        artifacts_root=root.resolve(), archive_url=archive_url.rstrip("/"),
        **{key: number(limits, key, True) for key in (
            "max_pages", "max_items", "max_download_bytes", "max_file_bytes", "disk_reserve_bytes")},
        soft_deadline_seconds=number(limits, "soft_deadline_seconds"),
        **{key: number(network, key) for key in (
            "connect_timeout_seconds", "read_timeout_seconds", "pacing_seconds")},
        retry_attempts=number(network, "retry_attempts", True),
    )
