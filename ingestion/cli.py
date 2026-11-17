import json
from pathlib import Path
from typing import Optional

import typer
from click import Choice

from .commands import CommandOptions, REVIEW_ACTIONS, option_choices, validate_capabilities
from .output import compact_result
from .registry import SOURCES, source_locations


app = typer.Typer(pretty_exceptions_show_locals=False, no_args_is_help=True, help="Discover documents and download originals locally.")
from .database_cli import app as database_app
app.add_typer(database_app, name="database")


@app.callback()
def main(ctx: typer.Context, config: Optional[Path] = typer.Option(None, "--config", help="Selected operational YAML file."),
         profile: Optional[Path] = typer.Option(None, "--profile", help="Public configuration overlay, e.g. config/scheduled.yaml."),
         summary_only: bool = typer.Option(False, "--summary-only", help="Print one compact JSON result and suppress progress; run details are in Postgres.")):
    ctx.obj = config
    ctx.meta["summary_only"] = summary_only
    ctx.meta["profile"] = profile
    if ctx.invoked_subcommand == 'database' and config is not None:
        from .config import read_configuration, resolve_environment
        from .database import configured_database
        try:
            data = read_configuration(config)
            database = resolve_environment(data.get('database', {}), 'database')
            if data.get('standalone') or database:
                ctx.with_resource(configured_database(database))
        except (ValueError, OSError) as error:
            fail(ctx, error, 'database')


def progress(ctx):
    return (lambda message: None) if ctx.meta.get("summary_only") else typer.echo


def emit_result(ctx, result, command, source=None, *, compact_default=False):
    compact = ctx.meta.get("summary_only", False)
    if compact:
        result = compact_result(result, command, source)
    formatting = {"separators": (",", ":")} if compact or compact_default else {"indent": 2}
    typer.echo(json.dumps(result, ensure_ascii=False, **formatting))


def fail(ctx, error, command, source=None):
    if ctx.meta.get("summary_only"):
        emit_result(ctx, {"error": str(error)}, command, source)
    else:
        typer.echo(f"Error: {error}", err=True)
    raise typer.Exit(1)


