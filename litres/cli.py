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
def pdf():
    """
    Download pdf books from the website
    """
    import pdf
    pdf.visit_pdf_books_pages()


@app.command()
def text():
    """
    Download text books from the website
    """
    import text
    text.visit_text_books_pages()


@app.command()
def hf():
    """
    Upload markdown and images to hugging face
    """
    import hf
    hf.upload_to_hf()


@app.command()
def upload():
    """
    Upload books to yandex disk, create public links and save details to the Google Sheets
    """
    import upload_books
    upload_books.upload_pdfs()


@app.command()
def metadata():
    """
    Scrap metadata for the books
    """
    import metadata
    metadata.scrap_metadata()


if __name__ == "__main__":
    app()
