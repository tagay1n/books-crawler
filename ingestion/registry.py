"""Ordered adapter registry; listing names never imports provider modules."""

from collections.abc import Mapping
from importlib import import_module


_MODULES = {name: name for name in (
    "magarif", "tatarica", "darul_kutub", "sarhaan", "ftatarstan", "dumrt", "tuganzhir",
    "beznenmiras", "miras_periodicals", "magarif_vakyt", "turuz", "yazuchy", "nizgar",
    "echovek", "obuchalka", "kazanutlary", "tatkniga", "miras", "commons", "isxaki",
    "internet_archive", "kfu_repository", "kfu_dspace", "tataroved", "kfu_books",
    "kfu_manuscripts", "kfu_il", "kfu_azad_halyk", "kfu_vakyt", "kfu_shura", "tatargalyame",
)}
_COLLECTIONS = {"kfu_books": ("27574", False), "kfu_manuscripts": ("18503", False),
                "kfu_il": ("28060", True), "kfu_azad_halyk": ("27528", True),
                "kfu_shura": ("25046", True)}
_MODULES.update({name: "kfu" for name in _COLLECTIONS})


class _Sources(Mapping):
    def __init__(self):
        self._loaded = {}

    def __iter__(self):
        return iter(_MODULES)

    def __len__(self):
        return len(_MODULES)

    def __contains__(self, name):
        return name in _MODULES

    def __getitem__(self, name):
        module_name = _MODULES[name]
        if name not in self._loaded:
            module = import_module("." + module_name, __package__)
            if name in _COLLECTIONS:
                collection_id, tatar_only = _COLLECTIONS[name]
                adapter = module.CollectionAdapter(collection_id, tatar_only=tatar_only)
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
        return SOURCES[name].ARCHIVE_URL


# Retain the diagnostic command without importing Miras during CLI startup.
PILOT_SOURCES = _Pilots()
