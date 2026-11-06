"""Litres PDF acquisition orchestration; transport and assembly live in focused modules.

Imported helper names remain available here for existing native pipeline callers.
"""
from .runtime_config import option as operational_option
import os
import re
from urllib.parse import parse_qs, urlparse
from rich.progress import track
from .litres_utils import requests, create_driver, load_index, save_index, get_in_workdir

from .litres_index import _content_type_from_book_page_html, _content_type_from_reader_url, _open_reader_url
from .litres_browser import (
    LitresAuthenticationError as LitresAuthenticationError,
    _binary_response_details as _binary_response_details,
    _create_litres_session as _create_litres_session,
    _fetch_binary_with_browser as _fetch_binary_with_browser,
    _fetch_binary_with_browser_cookies as _fetch_binary_with_browser_cookies,
    _fetch_pdf_page_with_browser as _fetch_pdf_page_with_browser,
    _fetch_text_with_browser as _fetch_text_with_browser,
    _format_pdf_page_response_error as _format_pdf_page_response_error,
    _get_litres_cookie_header as _get_litres_cookie_header,
    _get_litres_headers as _get_litres_headers,
    _get_litres_page_image_headers as _get_litres_page_image_headers,
    _is_image_response as _is_image_response,
    _is_invalid_selenium_session_error as _is_invalid_selenium_session_error,
    _raise_for_auth_response as _raise_for_auth_response,
    _raise_for_non_image_pdf_page_response as _raise_for_non_image_pdf_page_response,
    _raise_for_non_javascript_pdf_metadata_response as _raise_for_non_javascript_pdf_metadata_response,
    _response_details as _response_details,
    _should_retry_response_with_browser as _should_retry_response_with_browser,
    _should_retry_with_browser as _should_retry_with_browser,
    _wait_for_browser_challenge as _wait_for_browser_challenge,
    _warm_up_browser_for_protected_url as _warm_up_browser_for_protected_url,
)
from .litres_pdf_assembly import (
    _compressed_page_jpeg_bytes as _compressed_page_jpeg_bytes,
    _create_pdf as _create_pdf,
    _is_valid_image_file as _is_valid_image_file,
    _is_valid_pdf_file as _is_valid_pdf_file,
    _lossless_page_png_bytes as _lossless_page_png_bytes,
    _page_image_bytes_for_pdf as _page_image_bytes_for_pdf,
    _remove_if_exists as _remove_if_exists,
    _remove_stale_temporary_files as _remove_stale_temporary_files,
    _resample_lanczos as _resample_lanczos,
    _save_pdf_page_image as _save_pdf_page_image,
    _temporary_path as _temporary_path,
    _to_rgb_image as _to_rgb_image,
)
from .litres_pdf_config import _config_bool as _config_bool, _get_pdf_browser_challenge_wait_seconds as _get_pdf_browser_challenge_wait_seconds, _get_pdf_browser_headless as _get_pdf_browser_headless, _get_pdf_compression_options as _get_pdf_compression_options, _get_pdf_config as _get_pdf_config, _required_config_value as _required_config_value


# Compatibility exports for the unified native pipeline.
__all__ = [
    'LitresAuthenticationError',
    '_binary_response_details',
    '_create_litres_session',
    '_fetch_binary_with_browser',
    '_fetch_binary_with_browser_cookies',
    '_fetch_pdf_page_with_browser',
    '_fetch_text_with_browser',
    '_format_pdf_page_response_error',
    '_get_litres_cookie_header',
    '_get_litres_headers',
    '_get_litres_page_image_headers',
    '_is_image_response',
    '_is_invalid_selenium_session_error',
    '_raise_for_auth_response',
    '_raise_for_non_image_pdf_page_response',
    '_raise_for_non_javascript_pdf_metadata_response',
    '_response_details',
    '_should_retry_response_with_browser',
    '_should_retry_with_browser',
    '_wait_for_browser_challenge',
    '_warm_up_browser_for_protected_url',
    '_compressed_page_jpeg_bytes',
    '_create_pdf',
    '_is_valid_image_file',
    '_is_valid_pdf_file',
    '_lossless_page_png_bytes',
    '_page_image_bytes_for_pdf',
    '_remove_if_exists',
    '_remove_stale_temporary_files',
    '_resample_lanczos',
    '_save_pdf_page_image',
    '_temporary_path',
    '_to_rgb_image',
    'PDF_REQUEST_TIMEOUT_SECONDS',
    'PDF_RESPONSE_SNIPPET_BYTES',
    'RAW_PAGE_DPI',
    '_config_bool',
    '_get_pdf_browser_challenge_wait_seconds',
    '_get_pdf_browser_headless',
    '_get_pdf_compression_options',
    '_get_pdf_config',
    '_required_config_value',
]


