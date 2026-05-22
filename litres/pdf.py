"""Downloads Litres PDF books by fetching page metadata and images, reconstructs PDFs from image pages, and records file IDs and extensions in the index."""

import io
import json
import os.path
import base64
import glob
import hashlib
import re
from urllib.parse import parse_qs, urlparse

import pymupdf
import requests
from PIL import Image, UnidentifiedImageError
from rich.progress import track

from consts import domain
from index import BLOCKED_MARKERS, _content_type_from_book_page_html, _content_type_from_reader_url, _open_reader_url
from utils import create_driver, dump_json_atomic, get_sid, get_in_workdir, read_config

PDF_REQUEST_TIMEOUT_SECONDS = 30
PDF_RESPONSE_SNIPPET_BYTES = 300
PDF_DEFAULT_JPEG_QUALITY = 92
PDF_DEFAULT_MAX_WIDTH = 2400
PDF_DEFAULT_DPI = 300
PDF_DEFAULT_BROWSER_HEADLESS = True
PDF_DEFAULT_BROWSER_CHALLENGE_WAIT_SECONDS = 180
RAW_PAGE_DPI = 300


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
                for attempt in range(2):
                    try:
                        if _has_pdf_runtime_details(book):
                            actual_type = "pdf"
                        else:
                            actual_type = _get_content_type_from_book_page(url, session, driver_provider=_get_driver)
                            if actual_type and actual_type != "pdf":
                                print(f"Skipping non-PDF book: {url} ({actual_type})")
                                book["content_type"] = actual_type
                                _save_books_index(path_to_idx, all_books)
                                break
                        if book.get("file_id"):
                            file_id = book["file_id"]
                        else:
                            file_id = _get_file_id(url, session=session, driver_provider=_get_driver)
                            book['file_id'] = file_id
                            _save_books_index(path_to_idx, all_books)
                        print(f"Visiting book page: {file_id}")
                        if book.get('ext'):
                            page_extensions = book['ext']
                        else:
                            page_extensions = _get_page_extensions(file_id, session=session, driver_provider=_get_driver)

                        if file_id != book.get('file_id') or page_extensions != book.get('ext'):
                            book['file_id'] = file_id
                            book['ext'] = page_extensions
                            _save_books_index(path_to_idx, all_books)

                        download_page_images(
                            file_id,
                            page_extensions,
                            session=session,
                            driver=driver,
                            driver_provider=_get_driver,
                            book_page_url=url,
                        )
                        book['pdf_file'] = _create_pdf(book)
                        _save_books_index(path_to_idx, all_books)
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
            _save_books_index(path_to_idx, all_books)
            print(f"Interrupted; saved current index state to {path_to_idx}")
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


