"""Serializable, read-only listing requests shared by source adapters."""

from dataclasses import asdict, dataclass, field
import json


class CatalogChanged(ValueError):
    """The provider changed the catalog being enumerated; start a fresh scan."""


@dataclass
class PageRequest:
    url: str
    method: str = "GET"
    data: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)

    def dump(self):
        return asdict(self)

    def key(self):
        if self.method == "GET" and not self.data and not self.context:
            return self.url
        return json.dumps(self.dump(), sort_keys=True, ensure_ascii=False)


@dataclass
class ListingPage:
    records: list[str]
    following: list[PageRequest]
    entries: int = 0
    advertised: int | None = None
    validation: bool = False
    fingerprint: str | None = None
    detect_repeats: bool = False
    record_context: dict = field(default_factory=dict)
