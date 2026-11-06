"""Typer CLI for Common Crawl tasks (index, download, upload)."""

import typer
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingestion.database import source_lock

app = typer.Typer()

@app.command()
def index():
    import index
    with source_lock("common_crawl"):
        index.index()
    
    
@app.command()
def download():
    import download
    with source_lock("common_crawl"):
        download.download()
    
    
@app.command()
def upload():
    import upload
    with source_lock("common_crawl"):
        upload.upload()
    
    
    
if __name__ == "__main__":
    app()
