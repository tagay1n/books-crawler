"""Source capabilities and invocation options, separate from operational configuration."""
from dataclasses import dataclass, field
from pathlib import Path
from .registry import SOURCES, DESCRIPTORS


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
    session_file: Path | None = None


def capabilities(source):
    descriptor = DESCRIPTORS[source]
    return dict(commands=sorted(descriptor.commands), modes=list(descriptor.modes),
                formats=list(descriptor.formats), targets=list(descriptor.targets),
                requires_session=descriptor.requires_session,
                recheck=descriptor.recheck, maintenance=descriptor.maintenance)


def validate(source, command, options):
    if source not in SOURCES:
        raise ValueError(f'Unknown source: {source}')
    cap = capabilities(source)
    if command not in cap['commands'] or options.mode not in cap['modes'] or options.format not in cap['formats']:
        raise ValueError(f'{source} does not implement the selected stage or option')
    if command == 'publish' and options.target not in cap['targets']:
        raise ValueError(f'{source} does not support publication target {options.target}')
    if options.recheck and not cap['recheck']:
        raise ValueError(f'{source} does not support --recheck')
    if options.session_file is not None and not cap['requires_session']:
        raise ValueError(f'{source} does not support --session-file')
    if cap['requires_session'] and command != 'status' and not (command == 'publish' and options.target == 's3') and options.session_file is None:
        raise ValueError(f'{source} requires --session-file')
    if not cap['maintenance'] and (options.limited or options.index_name or options.maintenance):
        raise ValueError('Selected options require --source milli_kitaphana')
    if command == 'review' and options.action not in {'export', 'sync', 'import'}:
        raise ValueError('Review action must be export, sync, or import')
    if command == 'import-state' and options.from_path is None:
        raise ValueError('Import requires --from')
