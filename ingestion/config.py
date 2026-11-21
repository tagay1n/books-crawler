from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from .registry import PILOT_SOURCES, SOURCES
import os
import base64


@dataclass(frozen=True)
class Settings:
    artifacts_root: Path
    archive_url: str
    max_pages: int | float
    max_items: int | float
    max_download_bytes: int | float
    max_file_bytes: int | float
    disk_reserve_bytes: int
    soft_deadline_seconds: float
    connect_timeout_seconds: float
    read_timeout_seconds: float
    pacing_seconds: float
    retry_attempts: int
    source_options: dict = field(default_factory=dict, repr=False)
    s3: dict = field(default_factory=dict, repr=False)
    max_derived_pdf_bytes: int | float = field(kw_only=True)
    user_agent: str = field(kw_only=True)
    discovery_deadline_seconds: float | None = None
    publication_grace_seconds: float = 0
    database: dict = field(default_factory=dict, repr=False)
    file_only: bool = False
    additional_ca_certificates: str | None = None


def load_settings(path: Path | None, source: str = "magarif", *, profile: Path | None = None) -> Settings:
    if source not in SOURCES and source not in PILOT_SOURCES:
        raise ValueError(f"Unknown source: {source}")
    if path is None:
        raise ValueError("Select an operational YAML file with --config; examples are never loaded automatically.")
    path = path.expanduser().resolve()
    data = read_configuration(path)
    file_only = data.get('standalone') is True
    if file_only:
        database = data.get('database')
        if not isinstance(database, dict):
            raise ValueError(f'Set the database mapping in {path}')
        url = database.get('url')
        if url is not None and (not isinstance(url, str) or not url.strip() or url == '<SET ME>'):
            raise ValueError(f'Set database.url to a PostgreSQL URL in {path}')
    if file_only and profile is not None:
        raise ValueError('Standalone source configuration cannot use --profile')
    if profile is not None:
        profile = profile.expanduser().resolve()
        overlay = read_configuration(profile)
        data = merge_configuration(data, overlay)
        if 'artifacts_root' in overlay:
            data['artifacts_root'] = str(profile.parent / overlay['artifacts_root'])

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
    if 'direct_files_only' in selected and type(selected['direct_files_only']) is not bool:
        raise ValueError(f'sources.{source}.direct_files_only must be a boolean')
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
        # Milli supports explicit null workload caps. Other sources retain their
        # existing positive-number contract. Infinity keeps shared comparisons
        # and budget accounting intact without inventing a very large cap.
        if source == 'milli_kitaphana' and mapping is limits and key in limits and value is None:
            if key == 'disk_reserve_bytes':
                return 0
            if key == 'discovery_deadline_seconds':
                return None
            if key in {'max_pages', 'max_items', 'max_download_bytes', 'max_file_bytes',
                       'max_derived_pdf_bytes', 'soft_deadline_seconds'}:
                return float('inf')
        valid = type(value) is int if integer else type(value) in (int, float)
        if not valid or not 0 < value < float("inf"):
            raise ValueError(f"{key} must be a positive {'integer' if integer else 'finite number'}.")
        return value

    if not isinstance(network.get("user_agent"), str) or not network["user_agent"].strip():
        raise ValueError("network.user_agent must be a nonempty string")
    additional_ca = network.get('additional_ca_certificates')
    if additional_ca is not None and (not isinstance(additional_ca, str) or not additional_ca.strip()):
        raise ValueError('network.additional_ca_certificates must contain PEM certificates')
    return Settings(
        additional_ca_certificates=additional_ca,
        discovery_deadline_seconds=(number(limits, 'discovery_deadline_seconds')
                                    if 'discovery_deadline_seconds' in limits else None),
        publication_grace_seconds=(number(limits, 'publication_grace_seconds')
                                   if 'publication_grace_seconds' in limits else 0),
        user_agent=network["user_agent"],
        artifacts_root=root.resolve(), archive_url=archive_url,
        database=data.get('database', {}), file_only=file_only,
        s3=(data.get("storage") or {}).get("s3", {}),
        source_options=deferred_environment({**selected, "_config_dir": str(path.parent), "_source": source}, f"sources.{source}"),
        **{key: number(limits, key, True) for key in (
            "max_pages", "max_items", "max_download_bytes", "max_file_bytes", "disk_reserve_bytes")},
        soft_deadline_seconds=number(limits, "soft_deadline_seconds"),
        **{key: number(network, key) for key in (
            "connect_timeout_seconds", "read_timeout_seconds", "pacing_seconds")},
        retry_attempts=number(network, "retry_attempts", True),
        max_derived_pdf_bytes=number(limits, "max_derived_pdf_bytes", True),
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
    if data.get('standalone') is True:
        if 'extends' in data:
            raise ValueError(f'Standalone configuration cannot use extends: {path}')
        def check(value, key):
            if isinstance(value, dict):
                if set(value) == {'env'}:
                    raise ValueError(f'Set {key} directly in {path}; environment references are disabled')
                for name, child in value.items():
                    check(child, f'{key}.{name}')
            elif isinstance(value, list):
                for child in value:
                    check(child, key)
        check(data, 'configuration')
    parent = data.pop("extends", None)
    if parent is not None:
        if not isinstance(parent, str) or not parent.strip():
            raise ValueError("extends must be a nonempty file path")
        data = merge_configuration(read_configuration(path.parent / Path(parent).expanduser(), (*ancestors, path)), data)
    return data


def resolve_environment(value, key="configuration"):
    if isinstance(value, dict):
        if set(value) == {'base64'}:
            try:
                return base64.b64decode(value['base64'], validate=True)
            except (ValueError, TypeError):
                raise ValueError(f'Set {key}.base64 to a valid base64-encoded value in the source YAML') from None
        if set(value) == {"env"}:
            name = value["env"]
            if not isinstance(name, str) or not name or name not in os.environ:
                raise ValueError(f"Missing environment variable for {key}: {name}")
            return os.environ[name]
        return {k: resolve_environment(v, f"{key}.{k}") for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_environment(v, f"{key}[{i}]") for i, v in enumerate(value)]
    return value


def load_database_configuration(path=None, *, source=None):
    """Select database settings without loading acquisition or publication settings."""
    if path is None and source in SOURCES:
        from .local_config import source_config_path
        local = source_config_path(source)
        if local.exists():
            path = local
    if path is None:
        return None
    data = read_configuration(path)
    database = resolve_environment(data.get('database', {}), 'database')
    if not isinstance(database, dict):
        raise ValueError('Database configuration must be a mapping')
    url = database.get('url')
    if url is not None and (not isinstance(url, str) or not url.strip() or url == '<SET ME>'):
        raise ValueError('Set database.url to a PostgreSQL URL in the source configuration file')
    return database if data.get('standalone') is True or database else None


class EnvironmentMapping(dict):
    """Resolve credential references only when their stage reads them."""
    def __getitem__(self, key):
        value = super().__getitem__(key)
        return resolve_environment(value, self._key + '.' + str(key)) if isinstance(value, dict) and set(value) in ({'env'}, {'base64'}) else value

    def get(self, key, default=None):
        return self[key] if key in self else default


def deferred_environment(value, key):
    if isinstance(value, dict):
        if set(value) in ({'env'}, {'base64'}):
            return value
        result = EnvironmentMapping({k: deferred_environment(v, key + '.' + str(k)) for k, v in value.items()})
        result._key = key
        return result
    if isinstance(value, list):
        return [resolve_environment(v, f'{key}[{i}]') for i, v in enumerate(value)]
    return value
