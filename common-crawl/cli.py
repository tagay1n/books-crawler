import typer

app = typer.Typer()

@app.command()
def index():
    import index
    index.index()
    
    
@app.command()
def download():
    import download
    download.download()
    
    
@app.command()
def upload():
    import upload
    upload.upload()
    
    
    
if __name__ == "__main__":
    app()
