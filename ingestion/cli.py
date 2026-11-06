import json
from pathlib import Path
from typing import Optional

import typer

from .output import compact_result
from .registry import SOURCES


app = typer.Typer(pretty_exceptions_show_locals=False, no_args_is_help=True, help="Discover documents and download originals locally.")
from .database_cli import app as database_app
app.add_typer(database_app, name="database")


@app.callback()
def main(ctx: typer.Context, config: Optional[Path] = typer.Option(None, "--config", help="Selected operational YAML file."),
         summary_only: bool = typer.Option(False, "--summary-only", help="Print one compact JSON result and suppress progress; run details are in Postgres.")):
    ctx.obj = config
    ctx.meta["summary_only"] = summary_only


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
def sources_command(ctx: typer.Context):
    """List adapters implemented in the shared CLI."""
    if ctx.meta.get("summary_only"):
        emit_result(ctx, {"sources": list(SOURCES)}, "sources")
        return
    for source in SOURCES:
        typer.echo(source)


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
          session_file: Path = typer.Option(..., "--session-file", help="Miras-only cookie and user-agent JSON from your verified browser.")):
    """Check Miras HTTP access with exported cookies and acquire one sample PDF."""
    from .registry import PILOT_SOURCES
    from .config import load_settings
    try:
        if source not in PILOT_SOURCES:
            raise ValueError(f"Unknown access pilot: {source}. Available: {', '.join(PILOT_SOURCES)}")
        settings = load_settings(ctx.obj, source)
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
        from .config import load_settings
        from .core import restricted_settings, run
        settings = restricted_settings(load_settings(ctx.obj, source), limit, max_pages)
        settings.source_options["_target"] = target or "s3"
        if source in {"litres", "milli_kitaphana", "common_crawl"}:
            if session_file is not None:
                raise ValueError(f"{source} uses its operational source settings, not --session-file")
            settings.source_options.update(_limited=limited, _index_name=index_name, _maintenance=maintenance or {}, _mode=mode, _format=format, _action=action, _target=target, _from=str(from_path) if from_path else None)
            if source == "common_crawl":
                if command not in SOURCES[source].SUPPORTED_COMMANDS:
                    raise ValueError(f"{source} does not implement the selected stage")
                if mode != "catalog":
                    raise ValueError("Common Crawl supports only --mode catalog")
                if format not in {"all", "pdf"}:
                    raise ValueError("Common Crawl supports only original PDFs (--format all or pdf)")
                if recheck:
                    raise ValueError("Common Crawl does not support --recheck")
        elif mode != "catalog" or format != "all" or (command != "publish" or target != "s3") and command not in getattr(SOURCES[source], "SUPPORTED_COMMANDS", {"discover", "download", "run", "status"}):
            raise ValueError(f"{source} does not implement the selected stage or option")
        if source == "milli_kitaphana" and (mode != "catalog" or format != "all"):
            raise ValueError("Milli supports catalog discovery and its native document format only")
        if source != "milli_kitaphana" and (limited or index_name or maintenance):
            raise ValueError("Selected options require --source milli_kitaphana")
        result = run(settings, source, command, recheck=recheck, session_file=session_file, log=progress(ctx))
        emit_result(ctx, result, command, source)
    except (ValueError, OSError, RuntimeError, ImportError) as error:
        fail(ctx, error, command, source)
    if result.get("errors"):
        raise typer.Exit(1)


@app.command()
def discover(ctx: typer.Context, source: str = typer.Option(..., "--source"),
             max_pages: Optional[int] = typer.Option(None, "--max-pages"),
             mode: str = typer.Option("catalog", "--mode", help="catalog, candidates, or all"),
             session_file: Optional[Path] = typer.Option(None, "--session-file", help="Browser session export for miras or miras_periodicals.")):
    """Discover archive records and attachments without downloading originals."""
    if mode not in {"catalog", "candidates", "all"}:
        fail(ctx, ValueError("Invalid discovery mode"), "discover", source)
    execute(ctx, "discover", source, max_pages=max_pages, session_file=session_file, mode=mode)


@app.command()
def download(ctx: typer.Context, source: str = typer.Option(..., "--source"),
             limit: Optional[int] = typer.Option(None, "--limit", help="Maximum files; whole issues for kazanutlary, files/publications for tatkniga and KFU."),
             format: str = typer.Option("all", "--format", help="all, pdf, or text"),
             limited: bool = typer.Option(False, "--limited"),
             index_name: Optional[str] = typer.Option(None, "--index-name"),
             recheck: bool = typer.Option(False, "--recheck", help="Also revalidate completed downloads."),
             session_file: Optional[Path] = typer.Option(None, "--session-file", help="Browser session export for miras or miras_periodicals.")):
    """Download committed originals; Tatkniga reader PDFs require finalize."""
    if format not in {"all", "pdf", "text"}:
        fail(ctx, ValueError("Invalid download format"), "download", source)
    execute(ctx, "download", source, limit=limit, recheck=recheck, session_file=session_file, format=format, limited=limited, index_name=index_name)


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
           action: str = typer.Option(..., "--action")):
    """Export or sync TSV review decisions, or import accepted candidates."""
    if action not in {"export", "sync", "import"}:
        fail(ctx, ValueError("Review action must be export, sync, or import"), "review", source)
    execute(ctx, "review", source, action=action)


@app.command()
def publish(ctx: typer.Context, source: str = typer.Option(..., "--source"),
            target: str = typer.Option("s3", "--target")):
    """Publish finalized outputs to an explicitly selected destination."""
    if target not in {"s3", "yandex", "hf", "s3-media"}:
        fail(ctx, ValueError("Publish target must be s3, yandex, hf, or s3-media"), "publish", source)
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
def recover(ctx: typer.Context, source: str = typer.Option(..., "--source"), report: str = typer.Option("default", help="Postgres recovery journal name."), workers: int = typer.Option(4, min=1), download: bool = False, retry_failed: bool = False, download_workers: int = typer.Option(4, min=1)):
    execute(ctx, "recover", source, maintenance=dict(report_path=report, workers=workers, download=download, retry_failed=retry_failed, download_workers=download_workers))


@app.command("mark-existing-limited")
def mark_existing_limited(ctx: typer.Context, source: str = typer.Option(..., "--source")):
    execute(ctx, "mark-existing-limited", source)
