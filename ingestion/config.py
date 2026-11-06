from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from .registry import PILOT_SOURCES, SOURCES
import os


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
    source_options: dict = field(default_factory=dict, repr=False)
    s3: dict = field(default_factory=dict, repr=False)
    max_derived_pdf_bytes: int = field(kw_only=True)
    user_agent: str = field(kw_only=True)


def load_settings(path: Path | None, source: str = "magarif") -> Settings:
    if source not in SOURCES and source not in PILOT_SOURCES:
        raise ValueError(f"Unknown source: {source}")
    if path is None:
        raise ValueError("Select an operational YAML file with --config; examples are never loaded automatically.")
    path = path.expanduser().resolve()
    data = read_configuration(path)

    def section(name):
        value = data.get(name)
        if not isinstance(value, dict):
            raise ValueError(f"Missing configuration mapping: {name}")
        return value

    sources = section("sources")
    selected = sources.get(source)
    data = {k: (deferred_environment(v, k) if k == "storage" else resolve_environment(v, k)) for k, v in data.items() if k != "sources"}
    limits, network = data.get("limits"), data.get("network")
    if not isinstance(limits, dict) or not isinstance(network, dict):
        raise ValueError("limits and network must be configuration mappings")
    if not isinstance(selected, dict):
        raise ValueError(f"Missing sources.{source} configuration.")
    archive_url = selected.get("archive_url")
    if not isinstance(archive_url, str):
        raise ValueError(f"sources.{source}.archive_url must be a URL.")
    parsed = urlsplit(archive_url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.fragment
            or any(ord(c) < 32 for c in archive_url)):
        raise ValueError(f"sources.{source}.archive_url must be an HTTP(S) URL without credentials or fragment.")
    parsed.port
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

    if not isinstance(network.get("user_agent"), str) or not network["user_agent"].strip():
        raise ValueError("network.user_agent must be a nonempty string")
    return Settings(
        user_agent=network["user_agent"],
        artifacts_root=root.resolve(), archive_url=archive_url,
        s3=(data.get("storage") or {}).get("s3", {}),
        source_options=deferred_environment({**selected, "_config_dir": str(path.parent), "_source": source}, f"sources.{source}"),
        **{key: number(limits, key, True) for key in (
            "max_pages", "max_items", "max_download_bytes", "max_file_bytes", "disk_reserve_bytes")},
        soft_deadline_seconds=number(limits, "soft_deadline_seconds"),
        **{key: number(network, key) for key in (
            "connect_timeout_seconds", "read_timeout_seconds", "pacing_seconds")},
        retry_attempts=number(network, "retry_attempts", True),
        max_derived_pdf_bytes=number(
            {"max_derived_pdf_bytes": limits.get("max_derived_pdf_bytes")},
            "max_derived_pdf_bytes", True),
    )


def merge_configuration(base, override):
    result = dict(base)
    for key, value in override.items():
        result[key] = merge_configuration(result[key], value) if isinstance(result.get(key), dict) and isinstance(value, dict) else value
    return result


def read_configuration(path, ancestors=()):
    path = Path(path).expanduser().resolve()
    if path in ancestors:
        raise ValueError(f"Configuration inheritance cycle at {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError:
        raise ValueError(f"Invalid YAML configuration in {path}") from None
    if not isinstance(data, dict):
        raise ValueError(f"Configuration must be a YAML mapping: {path}")
    parent = data.pop("extends", None)
    if parent is not None:
        if not isinstance(parent, str) or not parent.strip():
            raise ValueError("extends must be a nonempty file path")
        data = merge_configuration(read_configuration(path.parent / Path(parent).expanduser(), (*ancestors, path)), data)
    return data


def resolve_environment(value, key="configuration"):
    if isinstance(value, dict):
        if set(value) == {"env"}:
            name = value["env"]
            if not isinstance(name, str) or not name or name not in os.environ:
                raise ValueError(f"Missing environment variable for {key}: {name}")
            return os.environ[name]
        return {k: resolve_environment(v, f"{key}.{k}") for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_environment(v, f"{key}[{i}]") for i, v in enumerate(value)]
    return value


class EnvironmentMapping(dict):
    """Resolve credential references only when their stage reads them."""
    def __getitem__(self, key):
        value = super().__getitem__(key)
        return resolve_environment(value, self._key + '.' + str(key)) if isinstance(value, dict) and set(value) == {'env'} else value

    def get(self, key, default=None):
        return self[key] if key in self else default


def deferred_environment(value, key):
    if isinstance(value, dict):
        if set(value) == {'env'}:
            return value
        result = EnvironmentMapping({k: deferred_environment(v, key + '.' + str(k)) for k, v in value.items()})
        result._key = key
        return result
    if isinstance(value, list):
        return [resolve_environment(v, f'{key}[{i}]') for i, v in enumerate(value)]
    return value