def visit_pdf_books_pages():
    """
    Entry point for visiting pdf books pages.

    Visit pdf books pages, download their pages separately and create pdf from them
    """
    all_books = load_index('books')

    pdf_books = _get_pdf_books_to_visit(all_books)

    print(f"Visiting {len(pdf_books)} pdf books pages")

    session = _create_litres_session()
    driver = None

    def _close_driver():
        nonlocal driver
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
            driver = None

    def _get_driver():
        nonlocal driver
        if driver is None:
            driver = create_driver(headless=_get_pdf_browser_headless())
        return driver

    try:
        try:
            for book in pdf_books[:]:
                url = book['url']
                for attempt in range(operational_option('litres_pdf', 'book_attempts')):
                    try:
                        if _has_pdf_runtime_details(book):
                            actual_type = "pdf"
                        else:
                            actual_type = _get_content_type_from_book_page(url, session, driver_provider=_get_driver)
                            if actual_type and actual_type != "pdf":
                                print(f"Skipping non-PDF book: {url} ({actual_type})")
                                book["content_type"] = actual_type
                                _save_books_index(all_books)
                                break
                        if book.get("file_id"):
                            file_id = book["file_id"]
                        else:
                            file_id = _get_file_id(url, session=session, driver_provider=_get_driver)
                            book['file_id'] = file_id
                            _save_books_index(all_books)
                        print(f"Visiting book page: {file_id}")
                        if book.get('ext'):
                            page_extensions = book['ext']
                        else:
                            page_extensions = _get_page_extensions(file_id, session=session, driver_provider=_get_driver)

                        if file_id != book.get('file_id') or page_extensions != book.get('ext'):
                            book['file_id'] = file_id
                            book['ext'] = page_extensions
                            _save_books_index(all_books)

                        download_page_images(
                            file_id,
                            page_extensions,
                            session=session,
                            driver=driver,
                            driver_provider=_get_driver,
                            book_page_url=url,
                        )
                        book['pdf_file'] = _create_pdf(book)
                        _save_books_index(all_books)
                        break
                    except Exception as e:
                        if attempt == 0 and _is_invalid_selenium_session_error(e):
                            print("Litres browser session is invalid; restarting browser and retrying current book")
                            _close_driver()
                            continue
                        print(f"Error processing book: {url}")
                        print(e)
                        break
        except KeyboardInterrupt:
            _save_books_index(all_books)
            print("Interrupted; saved current index state to Postgres")
            raise
    finally:
        _close_driver()


def _get_pdf_books_to_visit(all_books):
    """
    Return PDF books that still need local page download and PDF reconstruction.
    """
    return [
        b
        for b in all_books.values()
        if b.get("content_type") == "pdf" and not b.get("pdf_file")
    ]


def _has_pdf_runtime_details(book):
    return bool(book.get("file_id") and book.get("ext"))


def _save_books_index(all_books):
    save_index('books', all_books)


def _get_file_id(book_page_url, driver=None, session=None, driver_provider=None):
    """
    Get file_id from book page url

    :param book_page_url:
    :return: internal file id
    """
    print(f"Getting file id for book page: {book_page_url}")
    if session:
        try:
            file_id = _get_file_id_from_book_page_html(book_page_url, session)
        except requests.HTTPError as exc:
            if not _should_retry_with_browser(exc):
                raise
            print(f"Litres rejected direct request; opening reader in browser for file id: {book_page_url}")
            file_id = None
        if file_id:
            return file_id
    if driver is None:
        if driver_provider:
            driver = driver_provider()
        else:
            with create_driver() as driver:
                return _get_file_id_from_reader_url(book_page_url, driver)
    return _get_file_id_from_reader_url(book_page_url, driver)


def _get_file_id_from_book_page_html(book_page_url, session):
    response = session.get(book_page_url, timeout=operational_option('litres_pdf_config', 'pdf_request_timeout_seconds'))
    response.raise_for_status()
    details = _response_details(response)
    _raise_for_auth_response(details, "Litres rejected current SID while opening book page")
    match = re.search(r'release_file_id\\?":(\d+)', response.text)
    return match.group(1) if match else None


def _get_content_type_from_book_page(book_page_url, session, driver_provider=None):
    try:
        response = session.get(book_page_url, timeout=operational_option('litres_pdf_config', 'pdf_request_timeout_seconds'))
        response.raise_for_status()
    except requests.HTTPError as exc:
        if not driver_provider or not _should_retry_with_browser(exc):
            raise
        print(f"Litres rejected direct request; resolving content type in browser: {book_page_url}")
        reader_url = _open_reader_url(book_page_url, driver_provider())
        return _content_type_from_reader_url(reader_url, book_page_url)
    details = _response_details(response)
    _raise_for_auth_response(details, "Litres rejected current SID while opening book page")
    if driver_provider and _should_retry_response_with_browser(details):
        print(f"Litres returned anti-bot page; resolving content type in browser: {book_page_url}")
        reader_url = _open_reader_url(book_page_url, driver_provider())
        return _content_type_from_reader_url(reader_url, book_page_url)
    return _content_type_from_book_page_html(response.text, book_page_url)