def _save_books_index(path_to_idx, all_books):
    dump_json_atomic(all_books, path_to_idx)


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
    response = session.get(book_page_url, timeout=PDF_REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    details = _response_details(response)
    _raise_for_auth_response(details, "Litres rejected current SID while opening book page")
    match = re.search(r'release_file_id\\?":(\d+)', response.text)
    return match.group(1) if match else None


def _get_content_type_from_book_page(book_page_url, session, driver_provider=None):
    try:
        response = session.get(book_page_url, timeout=PDF_REQUEST_TIMEOUT_SECONDS)
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
    url = f"{domain}/pages/get_pdf_js/?file={file_id}"
    if session:
        try:
            with session.get(url, timeout=PDF_REQUEST_TIMEOUT_SECONDS) as r:
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
    with requests.get(url, headers=headers, timeout=PDF_REQUEST_TIMEOUT_SECONDS) as r:
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
    artifacts_dir = get_in_workdir(f"../__artifacts/litres/images/{file_id}")
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

        url = f"{domain}/pages/get_pdf_page/?file={file_id}&page={page_no}&rt=w{p[page_no]['w']}&ft={p[page_no]['ext']}"

        request = session.get if session else requests.get
        request_kwargs = {"timeout": PDF_REQUEST_TIMEOUT_SECONDS}
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


def _save_pdf_page_image(image_content, response, result_file, url):
    tmp_file = _temporary_path(result_file)
    try:
        img = Image.open(io.BytesIO(image_content))
    except UnidentifiedImageError as exc:
        raise ValueError(_format_pdf_page_response_error(response, url)) from exc
    try:
        with img:
            img.save(tmp_file, format="PNG", dpi=(RAW_PAGE_DPI, RAW_PAGE_DPI), optimize=True)
        if not _is_valid_image_file(tmp_file):
            raise ValueError(_format_pdf_page_response_error(response, url))
        os.replace(tmp_file, result_file)
    finally:
        _remove_if_exists(tmp_file)


def _is_valid_image_file(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except (OSError, UnidentifiedImageError):
        return False


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


def _should_retry_with_browser(exc):
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) in {401, 403}


def _should_retry_response_with_browser(response):
    content_type = (response.get("content_type") or "").lower()
    text = (response.get("text") or "").lower()
    return content_type.startswith("text/html") and any(marker.lower() in text for marker in BLOCKED_MARKERS)


def _is_invalid_selenium_session_error(exc):
    try:
        from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
    except ImportError:
        return "invalid session id" in str(exc).lower()
    return isinstance(exc, InvalidSessionIdException) or (
        isinstance(exc, WebDriverException) and "invalid session id" in str(exc).lower()
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


def _fetch_pdf_page_with_browser(driver, page_url, book_page_url=None):
    try:
        image_content, content_type = _fetch_binary_with_browser(driver, page_url)
    except ValueError:
        print(f"Litres browser fetch failed; warming browser session: {page_url}")
        _warm_up_browser_for_protected_url(driver, page_url, book_page_url)
        return _fetch_binary_with_browser_cookies(driver, page_url, referer=book_page_url)

    response = _binary_response_details(image_content, content_type)
    if not _should_retry_response_with_browser(response):
        return image_content, content_type

    print(f"Litres browser fetch returned anti-bot page; warming browser session: {page_url}")
    _warm_up_browser_for_protected_url(driver, page_url, book_page_url)
    return _fetch_binary_with_browser_cookies(driver, page_url, referer=book_page_url)


def _fetch_binary_with_browser_cookies(driver, url, referer=None):
    headers = _get_litres_page_image_headers(driver, referer=referer)
    with requests.get(url, headers=headers, timeout=PDF_REQUEST_TIMEOUT_SECONDS) as response:
        response.raise_for_status()
        return response.content, response.headers.get("content-type")


def _warm_up_browser_for_protected_url(driver, protected_url, context_url=None):
    if context_url:
        driver.get(context_url)
        _wait_for_browser_challenge(driver)
    driver.get(protected_url)
    _wait_for_browser_challenge(driver)


def _wait_for_browser_challenge(driver):
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.support.ui import WebDriverWait

    timeout = _get_pdf_browser_challenge_wait_seconds()
    print(f"Waiting up to {timeout}s for Litres browser challenge to clear")
    try:
        WebDriverWait(driver, timeout).until(
            lambda current: not any(marker.lower() in current.page_source.lower() for marker in BLOCKED_MARKERS)
        )
    except TimeoutException:
        # Keep the original non-image diagnostic from the subsequent fetch; it contains the exact URL and response body.
        return


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


def _get_litres_page_image_headers(driver, referer=None):
    headers = _get_litres_headers(driver)
    headers.update(
        {
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "same-origin",
        }
    )
    if referer:
        headers["Referer"] = referer
    return headers


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


def _temporary_path(path):
    directory = os.path.dirname(path)
    suffix = os.path.splitext(path)[1]
    digest = hashlib.md5(os.path.abspath(path).encode("utf-8")).hexdigest()
    return os.path.join(directory, f".tmp.{os.getpid()}.{digest}{suffix}")


def _remove_if_exists(path):
    if os.path.exists(path):
        os.remove(path)


def _remove_stale_temporary_files(directory):
    for pattern in ("*.tmp.*", ".tmp.*"):
        for tmp_file in glob.glob(os.path.join(directory, pattern)):
            _remove_if_exists(tmp_file)


def _create_pdf(book):
    """
    Create pdf from downloaded pages images
    """
    file_id = book['file_id']
    artifacts_dir = get_in_workdir(f"../__artifacts/litres/images/{file_id}")
    pdf_dir = get_in_workdir("../__artifacts/litres/docs")
    os.makedirs(pdf_dir, exist_ok=True)
    _remove_stale_temporary_files(pdf_dir)

    name_with_ext = f"{book['full_name']}.pdf"
    pdf_file = os.path.join(pdf_dir, name_with_ext)
    if _is_valid_pdf_file(pdf_file):
        return pdf_file

    tmp_pdf_file = _temporary_path(pdf_file)
    options = _get_pdf_compression_options()
    try:
        with pymupdf.open() as doc:
            # sort pages by number
            images = sorted([f for f in os.listdir(artifacts_dir)], key=lambda x: int(x.split(".")[0]))
            for page in track(images, description=f"Creating pdf for file: {file_id}"):
                image_bytes = _compressed_page_jpeg_bytes(os.path.join(artifacts_dir, page), options)
                with pymupdf.open(stream=image_bytes, filetype="jpeg") as img:
                    rect = img[0].rect  # pic dimension
                    with pymupdf.open("pdf", img.convert_to_pdf()) as img_pdf:
                        page = doc.new_page(width=rect.width, height=rect.height)
                        page.show_pdf_page(rect, img_pdf, 0)  # image fills the page

            doc.save(tmp_pdf_file)
        if not _is_valid_pdf_file(tmp_pdf_file):
            raise ValueError(f"Created invalid PDF: {tmp_pdf_file}")
        os.replace(tmp_pdf_file, pdf_file)
    finally:
        _remove_if_exists(tmp_pdf_file)
    return pdf_file


def _is_valid_pdf_file(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    try:
        with pymupdf.open(path) as doc:
            return doc.page_count > 0
    except pymupdf.FileDataError:
        return False


def _get_pdf_compression_options():
    config = read_config() or {}
    pdf_config = config.get("pdf") or {}
    options = {
        "jpeg_quality": int(pdf_config.get("jpeg_quality", PDF_DEFAULT_JPEG_QUALITY)),
        "max_width": pdf_config.get("max_width", PDF_DEFAULT_MAX_WIDTH),
        "dpi": int(pdf_config.get("dpi", PDF_DEFAULT_DPI)),
    }
    if options["max_width"] is not None:
        options["max_width"] = int(options["max_width"])

    if not 1 <= options["jpeg_quality"] <= 100:
        raise ValueError("pdf.jpeg_quality must be between 1 and 100")
    if options["max_width"] is not None and options["max_width"] <= 0:
        raise ValueError("pdf.max_width must be positive or null")
    if options["dpi"] <= 0:
        raise ValueError("pdf.dpi must be positive")
    return options


def _get_pdf_browser_headless():
    config = read_config() or {}
    pdf_config = config.get("pdf") or {}
    return _config_bool(pdf_config.get("browser_headless", PDF_DEFAULT_BROWSER_HEADLESS), "pdf.browser_headless")


def _get_pdf_browser_challenge_wait_seconds():
    config = read_config() or {}
    pdf_config = config.get("pdf") or {}
    value = int(pdf_config.get("browser_challenge_wait_seconds", PDF_DEFAULT_BROWSER_CHALLENGE_WAIT_SECONDS))
    if value <= 0:
        raise ValueError("pdf.browser_challenge_wait_seconds must be positive")
    return value


def _config_bool(value, name):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    raise ValueError(f"{name} must be true or false")


def _compressed_page_jpeg_bytes(image_path, options):
    with Image.open(image_path) as source:
        source.load()
        image = _to_rgb_image(source)

    max_width = options["max_width"]
    if max_width and image.width > max_width:
        ratio = max_width / image.width
        size = (max_width, max(1, round(image.height * ratio)))
        image = image.resize(size, _resample_lanczos())

    output = io.BytesIO()
    image.save(
        output,
        format="JPEG",
        quality=options["jpeg_quality"],
        dpi=(options["dpi"], options["dpi"]),
        optimize=True,
    )
    return output.getvalue()


def _to_rgb_image(image):
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    if image.mode == "RGB":
        return image.copy()
    return image.convert("RGB")


def _resample_lanczos():
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")
