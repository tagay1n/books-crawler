import json
from pathlib import Path
from typing import Optional

import typer

from .config import load_settings
from .core import SOURCES, restricted_settings, run


app = typer.Typer(no_args_is_help=True, help="Discover documents and download originals locally.")


@app.callback()
def main(ctx: typer.Context, config: Optional[Path] = typer.Option(None, "--config", help="Selected operational YAML file.")):
    ctx.obj = config


@app.command("sources")
def sources_command():
    """List adapters implemented in the shared CLI."""
    for source in SOURCES:
        typer.echo(source)


@app.command("inspect")
def inspect_command(url: str = typer.Argument(..., help="Public page or document URL to inspect."),
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
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    if not result["ok"]:
        raise typer.Exit(1)


@app.command()
def probe(ctx: typer.Context, source: str = typer.Option(..., "--source"),
          session_file: Path = typer.Option(..., "--session-file", help="Miras-only cookie and user-agent JSON from your verified browser.")):
    """Check Miras HTTP access with exported cookies and acquire one sample PDF."""
    from .registry import PILOT_SOURCES
    try:
        if source not in PILOT_SOURCES:
            raise ValueError(f"Unknown access pilot: {source}. Available: {', '.join(PILOT_SOURCES)}")
        settings = load_settings(ctx.obj, source)
        from .miras_session import run_cookie_probe
        result = run_cookie_probe(settings, session_file, log=typer.echo)
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, RuntimeError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)
    if not result["success"]:
        raise typer.Exit(1)


def execute(ctx, command, source, limit=None, max_pages=None, recheck=False, session_file=None):
    try:
        if source not in SOURCES:
            raise ValueError(f"Unknown source: {source}. Available: {', '.join(SOURCES)}")
        settings = restricted_settings(load_settings(ctx.obj, source), limit, max_pages)
        result = run(settings, source, command, recheck=recheck, session_file=session_file, log=typer.echo)
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, RuntimeError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)
    if result.get("errors"):
        raise typer.Exit(1)


@app.command()
def discover(ctx: typer.Context, source: str = typer.Option(..., "--source"),
             max_pages: Optional[int] = typer.Option(None, "--max-pages"),
             session_file: Optional[Path] = typer.Option(None, "--session-file", help="Browser session export for miras or miras_periodicals.")):
    """Discover archive records and attachments without downloading originals."""
    execute(ctx, "discover", source, max_pages=max_pages, session_file=session_file)


@app.command()
def download(ctx: typer.Context, source: str = typer.Option(..., "--source"),
             limit: Optional[int] = typer.Option(None, "--limit", help="Maximum files; whole issues for kazanutlary, files/publications for tatkniga and KFU."),
             recheck: bool = typer.Option(False, "--recheck", help="Also revalidate completed downloads."),
             session_file: Optional[Path] = typer.Option(None, "--session-file", help="Browser session export for miras or miras_periodicals.")):
    """Download committed local work; retry failed or missing originals."""
    execute(ctx, "download", source, limit=limit, recheck=recheck, session_file=session_file)


@app.command("run")
def run_command(ctx: typer.Context, source: str = typer.Option(..., "--source"),
                limit: Optional[int] = typer.Option(None, "--limit", help="Maximum files; whole issues for kazanutlary, files/publications for tatkniga and KFU."),
                max_pages: Optional[int] = typer.Option(None, "--max-pages"),
                recheck: bool = typer.Option(False, "--recheck"),
                session_file: Optional[Path] = typer.Option(None, "--session-file", help="Browser session export for miras or miras_periodicals.")):
    """Discover, then download eligible files within the same run budget."""
    execute(ctx, "run", source, limit=limit, max_pages=max_pages, recheck=recheck, session_file=session_file)


@app.command()
def status(ctx: typer.Context, source: str = typer.Option(..., "--source")):
    """Read manifest counts without network requests or artifact writes."""
    execute(ctx, "status", source)
