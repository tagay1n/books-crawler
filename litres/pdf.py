"""Downloads Litres PDF books by fetching page metadata and images, reconstructs PDFs from image pages, and records file IDs and extensions in the index."""

import io
import json
import os.path
import base64
import re
from urllib.parse import parse_qs, urlparse

import pymupdf
import requests
from PIL import Image, UnidentifiedImageError
from rich.progress import track

from consts import domain
from index import _content_type_from_book_page_html, _open_reader_url
from utils import create_driver, dump_json_atomic, get_sid, get_in_workdir

PDF_REQUEST_TIMEOUT_SECONDS = 30
PDF_RESPONSE_SNIPPET_BYTES = 300


class LitresAuthenticationError(ValueError):
    """Raised when Litres redirects protected PDF resources to the login page."""


def visit_pdf_books_pages():
    """
    Entry point for visiting pdf books pages.

    Visit pdf books pages, download their pages separately and create pdf from them
    """
    path_to_idx = get_in_workdir("../__artifacts/litres/books-index.json")
    with open(path_to_idx, "r", encoding="utf-8") as f:
        all_books = json.load(f)

    pdf_books = _get_pdf_books_to_visit(all_books)

    print(f"Visiting {len(pdf_books)} pdf books pages")

    session = _create_litres_session()
    driver = None
    try:
        try:
            for book in pdf_books[:]:
                url = book['url']
                try:
                    actual_type = _get_content_type_from_book_page(url, session)
                    if actual_type and actual_type != "pdf":
                        print(f"Skipping non-PDF book: {url} ({actual_type})")
                        book["content_type"] = actual_type
                        _save_books_index(path_to_idx, all_books)
                        continue
                    if book.get("file_id"):
                        file_id = book["file_id"]
                    else:
                        file_id = _get_file_id(url, session=session)
                        book['file_id'] = file_id
                        _save_books_index(path_to_idx, all_books)
                    print(f"Visiting book page: {file_id}")
                    if book.get('ext'):
                        page_extensions = book['ext']
                    else:
                        page_extensions = _get_page_extensions(file_id, session=session)

                    if file_id != book.get('file_id') or page_extensions != book.get('ext'):
                        book['file_id'] = file_id
                        book['ext'] = page_extensions
                        _save_books_index(path_to_idx, all_books)

                    download_page_images(file_id, page_extensions, session=session, driver=driver)
                    book['pdf_file'] = _create_pdf(book)
                    _save_books_index(path_to_idx, all_books)
                except Exception as e:
                    print(f"Error processing book: {url}")
                    print(e)
        except KeyboardInterrupt:
            _save_books_index(path_to_idx, all_books)
            print(f"Interrupted; saved current index state to {path_to_idx}")
            raise
    finally:
        if driver:
            driver.quit()


def _get_pdf_books_to_visit(all_books):
    """
    Return PDF books that still need local page download and PDF reconstruction.
    """
    return [
        b
        for b in all_books.values()
        if b.get("content_type") == "pdf" and not b.get("pdf_file")
    ]


def _save_books_index(path_to_idx, all_books):
    dump_json_atomic(all_books, path_to_idx)


def _get_file_id(book_page_url, driver=None, session=None):
    """
    Get file_id from book page url

    :param book_page_url:
    :return: internal file id
    """
    print(f"Getting file id for book page: {book_page_url}")
    if session:
        file_id = _get_file_id_from_book_page_html(book_page_url, session)
        if file_id:
            return file_id
    if driver is None:
        with create_driver() as driver:
            return _get_file_id_from_reader_url(book_page_url, driver)
    return _get_file_id_from_reader_url(book_page_url, driver)


