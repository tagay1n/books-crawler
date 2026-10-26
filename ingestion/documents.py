from urllib.parse import urljoin, urlsplit, urlunsplit


DOCUMENT_EXTENSIONS = {".pdf", ".djvu", ".djv", ".epub", ".txt", ".html", ".htm",
                       ".doc", ".docx", ".odt", ".rtf", ".ppt", ".pptx", ".odp",
                       ".xls", ".xlsx", ".ods"}


def canonical(url, base):
    parsed = urlsplit(urljoin(base, url))
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, parsed.query, ""))


def same_origin(url, base):
    left, right = urlsplit(url), urlsplit(base)
    return (left.scheme, left.netloc) == (right.scheme, right.netloc)
