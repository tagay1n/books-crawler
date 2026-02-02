"""CLI entry points for Milli Kitaphana indexing, download, and maintenance tasks."""

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
def download(limited: bool = False, index_name: str = None):
    """
    Read index file and download documents what have not been downloaded yet
    """
    import download
    download.download(limited, index_name)
    

@app.command()
def decrypt():
    """
    Decrypt PDF parts what was downloaded by `download` command 
    """
    import decrypt as decrypt
    decrypt.decrypt()
    
    
@app.command()
def merge_index(path: str):
    """
    Merge index file provided by path with main index 
    """
    import merge_index
    merge_index.merge_indexes(path)
    

@app.command()
def split(
    parts: int = typer.Option(..., "--parts", "-p", help="Number of sublists to create"),
    dest: str = None,
    prefix: str = "index-part",
):
    """
    Split pending docs into N sublists stored under dest folder
    """
    import split_index
    split_index.split_lists(parts, dest, prefix)
    
    
if __name__ == "__main__":
    app()
