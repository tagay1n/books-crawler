"""Source-first shortcuts backed by the shared CLI command handlers."""

from functools import wraps
from inspect import signature
from copy import copy
from pathlib import Path
from typing import Optional

import typer
from click import Choice
from typer.models import OptionInfo

from .registry import DESCRIPTORS, PILOT_SOURCES


def _bind_source(callback, source):
    descriptor = DESCRIPTORS[source]
    original = signature(callback)
    defaults = {'source': source} if 'source' in original.parameters else {}
    parameters = []
    supported = {'session_file': descriptor.requires_session, 'recheck': descriptor.recheck,
                 'limited': descriptor.maintenance, 'index_name': descriptor.maintenance}
    choices = {'mode': descriptor.modes, 'format': descriptor.formats, 'target': descriptor.targets}
    for name, parameter in original.parameters.items():
        if name == 'source':
            continue
        if not supported.get(name, True):
            defaults[name] = parameter.default.default
            continue
        if name in choices and isinstance(parameter.default, OptionInfo):
            option = copy(parameter.default)
            option.click_type = Choice(choices[name])
            option.help = f'Allowed {name} for {source}.'
            parameter = parameter.replace(default=option)
        parameters.append(parameter)

    @wraps(callback)
    def bound(*args, **kwargs):
        return callback(*args, **{**kwargs, **defaults})

    bound.__signature__ = original.replace(parameters=parameters)
    return bound


def _source_callback(source, run_command):
    def source_main(
        ctx: typer.Context,
        config: Optional[Path] = typer.Option(None, "--config", help="Override this source's operational YAML."),
        profile: Optional[Path] = typer.Option(None, "--profile", help="Public configuration overlay."),
        summary_only: Optional[bool] = typer.Option(None, "--summary-only", help="Print one compact JSON result."),
        limit: Optional[int] = typer.Option(None, "--limit", help="Item limit for the default run."),
        max_pages: Optional[int] = typer.Option(None, "--max-pages", help="Page limit for the default run."),
        recheck: bool = typer.Option(False, "--recheck", help="Revalidate completed downloads in the default run."),
        session_file: Optional[Path] = typer.Option(None, "--session-file", help="Browser session export for Miras sources."),
    ):
        ctx.obj = config if config is not None else ctx.obj
        if ctx.obj is None:
            ctx.obj = Path(__file__).resolve().parents[1] / "config" / "sources" / f"{source}.yaml"
        if profile is not None:
            ctx.meta["profile"] = profile
        if summary_only is not None:
            ctx.meta["summary_only"] = summary_only
        if ctx.invoked_subcommand is None:
            run_command(ctx, source=source, limit=limit, max_pages=max_pages,
                        recheck=recheck, session_file=session_file)
        elif limit is not None or max_pages is not None or recheck or session_file is not None:
            raise typer.BadParameter("Put stage options after the stage name, or omit the stage to run the pipeline.")

    return _bind_source(source_main, source)


def register_source_commands(app, run_command):
    # Capture only the shared stage commands before adding source groups.
    commands = {command.name or command.callback.__name__.replace("_", "-"): command
                for command in app.registered_commands}
    for source, descriptor in DESCRIPTORS.items():
        source_app = typer.Typer(
            invoke_without_command=True, no_args_is_help=False,
            pretty_exceptions_show_locals=False,
            help=f"Run {source} using config/sources/{source}.yaml, or select a stage.",
        )
        source_app.callback()(_source_callback(source, run_command))
        stages = (*descriptor.commands, "probe") if source in PILOT_SOURCES else descriptor.commands
        for stage in stages:
            command = commands[stage]
            source_app.command(stage, help=command.help)(_bind_source(command.callback, source))
        app.add_typer(source_app, name=source)
