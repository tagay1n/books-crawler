import typer

app = typer.Typer()

@app.command()
def index():
    """
    Index book details from the website and save them to the file
    """
    import index
    index.index()
    
    
@app.command()
def download(url):
    """
    Read index file and download documents what have not been downloaded yet
    """
    import downloader
    downloader.download(url)
    
if __name__ == "__main__":
    app()