@app.command("sources")
def sources_command(ctx: typer.Context, details: bool = typer.Option(False, "--details"),
                    source: Optional[str] = typer.Option(None, "--source"),
                    symbols: bool = typer.Option(False, "--symbols", help="Include bounded definition/line maps; requires --source and implies --details."),
                    module: Optional[str] = typer.Option(None, "--module", help="Module stem or repository Python path; implies --symbols."),
                    symbol: Optional[str] = typer.Option(None, "--symbol", help="Case-sensitive definition name substring; implies --symbols.")):
    """List adapters implemented in the shared CLI."""
    if source is not None and source not in SOURCES:
        fail(ctx, ValueError(f"Unknown source: {source}"), "sources", source)
    navigation = symbols or module is not None or symbol is not None
    if navigation and source is None:
        fail(ctx, ValueError("Symbol navigation requires --source"), "sources")
    names = [source] if source else list(SOURCES)
    if details or navigation:
        from .commands import capabilities
        try:
            result = {name: {**capabilities(name), "locations": source_locations(
                name, symbols=navigation, module=module, symbol=symbol)} for name in names}
        except (OSError, SyntaxError, UnicodeError, ValueError) as error:
            fail(ctx, error, "sources", source)
        typer.echo(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return
    if ctx.meta.get("summary_only"):
        emit_result(ctx, {"sources": names}, "sources")
        return
    for name in names:
        typer.echo(name)


@app.command('configure')
def configure_command(source: str = typer.Option(..., '--source')):
    """Create a complete private source YAML without overwriting an existing file."""
    from .local_config import create_source_config
    try:
        typer.echo(str(create_source_config(source)))
    except (ValueError, OSError) as error:
        typer.echo(f'Error: {error}', err=True)
        raise typer.Exit(1)


@app.command("inspect")
def inspect_command(ctx: typer.Context, url: str = typer.Argument(..., help="Public page or document URL to inspect."),
                    output_dir: Path = typer.Option(Path("__artifacts/inspections"), "--output-dir"),
                    max_bytes: int = typer.Option(2 * 1024 * 1024, "--max-bytes", min=1024, max=2 * 1024 * 1024),
                    max_links: int = typer.Option(20, "--max-links", min=1, max=200),
                    probe_pdfs: int = typer.Option(0, "--probe-pdfs", min=0, max=10),
                    allow_external: bool = typer.Option(False, "--allow-external", help="Allow PDF probes and redirects outside the inspected page origin.")):
    """Save bounded public-page evidence and print concise JSON; no config required."""
    from .inspection import inspect
    try:
        result = inspect(url, output_dir, max_bytes=max_bytes, max_links=max_links,
                         probe_pdfs=probe_pdfs, allow_external=allow_external)
    except (ValueError, OSError) as error:
        fail(ctx, error, "inspect")
    emit_result(ctx, result, "inspect", compact_default=True)
    if not result["ok"]:
        raise typer.Exit(1)


@app.command()
def probe(ctx: typer.Context, source: str = typer.Option(..., "--source"),
          session_file: Optional[Path] = typer.Option(None, "--session-file", help="Legacy Miras session export; standalone YAML uses sources.miras.session.")):
    """Check Miras HTTP access with exported cookies and acquire one sample PDF."""
    from .registry import PILOT_SOURCES
    from .config import load_settings
    try:
        if source not in PILOT_SOURCES:
            raise ValueError(f"Unknown access pilot: {source}. Available: {', '.join(PILOT_SOURCES)}")
        settings = load_settings(ctx.obj, source)
        if settings.file_only and session_file is not None:
            raise ValueError('Store browser session credentials in sources.miras.session in the source YAML')
        session_file = session_file or settings.source_options.get('session')
        if session_file is None:
            raise ValueError('Set sources.miras.session in the source configuration')
        from .miras_session import run_cookie_probe
        result = run_cookie_probe(settings, session_file, log=progress(ctx))
        emit_result(ctx, result, "probe", source)
    except (ValueError, OSError, RuntimeError, ImportError) as error:
        fail(ctx, error, "probe", source)
    if not result["success"]:
        raise typer.Exit(1)


def execute(ctx, command, source, limit=None, max_pages=None, recheck=False, session_file=None, mode="catalog", format="all", action=None, target=None, from_path=None, limited=False, index_name=None, maintenance=None):
    try:
        if source not in SOURCES:
            raise ValueError(f"Unknown source: {source}. Available: {', '.join(SOURCES)}")
        options = CommandOptions(mode=mode, format=format, target=target or "s3", action=action,
                                 from_path=from_path, limited=limited, index_name=index_name,
                                 maintenance=maintenance or {}, recheck=recheck, session_file=session_file)
        validate_capabilities(source, command, options)
        from .config import load_settings
        from .core import restricted_settings, run
        settings = restricted_settings(load_settings(ctx.obj, source, profile=ctx.meta.get('profile')), limit, max_pages)
        if settings.file_only and session_file is not None:
            raise ValueError('Store browser session credentials in sources.<source>.session in the source YAML')
        session_file = session_file or settings.source_options.get('session')
        from dataclasses import replace
        options = replace(options, session_file=session_file)
        result = run(settings, source, command, options=options, log=progress(ctx))
        from .automation import job_summary
        job_summary(result, source, command)
        emit_result(ctx, result, command, source)
    except (ValueError, OSError, RuntimeError, ImportError) as error:
        from .automation import job_summary
        job_summary({'errors': [{}]}, source, command)
        fail(ctx, error, command, source)
    if result.get("errors"):
        raise typer.Exit(1)


@app.command()
def discover(ctx: typer.Context, source: str = typer.Option(..., "--source"),
             max_pages: Optional[int] = typer.Option(None, "--max-pages"),
             mode: str = typer.Option("catalog", "--mode", click_type=Choice(option_choices('modes')), help="Discovery mode."),
             session_file: Optional[Path] = typer.Option(None, "--session-file", help="Browser session export for miras or miras_periodicals.")):
    """Discover archive records and attachments without downloading originals."""
    execute(ctx, "discover", source, max_pages=max_pages, session_file=session_file, mode=mode)


@app.command()
def download(ctx: typer.Context, source: str = typer.Option(..., "--source"),
             limit: Optional[int] = typer.Option(None, "--limit", help="Maximum source items within the configured cap."),
             format: str = typer.Option("all", "--format", click_type=Choice(option_choices('formats')), help="Document format."),
             limited: bool = typer.Option(False, "--limited"),
             index_name: Optional[str] = typer.Option(None, "--index-name"),
             recheck: bool = typer.Option(False, "--recheck", help="Also revalidate completed downloads."),
             session_file: Optional[Path] = typer.Option(None, "--session-file", help="Browser session export for miras or miras_periodicals.")):
    """Download original inputs; staged sources assemble outputs during finalize."""
    execute(ctx, "download", source, limit=limit, recheck=recheck, session_file=session_file, format=format, limited=limited, index_name=index_name)


@app.command("run")
def run_command(ctx: typer.Context, source: str = typer.Option(..., "--source"),
                limit: Optional[int] = typer.Option(None, "--limit", help="Maximum source items within the configured cap."),
                max_pages: Optional[int] = typer.Option(None, "--max-pages"),
                recheck: bool = typer.Option(False, "--recheck"),
                session_file: Optional[Path] = typer.Option(None, "--session-file", help="Browser session export for miras or miras_periodicals.")):
    """Discover, then download eligible files within the same run budget."""
    execute(ctx, "run", source, limit=limit, max_pages=max_pages, recheck=recheck, session_file=session_file)


@app.command()
def status(ctx: typer.Context, source: str = typer.Option(..., "--source")):
    """Read manifest counts without network requests or artifact writes."""
    execute(ctx, "status", source)


@app.command()
def finalize(ctx: typer.Context, source: str = typer.Option(..., "--source"),
             limit: Optional[int] = typer.Option(None, "--limit", help="Maximum outputs needing finalization; verified Tatkniga PDFs are skipped.")):
    """Build local outputs from verified downloaded inputs, without network access."""
    execute(ctx, "finalize", source, limit=limit)


@app.command()
def metadata(ctx: typer.Context, source: str = typer.Option(..., "--source")):
    """Refresh bibliographic metadata."""
    execute(ctx, "metadata", source)


@app.command()
def review(ctx: typer.Context, source: str = typer.Option(..., "--source"),
           action: str = typer.Option(..., "--action", click_type=Choice(REVIEW_ACTIONS))):
    """Export or sync TSV review decisions, or import accepted candidates."""
    execute(ctx, "review", source, action=action)


@app.command()
def publish(ctx: typer.Context, source: str = typer.Option(..., "--source"),
            target: str = typer.Option("s3", "--target", click_type=Choice(option_choices('targets')))):
    """Publish finalized outputs to an explicitly selected destination."""
    execute(ctx, "publish", source, target=target)


@app.command("import-state")
def import_state(ctx: typer.Context, source: str = typer.Option(..., "--source"),
                 from_path: Path = typer.Option(..., "--from", exists=True, file_okay=False)):
    """Import legacy state without modifying its source directory."""
    execute(ctx, "import-state", source, from_path=from_path)


@app.command()
def split(ctx: typer.Context, source: str = typer.Option(..., "--source"), parts: int = typer.Option(..., "--parts", "-p", min=1), dest: Optional[str] = None, prefix: str = "index-part"):
    """Store Milli worker selections in Postgres; --dest also exports JSON."""
    execute(ctx, "split", source, maintenance=dict(parts=parts, dest=dest, prefix=prefix))


@app.command("merge-index")
def merge_index(ctx: typer.Context, path: Path, source: str = typer.Option(..., "--source")):
    execute(ctx, "merge-index", source, maintenance=dict(path=str(path)))


@app.command()
def recover(ctx: typer.Context, source: str = typer.Option(..., "--source"), report: str = typer.Option("default", help="Postgres recovery journal name."), workers: Optional[int] = typer.Option(None, min=1), download: bool = False, retry_failed: bool = False, download_workers: Optional[int] = typer.Option(None, min=1)):
    execute(ctx, "recover", source, maintenance=dict(report_path=report, workers=workers, download=download, retry_failed=retry_failed, download_workers=download_workers))


@app.command("mark-existing-limited")
def mark_existing_limited(ctx: typer.Context, source: str = typer.Option(..., "--source")):
    execute(ctx, "mark-existing-limited", source)


from .source_cli import register_source_commands
register_source_commands(app, run_command)
