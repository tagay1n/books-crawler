import typer

app = typer.Typer()

@app.command()
def index():
    import index
    index.index()
    
    
@app.command()
def download():
    import downloader
    downloader.download()
    
if __name__ == "__main__":
    app()
