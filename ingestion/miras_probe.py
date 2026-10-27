"""Public-page parsers and PDF validation for the Miras cookie-access pilot."""

from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
import pymupdf

from .documents import canonical, same_origin
from .network import InvalidDocument


SAMPLE_RECORD = "https://miras.info/projects/mirasxane/books/889-avyl-kyzy-.html"



def catalog(html):
    soup = BeautifulSoup(html, "html.parser")
    links = {canonical(a["href"], SAMPLE_RECORD): a.get_text(" ", strip=True)
             for a in soup.select('a[href*="/projects/mirasxane/books/"]')
             if same_origin(canonical(a["href"], SAMPLE_RECORD), SAMPLE_RECORD)
             and urlsplit(canonical(a["href"], SAMPLE_RECORD)).path.endswith(".html")}
    if not links:
        raise ValueError("No recognizable Miras book records in catalog HTML.")
    return links


def book(html):
    soup = BeautifulSoup(html, "html.parser")
    files = set()
    for node in soup.select("iframe[src], a[href]"):
        target = canonical(node.get("src", node.get("href")), SAMPLE_RECORD)
        if not same_origin(target, SAMPLE_RECORD):
            continue
        parsed = urlsplit(target)
        values = parse_qs(parsed.query).get("file", [])
        if parsed.path.endswith("/viewer.html") and len(values) == 1:
            target = canonical(values[0], target)
            parsed = urlsplit(target)
        if (same_origin(target, SAMPLE_RECORD) and parsed.path.startswith("/uploads/files/")
                and parsed.path.lower().endswith(".pdf") and not parsed.query):
            files.add(target)
    if len(files) != 1:
        raise ValueError("Expected exactly one same-origin PDF reference in the sample book reader.")
    heading = soup.select_one("h1, .fullstory-title, .full-title, title")
    return {"url": SAMPLE_RECORD, "title": heading.get_text(" ", strip=True) if heading else "Авыл кызы",
            "pilot": True, "pdf_url": files.pop()}


def validate_pdf(path):
    try:
        with pymupdf.open(path) as document:
            if document.page_count < 1:
                raise ValueError("PDF has no pages.")
            document.load_page(0)
            return document.page_count
    except (ValueError, RuntimeError) as error:
        raise InvalidDocument("Sample could not be reopened as a nonempty PDF.") from error
