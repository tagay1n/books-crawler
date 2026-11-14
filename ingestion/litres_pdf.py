"""Litres PDF metadata and page-image acquisition helpers."""
from .runtime_config import option as operational_option
import os
import re
from urllib.parse import parse_qs, urlparse
from rich.progress import track
from .litres_utils import requests, create_driver, get_in_workdir
from .litres_index import _open_reader_url
from .litres_browser import (
    _binary_response_details,
    _fetch_pdf_page_with_browser,
    _fetch_text_with_browser,
    _get_litres_headers,
    _is_image_response,
    _raise_for_auth_response,
    _raise_for_non_image_pdf_page_response,
    _raise_for_non_javascript_pdf_metadata_response,
    _response_details,
    _should_retry_response_with_browser,
    _should_retry_with_browser,
)
from .litres_pdf_assembly import (
    _is_valid_image_file,
    _remove_stale_temporary_files,
    _save_pdf_page_image,
)


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
