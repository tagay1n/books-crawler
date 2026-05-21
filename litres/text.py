"""Downloads Litres text books by fetching JS page fragments, converts the structured content into markdown with images and footnotes, and stores artifacts under workdir."""

import contextlib
import json
import os
import re
import unicodedata
from urllib.parse import urlparse, parse_qs

import requests
import typer
from rich.progress import track

from consts import domain
from index import _open_reader_url
from utils import create_driver, dump_json_atomic, get_in_workdir, get_hash, get_sid

def visit_text_books_pages():
    path_to_idx = get_in_workdir("../__artifacts/litres/books-index.json")
    with open(path_to_idx, "r") as f:
        all_books = json.load(f)

    books = _get_text_books_to_visit(all_books)

    print(f"Visiting {len(books)} text docs")

    failed = 0
    try:
        with create_driver() as driver:
            for book in track(books, description="Downloading text books"):
                print(f"Processing book: {book['full_name']}")
                print(f"Book URL: {book['url']}")
                try:
                    artifacts_dir = _download_page_descriptions(book, driver=driver)
                    book["markdown_file"] = _make_up_markdown(artifacts_dir, book, driver=driver)
                    book.pop("download_error", None)
                except Exception as e:
                    failed += 1
                    book["download_error"] = str(e)
                    print(f"Error processing text book: {book['url']}")
                    print(e)
                _save_books_index(path_to_idx, all_books)
    except KeyboardInterrupt:
        _save_books_index(path_to_idx, all_books)
        print(f"Interrupted; saved current index state to {path_to_idx}")
        raise
    if failed:
        print(f"Finished with {failed} text book download error(s)")


def _get_text_books_to_visit(all_books):
    """
    Return text books that still need markdown output or previously failed.
    """
    return [
        book
        for book in all_books.values()
        if book.get("content_type") == "text"
        and (book.get("download_error") or not book.get("markdown_file"))
    ]


def _save_books_index(path_to_idx, all_books):
    dump_json_atomic(all_books, path_to_idx)


def _download_page_descriptions(book, driver=None):
    url = book['url']
    digest = book.get('hash') or get_hash(url)
    artifacts_dir = get_in_workdir("../__artifacts/litres/js")
    os.makedirs(artifacts_dir, exist_ok=True)
    completed_dir = os.path.join(artifacts_dir, digest)
    if os.path.exists(completed_dir):
        if not book.get("resource_url"):
            book["resource_url"] = _resolve_resource_url(url, driver)
        return completed_dir
    incompleted_dir = completed_dir + ".part"
    os.makedirs(incompleted_dir, exist_ok=True)

    resource_url = _resolve_resource_url(url, driver)
    book['resource_url'] = resource_url
    counter = 0
    headers = _headers()
    while True:
        file_name = f"{'{:03d}'.format(counter)}.js"
        counter += 1
        output_path = os.path.join(incompleted_dir, file_name)
        if not os.path.exists(output_path):
            file_url = f"{resource_url}{file_name}"
            resp = requests.get(file_url, headers=headers, timeout=20)
            if resp.status_code == 404:
                break
            elif resp.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(resp.content)
            else:
                raise ValueError(f"Could not download file: {file_url}, resp: {resp}")

    os.rename(incompleted_dir, completed_dir)
    return completed_dir


def _resolve_resource_url(url, driver=None):
    if resource_url := _guess_resource_url(url):
        if _resource_url_exists(resource_url):
            return resource_url

    with _driver_context(driver) as active_driver:
        reader_url = _open_reader_url(url, active_driver)
        base_url = _base_url_from_reader_url(reader_url, url)
        return f"{domain}{base_url}json/"


def _guess_resource_url(url):
    if match := re.search(r"-(\d+)/?$", urlparse(url).path):
        return f"{domain}/pub/t/{match.group(1)}.json/"
    return None


def _resource_url_exists(resource_url):
    try:
        resp = requests.get(f"{resource_url}000.js", headers=_headers(), timeout=20)
    except requests.RequestException:
        return False
    return resp.status_code == 200


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


def _make_up_markdown(input_dir, book, driver=None):
    # directory for resulting markdown file
    output_name = _markdown_output_name(book)
    output_dir = get_in_workdir(f"../__artifacts/litres/markdown/{output_name}")
    os.makedirs(output_dir, exist_ok=True)

    # path to resulting markdown file
    output_file = os.path.join(output_dir, f"{output_name}.md")
    if os.path.exists(output_file):
        return output_file
    # temporary file to store partial results, will be renamed to output_file at the end
    partial_output = output_file + ".part"

    files = sorted([f for f in os.listdir(input_dir) if f.endswith('.js')], key=lambda x: int(x.split(".")[0]))
    all_footnotes = []
    context = {'f': all_footnotes, 'book': book, 'workdir': output_dir, 'footn_counter': 1}
    with open(partial_output, "w") as out, _driver_context(driver) as active_driver:
        for f in files:
            with open(os.path.join(input_dir, f), "r") as f:
                results = []
                for item in active_driver.execute_script("let c = " + f.read() + "; return c;"):
                    if res := textify(item, context).rstrip('\n'):
                        results.append(res)
                out.write('\n\n'.join(results))

        if all_footnotes:
            out.write('\n\n')
            out.write('\n\n'.join(all_footnotes))

    os.rename(partial_output, output_file)
    return output_file


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
                    "Cookie": f"SID={get_sid()};",
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
                }
                if not os.path.exists(image_location):
                    with requests.get(image_url, headers=headers, timeout=20) as r:
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


def _markdown_output_name(book):
    return _legacy_path_name(book["full_name"])


def _legacy_path_name(value):
    value = unicodedata.normalize("NFC", value)
    value = value.replace("/", "|")
    value = re.sub(r"[\x00-\x1f]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value or "book"
