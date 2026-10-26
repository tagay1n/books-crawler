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


def execute(ctx, command, source, limit=None, max_pages=None, recheck=False):
    try:
        if source not in SOURCES:
            raise ValueError(f"Unknown source: {source}. Available: {', '.join(SOURCES)}")
        settings = restricted_settings(load_settings(ctx.obj, source), limit, max_pages)
        result = run(settings, source, command, recheck=recheck, log=typer.echo)
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, RuntimeError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)
    if result.get("errors"):
        raise typer.Exit(1)


@app.command()
def discover(ctx: typer.Context, source: str = typer.Option(..., "--source"),
             max_pages: Optional[int] = typer.Option(None, "--max-pages")):
    """Discover archive records and attachments without downloading originals."""
    execute(ctx, "discover", source, max_pages=max_pages)


@app.command()
def download(ctx: typer.Context, source: str = typer.Option(..., "--source"),
             limit: Optional[int] = typer.Option(None, "--limit"),
             recheck: bool = typer.Option(False, "--recheck", help="Also revalidate completed downloads.")):
    """Download committed local work; retry failed or missing originals."""
    execute(ctx, "download", source, limit=limit, recheck=recheck)


@app.command("run")
def run_command(ctx: typer.Context, source: str = typer.Option(..., "--source"),
                limit: Optional[int] = typer.Option(None, "--limit"),
                max_pages: Optional[int] = typer.Option(None, "--max-pages"),
                recheck: bool = typer.Option(False, "--recheck")):
    """Discover, then download eligible files within the same run budget."""
    execute(ctx, "run", source, limit=limit, max_pages=max_pages, recheck=recheck)


@app.command()
def status(ctx: typer.Context, source: str = typer.Option(..., "--source")):
    """Read manifest counts without network requests or artifact writes."""
    execute(ctx, "status", source)