def _get_file_id_from_book_page_html(book_page_url, session):
    response = session.get(book_page_url, timeout=PDF_REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    details = _response_details(response)
    _raise_for_auth_response(details, "Litres rejected current SID while opening book page")
    match = re.search(r'release_file_id\\?":(\d+)', response.text)
    return match.group(1) if match else None


def _get_content_type_from_book_page(book_page_url, session):
    response = session.get(book_page_url, timeout=PDF_REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    details = _response_details(response)
    _raise_for_auth_response(details, "Litres rejected current SID while opening book page")
    return _content_type_from_book_page_html(response.text, book_page_url)


def _get_file_id_from_reader_url(book_page_url, driver):
    reader_url = _open_reader_url(book_page_url, driver)
    parsed_url = urlparse(reader_url)
    queries = parse_qs(parsed_url.query)
    if not (file := queries.get('file')):
        raise ValueError(f"Could not find file id in reader URL for {book_page_url}: {reader_url}")
    return file[0]


def _get_page_extensions(file_id, session=None, driver=None):
    """
    Get dict with extensions for each page

    :param file_id: id of the file
    :return: dict with extensions for each page
    """
    print(f"Getting page extensions for file: {file_id}")
    url = f"{domain}/pages/get_pdf_js/?file={file_id}"
    if session:
        with session.get(url, timeout=PDF_REQUEST_TIMEOUT_SECONDS) as r:
            r.raise_for_status()
            response = _response_details(r)
            _raise_for_non_javascript_pdf_metadata_response(response, url)
            with create_driver() as driver:
                return driver.execute_script(
                    """let PFURL = { pdf: { } };""" + response["text"] + "; return PFURL.pdf[" + file_id + "];"
                )

    if driver:
        response = _fetch_text_with_browser(driver, url)
        if response.get("error"):
            raise ValueError(f"Could not fetch Litres PDF metadata in browser: {response['error']}")
        _raise_for_non_javascript_pdf_metadata_response(response, url)
        return driver.execute_script(
            """let PFURL = { pdf: { } };""" + response["text"] + "; return PFURL.pdf[" + file_id + "];"
        )

    headers = _get_litres_headers()
    with requests.get(url, headers=headers, timeout=PDF_REQUEST_TIMEOUT_SECONDS) as r:
        r.raise_for_status()
        response = _response_details(r)
        _raise_for_non_javascript_pdf_metadata_response(response, url)
        with create_driver() as driver:
            return driver.execute_script(
                """let PFURL = { pdf: { } };""" + response["text"] + "; return PFURL.pdf[" + file_id + "];")


def download_page_images(file_id, page_extensions, session=None, driver=None):
    artifacts_dir = get_in_workdir(f"../__artifacts/litres/images/{file_id}")
    os.makedirs(artifacts_dir, exist_ok=True)
    p = page_extensions['pages'][0]['p']

    headers = _get_litres_headers(driver)
    for page_no in track(range(0, len(p)), description=f"Downloading pages for file: {file_id}"):
        result_file = os.path.join(artifacts_dir, f"{page_no}.png")
        if not os.path.exists(result_file):
            url = f"{domain}/pages/get_pdf_page/?file={file_id}&page={page_no}&rt=w{p[page_no]['w']}&ft={p[page_no]['ext']}"

            request = session.get if session else requests.get
            request_kwargs = {"timeout": PDF_REQUEST_TIMEOUT_SECONDS}
            if not session:
                request_kwargs["headers"] = headers
            with request(url, **request_kwargs) as r:
                r.raise_for_status()
                if driver and not _is_image_response(r):
                    image_content, content_type = _fetch_binary_with_browser(driver, url)
                    response = _binary_response_details(image_content, content_type)
                else:
                    image_content = r.content
                    response = _response_details(r)

                _raise_for_non_image_pdf_page_response(response, url)
                try:
                    img = Image.open(io.BytesIO(image_content))
                except UnidentifiedImageError as exc:
                    raise ValueError(_format_pdf_page_response_error(response, url)) from exc
                with img:
                    img.save(result_file, format="PNG", dpi=(300, 300), optimize=True)


def _raise_for_non_image_pdf_page_response(response, url):
    _raise_for_auth_response(response, "Litres rejected current SID while loading PDF page image")
    content_type = response["content_type"] or ""
    if content_type and not content_type.lower().startswith("image/"):
        raise ValueError(_format_pdf_page_response_error(response, url))


def _format_pdf_page_response_error(response, url):
    snippet = response["content"][:PDF_RESPONSE_SNIPPET_BYTES].decode("utf-8", errors="replace")
    snippet = " ".join(snippet.split())
    return (
        "Litres returned a non-image PDF page response; "
        f"url={url}; status={response['status']}; "
        f"content-type={response['content_type']}; body-start={snippet!r}"
    )


def _raise_for_non_javascript_pdf_metadata_response(response, url):
    _raise_for_auth_response(response, "Litres rejected current SID while loading PDF metadata")
    content_type = response["content_type"] or ""
    text_start = response["text"].lstrip()[:1]
    if response["status"] >= 400 or content_type.lower().startswith("text/html") or text_start == "<":
        snippet = " ".join(response["text"][:PDF_RESPONSE_SNIPPET_BYTES].split())
        raise ValueError(
            "Litres returned a non-JavaScript PDF metadata response; "
            f"url={url}; status={response['status']}; "
            f"content-type={response['content_type']}; body-start={snippet!r}"
        )


def _raise_for_auth_response(response, message):
    if "/auth/login/" in (response.get("url") or ""):
        raise LitresAuthenticationError(
            f"{message}. Update 'sid' in litres/config.yaml, then rerun the command."
        )


def _create_litres_session():
    session = requests.Session()
    session.headers.update(_get_litres_headers())
    return session


def _fetch_text_with_browser(driver, url):
    return driver.execute_async_script(
        """
        const [url, callback] = arguments;
        fetch(url, {credentials: 'include'})
          .then(async response => callback({
            status: response.status,
            content_type: response.headers.get('content-type'),
            text: await response.text()
          }))
          .catch(error => callback({error: String(error)}));
        """,
        url,
    )


def _fetch_binary_with_browser(driver, url):
    response = driver.execute_async_script(
        """
        const [url, callback] = arguments;
        fetch(url, {credentials: 'include'})
          .then(async response => {
            const blob = await response.blob();
            const reader = new FileReader();
            reader.onloadend = () => callback({
              status: response.status,
              content_type: response.headers.get('content-type'),
              dataUrl: reader.result
            });
            reader.onerror = () => callback({error: 'Could not read response blob'});
            reader.readAsDataURL(blob);
          })
          .catch(error => callback({error: String(error)}));
        """,
        url,
    )
    if response.get("error"):
        raise ValueError(f"Could not fetch Litres PDF page in browser: {response['error']}")
    _, encoded = response["dataUrl"].split(",", 1)
    return base64.b64decode(encoded), response.get("content_type")


def _get_litres_headers(driver=None):
    user_agent = (
        driver.execute_script("return navigator.userAgent")
        if driver
        else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    )
    return {
        "Cookie": _get_litres_cookie_header(driver),
        "User-Agent": user_agent,
    }


def _get_litres_cookie_header(driver=None):
    if not driver:
        return f"SID={get_sid()};"
    return "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in driver.get_cookies())


def _is_image_response(response):
    return (response.headers.get("content-type") or "").lower().startswith("image/")


def _response_details(response):
    return {
        "status": response.status_code,
        "url": response.url,
        "content_type": response.headers.get("content-type"),
        "content": response.content,
        "text": response.text,
    }


def _binary_response_details(content, content_type, status=200):
    return {
        "status": status,
        "url": None,
        "content_type": content_type,
        "content": content,
        "text": content.decode("utf-8", errors="replace"),
    }


def _create_pdf(book):
    """
    Create pdf from downloaded pages images
    """
    file_id = book['file_id']
    artifacts_dir = get_in_workdir(f"../__artifacts/litres/images/{file_id}")
    pdf_dir = get_in_workdir("../__artifacts/litres/docs")
    os.makedirs(pdf_dir, exist_ok=True)

    name_with_ext = f"{book['full_name']}.pdf"
    pdf_file = os.path.join(pdf_dir, name_with_ext)
    if not os.path.exists(pdf_file):
        with pymupdf.open() as doc:
            # sort pages by number
            images = sorted([f for f in os.listdir(artifacts_dir)], key=lambda x: int(x.split(".")[0]))
            for page in track(images, description=f"Creating pdf for file: {file_id}"):
                with pymupdf.open(os.path.join(artifacts_dir, page)) as img:
                    rect = img[0].rect  # pic dimension
                    img_pdf = pymupdf.open("pdf", img.convert_to_pdf())  # open stream as PDF
                    page = doc.new_page(width=rect.width, height=rect.height)
                    page.show_pdf_page(rect, img_pdf, 0)  # image fills the page

            doc.save(pdf_file)
    return pdf_file
