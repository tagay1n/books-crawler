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
        payload = self.dump()
        # Tree adapters carry large resume snapshots that do not identify a request.
        # Opt in explicitly; existing adapters retain their complete-context keys.
        if "_request_identity" in self.context:
            payload["context"] = self.context["_request_identity"]
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)


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
