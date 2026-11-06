"""Litres authenticated browser transport and response diagnostics."""
from .runtime_config import option as operational_option
import base64
from .litres_utils import requests, get_sid
from .litres_index import BLOCKED_MARKERS
from .litres_pdf_config import _get_pdf_browser_challenge_wait_seconds


class LitresAuthenticationError(ValueError):
    """Raised when Litres redirects protected PDF resources to the login page."""


def _raise_for_non_image_pdf_page_response(response, url):
    _raise_for_auth_response(response, "Litres rejected current SID while loading PDF page image")
    content_type = response["content_type"] or ""
    if content_type and not content_type.lower().startswith("image/"):
        raise ValueError(_format_pdf_page_response_error(response, url))


def _format_pdf_page_response_error(response, url):
    snippet = response["content"][:operational_option('litres_pdf_config', 'pdf_response_snippet_bytes')].decode("utf-8", errors="replace")
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
        snippet = " ".join(response["text"][:operational_option('litres_pdf_config', 'pdf_response_snippet_bytes')].split())
        raise ValueError(
            "Litres returned a non-JavaScript PDF metadata response; "
            f"url={url}; status={response['status']}; "
            f"content-type={response['content_type']}; body-start={snippet!r}"
        )


def _raise_for_auth_response(response, message):
    if "/auth/login/" in (response.get("url") or ""):
        raise LitresAuthenticationError(
            f"{message}. Update 'sid' in sources.litres in the selected operational YAML, then rerun the command."
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
    with requests.get(url, headers=headers, timeout=operational_option('litres_pdf_config', 'pdf_request_timeout_seconds')) as response:
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
