from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import yaml


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


def load_settings(path: Path | None) -> Settings:
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
    magarif = sources.get("magarif")
    if not isinstance(magarif, dict):
        raise ValueError("Missing sources.magarif configuration.")
    archive_url = magarif.get("archive_url")
    if not isinstance(archive_url, str):
        raise ValueError("sources.magarif.archive_url must be a URL.")
    parsed = urlsplit(archive_url)
    if (parsed.scheme != "https" or parsed.netloc != "magarif-uku.ru"
            or parsed.path.rstrip("/") != "/documents" or parsed.query or parsed.fragment):
        raise ValueError("magarif.archive_url must be https://magarif-uku.ru/documents")
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