def _get_file_id_from_reader_url(book_page_url, driver):
    reader_url = _open_reader_url(book_page_url, driver)
    parsed_url = urlparse(reader_url)
    queries = parse_qs(parsed_url.query)
    if not (file := queries.get('file')):
        raise ValueError(f"Could not find file id in reader URL for {book_page_url}: {reader_url}")
    return file[0]


def _get_page_extensions(file_id, session=None, driver=None, driver_provider=None):
    """
    Get dict with extensions for each page

    :param file_id: id of the file
    :return: dict with extensions for each page
    """
    print(f"Getting page extensions for file: {file_id}")
    url = f"{operational_option('litres_consts', 'domain')}/pages/get_pdf_js/?file={file_id}"
    if session:
        try:
            with session.get(url, timeout=operational_option('litres_pdf_config', 'pdf_request_timeout_seconds')) as r:
                r.raise_for_status()
                response = _response_details(r)
                if driver_provider and _should_retry_response_with_browser(response):
                    print(f"Litres returned anti-bot page; loading PDF metadata in browser: {file_id}")
                    return _get_page_extensions(file_id, driver=driver_provider())
                _raise_for_non_javascript_pdf_metadata_response(response, url)
                return _execute_pdf_metadata_script(response["text"], file_id, driver, driver_provider)
        except requests.HTTPError as exc:
            if not _should_retry_with_browser(exc):
                raise
            print(f"Litres rejected direct request; loading PDF metadata in browser: {file_id}")

    if driver:
        response = _fetch_text_with_browser(driver, url)
        if response.get("error"):
            raise ValueError(f"Could not fetch Litres PDF metadata in browser: {response['error']}")
        _raise_for_non_javascript_pdf_metadata_response(response, url)
        return driver.execute_script(
            """let PFURL = { pdf: { } };""" + response["text"] + "; return PFURL.pdf[" + file_id + "];"
        )

    if driver_provider:
        return _get_page_extensions(file_id, driver=driver_provider())

    headers = _get_litres_headers()
    with requests.get(url, headers=headers, timeout=operational_option('litres_pdf_config', 'pdf_request_timeout_seconds')) as r:
        r.raise_for_status()
        response = _response_details(r)
        _raise_for_non_javascript_pdf_metadata_response(response, url)
        with create_driver() as driver:
            return _execute_pdf_metadata_script(response["text"], file_id, driver)


def _execute_pdf_metadata_script(script_text, file_id, driver=None, driver_provider=None):
    script = """let PFURL = { pdf: { } };""" + script_text + "; return PFURL.pdf[" + file_id + "];"
    if driver:
        return driver.execute_script(script)
    if driver_provider:
        return driver_provider().execute_script(script)
    with create_driver() as driver:
        return driver.execute_script(script)


def download_page_images(file_id, page_extensions, session=None, driver=None, driver_provider=None, book_page_url=None):
    artifacts_dir = get_in_workdir(f"images/{file_id}")
    os.makedirs(artifacts_dir, exist_ok=True)
    _remove_stale_temporary_files(artifacts_dir)
    p = page_extensions['pages'][0]['p']

    headers = _get_litres_headers(driver) if not session else None
    for page_no in track(range(0, len(p)), description=f"Downloading pages for file: {file_id}"):
        result_file = os.path.join(artifacts_dir, f"{page_no}.png")
        if _is_valid_image_file(result_file):
            continue
        if os.path.exists(result_file):
            os.remove(result_file)

        url = f"{operational_option('litres_consts', 'domain')}/pages/get_pdf_page/?file={file_id}&page={page_no}&rt=w{p[page_no]['w']}&ft={p[page_no]['ext']}"

        request = session.get if session else requests.get
        request_kwargs = {"timeout": operational_option('litres_pdf_config', 'pdf_request_timeout_seconds')}
        if not session:
            request_kwargs["headers"] = headers
        with request(url, **request_kwargs) as r:
            try:
                r.raise_for_status()
            except requests.HTTPError as exc:
                if not driver_provider or not _should_retry_with_browser(exc):
                    raise
                print(f"Litres rejected direct request; loading PDF page in browser: {file_id}/{page_no}")
                image_content, content_type = _fetch_pdf_page_with_browser(driver_provider(), url, book_page_url)
                response = _binary_response_details(image_content, content_type)
                _raise_for_non_image_pdf_page_response(response, url)
                _save_pdf_page_image(image_content, response, result_file, url)
                continue
            if driver and not _is_image_response(r):
                image_content, content_type = _fetch_pdf_page_with_browser(driver, url, book_page_url)
                response = _binary_response_details(image_content, content_type)
            elif driver_provider and _should_retry_response_with_browser(_response_details(r)):
                print(f"Litres returned anti-bot page; loading PDF page in browser: {file_id}/{page_no}")
                image_content, content_type = _fetch_pdf_page_with_browser(driver_provider(), url, book_page_url)
                response = _binary_response_details(image_content, content_type)
            else:
                image_content = r.content
                response = _response_details(r)

            _raise_for_non_image_pdf_page_response(response, url)
            _save_pdf_page_image(image_content, response, result_file, url)
