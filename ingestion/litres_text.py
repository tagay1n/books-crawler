"""Downloads Litres text books by fetching JS page fragments, converts the structured content into markdown with images and footnotes, and stores artifacts under workdir."""
from .runtime_config import option as operational_option

import contextlib
import json
import os
import re
import shutil
import unicodedata
from urllib.parse import urlparse, parse_qs

from .litres_utils import requests
import typer


from .litres_index import _open_reader_url
from .litres_utils import create_driver, get_in_workdir, get_hash, get_sid

PREVIEW_MARKERS = (
    "The end of the free preview",
)


def _download_page_descriptions(book, driver=None):
    url = book['url']
    digest = book.get('hash') or get_hash(url)
    artifacts_dir = get_in_workdir("js")
    os.makedirs(artifacts_dir, exist_ok=True)
    completed_dir = os.path.join(artifacts_dir, digest)
    if os.path.exists(completed_dir) and not _must_refresh_text_cache(book):
        if not book.get("resource_url"):
            book["resource_url"] = _resolve_resource_url(url, driver, prefer_reader=book.get("subscription"))
        return completed_dir
    incompleted_dir = completed_dir + ".part"
    if os.path.exists(incompleted_dir):
        shutil.rmtree(incompleted_dir)
    os.makedirs(incompleted_dir, exist_ok=True)

    resource_url = _resolve_resource_url(url, driver, prefer_reader=book.get("subscription"))
    book['resource_url'] = resource_url
    counter = 0
    headers = _headers()
    while True:
        file_name = f"{'{:03d}'.format(counter)}.js"
        counter += 1
        output_path = os.path.join(incompleted_dir, file_name)
        if not os.path.exists(output_path):
            file_url = f"{resource_url}{file_name}"
            resp = requests.get(file_url, headers=headers, timeout=operational_option('litres_text', 'request_timeout_seconds'))
            if resp.status_code == 404:
                break
            elif resp.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(resp.content)
            else:
                raise ValueError(f"Could not download file: {file_url}, resp: {resp}")

    if os.path.exists(completed_dir):
        backup_dir = completed_dir + ".stale"
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        os.rename(completed_dir, backup_dir)
    os.rename(incompleted_dir, completed_dir)
    return completed_dir


def _must_refresh_text_cache(book):
    return book.get("subscription") and (
        not book.get("resource_url") or _is_public_text_resource_url(book.get("resource_url"))
    )


def _resolve_resource_url(url, driver=None, prefer_reader=False):
    if prefer_reader:
        return _resolve_resource_url_from_reader(url, driver)

    if resource_url := _guess_resource_url(url):
        if _resource_url_exists(resource_url):
            return resource_url

    return _resolve_resource_url_from_reader(url, driver)


def _resolve_resource_url_from_reader(url, driver=None):
    with _driver_context(driver) as active_driver:
        reader_url = _open_reader_url(url, active_driver)
        base_url = _base_url_from_reader_url(reader_url, url)
        return f"{operational_option('litres_consts', 'domain')}{base_url}json/"


def _guess_resource_url(url):
    if match := re.search(r"-(\d+)/?$", urlparse(url).path):
        return f"{operational_option('litres_consts', 'domain')}/pub/t/{match.group(1)}.json/"
    return None


def _resource_url_exists(resource_url):
    try:
        resp = requests.get(f"{resource_url}000.js", headers=_headers(), timeout=operational_option('litres_text', 'request_timeout_seconds'))
    except requests.RequestException:
        return False
    return resp.status_code == 200


def _is_public_text_resource_url(resource_url):
    return bool(resource_url and "/pub/t/" in resource_url)


def _headers():
    return {
        "Cookie": f"SID={get_sid()};",
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    }


def _driver_context(driver=None):
    if driver:
        return contextlib.nullcontext(driver)
    return create_driver()


def _base_url_from_reader_url(reader_url, book_url):
    parsed_url = urlparse(reader_url)
    queries = parse_qs(parsed_url.query)
    if base_url := queries.get("baseurl"):
        return base_url[0]
    raise ValueError(f"Could not find text resource base URL for {book_url}; reader URL was {reader_url}")


