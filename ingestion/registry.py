"""Ordered adapter registry; listing names never imports provider modules."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from importlib import import_module
from pathlib import Path


@dataclass(frozen=True)
class SourceDescriptor:
    module: str
    commands: tuple[str, ...] = ('discover', 'download', 'run', 'status', 'publish')
    modes: tuple[str, ...] = ('catalog',)
    formats: tuple[str, ...] = ('all',)
    targets: tuple[str, ...] = ('s3',)
    requires_session: bool = False
    recheck: bool = True
    maintenance: bool = False
    collection: bool = False
    guide: str | None = None


# Static navigation and capabilities never import provider implementations.
DESCRIPTORS = {name: SourceDescriptor(name) for name in (
    'milli_kitaphana', 'litres', 'common_crawl', 'magarif', 'tatarica',
    'darul_kutub', 'sarhaan', 'ftatarstan', 'dumrt', 'tuganzhir',
    'beznenmiras', 'miras_periodicals', 'magarif_vakyt', 'turuz', 'yazuchy',
    'nizgar', 'echovek', 'obuchalka', 'kazanutlary', 'tatkniga',
    'miras', 'commons', 'isxaki', 'internet_archive', 'kfu_repository',
    'kfu_dspace', 'tataroved', 'kfu_books', 'kfu_manuscripts', 'kfu_il',
    'kfu_azad_halyk', 'kfu_vakyt', 'kfu_shura', 'tatargalyame',
)}
for name in ('kfu_books', 'kfu_manuscripts', 'kfu_il', 'kfu_azad_halyk', 'kfu_shura'):
    DESCRIPTORS[name] = replace(DESCRIPTORS[name], module='kfu', collection=True)
DESCRIPTORS['kfu_manuscripts'] = replace(DESCRIPTORS['kfu_manuscripts'], guide='kfu-books')
DESCRIPTORS['milli_kitaphana'] = replace(
    DESCRIPTORS['milli_kitaphana'],
    commands=('discover', 'download', 'finalize', 'import-state', 'mark-existing-limited',
              'merge-index', 'publish', 'recover', 'run', 'split', 'status'),
    targets=('s3', 'yandex'), maintenance=True)
DESCRIPTORS['litres'] = replace(
    DESCRIPTORS['litres'],
    commands=('discover', 'download', 'finalize', 'import-state', 'metadata',
              'publish', 'review', 'run', 'status'),
    modes=('catalog', 'candidates', 'all'), formats=('all', 'pdf', 'text'),
    targets=('s3', 'yandex', 'hf', 's3-media'))
DESCRIPTORS['common_crawl'] = replace(
    DESCRIPTORS['common_crawl'], formats=('all', 'pdf'), targets=('s3', 'yandex'), recheck=False)
DESCRIPTORS['miras_periodicals'] = replace(DESCRIPTORS['miras_periodicals'], requires_session=True)
DESCRIPTORS['tatkniga'] = replace(
    DESCRIPTORS['tatkniga'], commands=('discover', 'download', 'finalize', 'publish', 'run', 'status'))
DESCRIPTORS['miras'] = replace(DESCRIPTORS['miras'], requires_session=True)


class _Sources(Mapping):
    def __init__(self):
        self._loaded = {}

    def __iter__(self):
        return iter(DESCRIPTORS)

    def __len__(self):
        return len(DESCRIPTORS)

    def __contains__(self, name):
        return name in DESCRIPTORS

    def __getitem__(self, name):
        descriptor = DESCRIPTORS[name]
        module_name = descriptor.module
        if name not in self._loaded:
            module = import_module("." + module_name, __package__)
            if descriptor.collection:
                adapter = module.CollectionAdapter()
            else:
                adapter = module
            self._loaded[name] = adapter
        return self._loaded[name]


SOURCES = _Sources()


class _Pilots(Mapping):
    def __iter__(self):
        return iter(("miras",))

    def __len__(self):
        return 1

    def __contains__(self, name):
        return name == "miras"

    def __getitem__(self, name):
        if name not in self:
            raise KeyError(name)
        return name


# Retain the diagnostic command without importing Miras during CLI startup.
PILOT_SOURCES = _Pilots()


def configured_adapter(source, settings):
    adapter = SOURCES[source]
    if DESCRIPTORS[source].collection:
        options = settings.source_options
        if not isinstance(options.get('collection_id'), str) or type(options.get('tatar_only')) is not bool:
            raise ValueError(f'Missing or invalid sources.{source}.collection_id / tatar_only')
        acquisition = {}
        if 'direct_files_only' in options:
            if type(options['direct_files_only']) is not bool:
                raise ValueError(f'sources.{source}.direct_files_only must be a boolean')
            acquisition['direct_files_only'] = options['direct_files_only']
        return type(adapter)(options['collection_id'], tatar_only=options['tatar_only'], **acquisition)
    return adapter


def source_locations(source):
    """Repository-relative navigation, without importing the selected adapter."""
    descriptor = DESCRIPTORS[source]
    module = descriptor.module
    root = Path(__file__).resolve().parents[1]
    guide = descriptor.guide or source.replace('_', '-')
    adapter_modules = {entry.module for entry in DESCRIPTORS.values()}
    return dict(adapter=f'ingestion/{module}.py',
                helpers=[str(path.relative_to(root)) for path in sorted(
                    (root / 'ingestion').glob(module + '_*.py'))
                         if path.stem not in adapter_modules],
                guide=f'docs/ingestion/{guide}.md', config=f'config/sources/{source}.yaml')
