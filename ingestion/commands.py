"""Source capabilities and invocation options, separate from operational configuration."""
from dataclasses import dataclass, field
from pathlib import Path
from .registry import SOURCES, DESCRIPTORS

REVIEW_ACTIONS = ('export', 'sync', 'import')


def option_choices(name):
    return tuple(dict.fromkeys(value for descriptor in DESCRIPTORS.values()
                               for value in getattr(descriptor, name)))


@dataclass(frozen=True)
class CommandOptions:
    mode: str = 'catalog'
    format: str = 'all'
    target: str = 's3'
    action: str | None = None
    from_path: Path | None = None
    limited: bool = False
    index_name: str | None = None
    maintenance: dict = field(default_factory=dict)
    recheck: bool = False
    session_file: Path | dict | None = field(default=None, repr=False)


def capabilities(source):
    descriptor = DESCRIPTORS[source]
    return dict(commands=sorted(descriptor.commands), modes=list(descriptor.modes),
                formats=list(descriptor.formats), targets=list(descriptor.targets),
                requires_session=descriptor.requires_session,
                recheck=descriptor.recheck, maintenance=descriptor.maintenance)


def validate_capabilities(source, command, options):
    """Reject unsupported invocations without reading operational configuration."""
    if source not in SOURCES:
        raise ValueError(f'Unknown source: {source}')
    cap = capabilities(source)
    for label, value, allowed in (('stage', command, cap['commands']),
                                  ('--mode', options.mode, cap['modes']),
                                  ('--format', options.format, cap['formats'])):
        if value not in allowed:
            raise ValueError(f'{source} does not support {label} {value!r}. Allowed: {", ".join(allowed)}')
    if command == 'publish' and options.target not in cap['targets']:
        raise ValueError(f'{source} does not support --target {options.target!r}. Allowed: {", ".join(cap["targets"])}')
    if options.recheck and not cap['recheck']:
        raise ValueError(f'{source} does not support --recheck')
    if options.session_file is not None and not cap['requires_session']:
        raise ValueError(f'{source} does not support --session-file')
    if not cap['maintenance'] and (options.limited or options.index_name or options.maintenance):
        raise ValueError('Selected options require --source milli_kitaphana')
    if command == 'review' and options.action not in REVIEW_ACTIONS:
        raise ValueError(f'{source} does not support --action {options.action!r}. Allowed: {", ".join(REVIEW_ACTIONS)}')
    if command == 'import-state' and options.from_path is None:
        raise ValueError('Import requires --from')


def validate(source, command, options):
    validate_capabilities(source, command, options)
    if (DESCRIPTORS[source].requires_session and command != 'status'
            and not (command == 'publish' and options.target == 's3') and options.session_file is None):
        raise ValueError(f'{source} requires --session-file')
