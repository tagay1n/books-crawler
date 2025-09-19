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
def download(with_limited: bool = False):
    """
    Read index file and download documents what have not been downloaded yet
    """
    import download
    download.download(with_limited)
    

@app.command()
def decrypt():
    """
    Decrypt PDF parts what was downloaded by `download` command 
    """
    import decrypt as decrypt
    decrypt.decrypt()
    
    
if __name__ == "__main__":
    app()