def textify(item, ctxt, prefix="", suffix=""):
    accumulator = ""
    if isinstance(item, dict):
        ty = item['t']
        c = item.get('c')
        match ty:
            case "title" if c:
                title_depth = len(item['xp'])
                # the deeper the title, the more hashes we need
                prefix = '#' * max(title_depth - 1, 1) + ' '
                accumulator += textify(c, ctxt, prefix=prefix, suffix='\n')
            case ("p" | "div" | "epigraph" | "subtitle" | 'blockquote' | 'span') if c:
                accumulator += textify(c, ctxt, prefix=prefix, suffix=suffix)
            case "subscription" if c:
                accumulator += textify(c, ctxt, prefix="(", suffix=")")
            case 'sup' if c:
                accumulator += textify(c, ctxt, prefix="<sup>", suffix="</sup>")
            case 'sub' if c:
                accumulator += textify(c, ctxt, prefix="<sub>", suffix="</sub>")
            case "em" if c:
                accumulator += textify(c, ctxt, prefix='*', suffix='*')
            case "strong" if c:
                accumulator += textify(c, ctxt, prefix='**', suffix='**')
            case "img":
                image_store_dir = os.path.join(ctxt['workdir'], 'media')
                os.makedirs(image_store_dir, exist_ok=True)

                image_location = os.path.join(image_store_dir, item['s'])
                image_url = f"{ctxt['book']['resource_url']}{item['s']}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
                }
                if not os.path.exists(image_location):
                    with requests.get(image_url, headers=headers, timeout=operational_option('litres_text', 'request_timeout_seconds')) as r:
                        r.raise_for_status()
                        with open(image_location, "wb") as f:
                            f.write(r.content)

                rel_path = os.path.join('media', item['s'])
                accumulator += f"![{item['src']}]({rel_path})\n\n"
            case ("stanza" | "poem") if c:
                accumulator += textify(c, ctxt, prefix=prefix, suffix='<br>')
            case 'note':
                res = textify(item['f'], ctxt, prefix=prefix, suffix=suffix)
                if not res:
                    print(f"Skipping an empty note: {json.dumps(item, indent=4, ensure_ascii=False)}")
                    return accumulator
                if _match := re.match(r'^#+ (\\\*+|\d+)\n(.+)$', res):
                    _f = f"[^{ctxt['footn_counter']}]"
                    ctxt['footn_counter'] += 1
                    accumulator += _f
                    footnote_text = _clear_string(_match.group(2)).replace('\n', '').strip()
                    ctxt['f'].append(f"{_f}: {footnote_text}")
                else:
                    print(f"Could not extract footer info: `{res}`")
                    raise typer.Abort()
            case 'footnote':
                accumulator += textify(c, ctxt, prefix=prefix, suffix=suffix)
            case ('nobr' | 'br') if c:
                accumulator += textify(c, ctxt, prefix=prefix, suffix=suffix)
            case 'br':
                pass
            case 'code' if c:
                accumulator += textify(c, ctxt, prefix='`', suffix='`')
            case _ if c:
                print(f"Unknown item type: {ty}: {json.dumps(item, indent=4, ensure_ascii=False)}")
                raise typer.Abort()
    elif isinstance(item, list):
        if all(isinstance(i, str) for i in item):
            item = [textify(i, ctxt, '', '') for i in item]
            accumulator += prefix + ''.join(item) + suffix
        else:
            for i in item:
                if isinstance(i, dict):
                    accumulator += f"{prefix}{textify(i, ctxt, '', '')}{suffix}"
                else:
                    accumulator += textify(i, ctxt, prefix, suffix)
    elif isinstance(item, str):
        accumulator += _clear_string(item)
    else:
        print(f"Item neither list, dict or str: {item}")
        raise typer.Abort()
    return accumulator


def _clear_string(s):
    return s.replace('\xad', '').replace('\xa0', ' ').replace(' ', '').replace('*', '\\*').replace('`', '\\`')


def _contains_preview_marker(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return any(marker in content for marker in PREVIEW_MARKERS)


def _raise_if_preview_markdown(path, book):
    if _contains_preview_marker(path):
        os.remove(path)
        raise ValueError(
            "Litres returned preview-only text. "
            f"Reader-authenticated resource URL was not resolved for {book['url']}."
        )


def _markdown_output_name(book):
    return _legacy_path_name(book["full_name"])


def _legacy_path_name(value):
    value = unicodedata.normalize("NFC", value)
    value = value.replace("/", "|")
    value = re.sub(r"[\x00-\x1f]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value or "book"
