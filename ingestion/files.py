"""Shared local-file integrity, space checks and document signatures."""
import hashlib
import shutil

from .network import InvalidDocument


MIME_EXTENSIONS = {
    "application/pdf": ".pdf", "image/vnd.djvu": ".djvu", "image/x-djvu": ".djvu",
    "application/epub+zip": ".epub", "text/plain": ".txt", "text/html": ".html",
    "application/msword": ".doc", "application/rtf": ".rtf", "text/rtf": ".rtf",
    "application/vnd.ms-powerpoint": ".ppt", "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.oasis.opendocument.text": ".odt",
    "application/vnd.oasis.opendocument.presentation": ".odp",
    "application/vnd.oasis.opendocument.spreadsheet": ".ods",
}


def file_digests(path):
    sha, md5, size = hashlib.sha256(), hashlib.md5(), 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
            md5.update(chunk)
            size += len(chunk)
    return sha.hexdigest(), md5.hexdigest(), size


def valid_local(directory, result, *, folder="files"):
    if not result:
        return False
    path = (directory / result["path"]).resolve()
    if not path.is_relative_to((directory / folder).resolve()):
        raise ValueError("Manifest contains a file reference outside its managed files directory.")
    if not path.is_file() or path.stat().st_size != result["size"]:
        return False
    return file_digests(path)[0] == result["sha256"]


def source_version_matches(asset):
    """Opt-in source hints do not alter older adapters' download behavior."""
    return ("source_version" not in asset
            or asset.get("verified_source_version") == asset["source_version"])


def check_space(directory, reserve, upcoming=0):
    if shutil.disk_usage(directory).free - upcoming < reserve:
        raise OSError("Insufficient free disk space for the configured reserve and transfer.")


def validate_document(prefix, extension, mime):
    stripped = prefix.lstrip().lower()
    html = stripped.startswith((b"<!doctype html", b"<html", b"<head", b"<body"))
    if extension not in {".html", ".htm"} and (html or mime in {"text/html", "application/xhtml+xml"}):
        raise InvalidDocument("Received an HTML/error/login page instead of a document.")
    if extension == ".pdf" and b"%PDF-" not in prefix[:1024]:
        raise InvalidDocument("Response does not have a PDF signature.")
    if extension in {".djvu", ".djv"} and not prefix.startswith(b"AT&TFORM"):
        raise InvalidDocument("Response does not have a DjVu signature.")
    if extension in {".docx", ".pptx", ".xlsx", ".epub", ".odt", ".odp", ".ods"} and not prefix.startswith(b"PK"):
        raise InvalidDocument("Response does not have an expected document-container signature.")
    if extension in {".doc", ".ppt", ".xls"} and not prefix.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise InvalidDocument("Response does not have an expected office-document signature.")
    if extension == ".rtf" and not stripped.startswith(b"{\\rtf"):
        raise InvalidDocument("Response does not have an RTF signature.")
