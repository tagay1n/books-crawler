import json
import os
from urllib.parse import urlparse, parse_qs

import requests
import typer
from rich.progress import track
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import re
from consts import domain
from utils import get_in_workdir, create_driver, get_hash, get_sid


def visit_text_books_pages():
    path_to_idx = get_in_workdir("../__artifacts/litres/books-index.json")
    with open(path_to_idx, "r") as f:
        all_books = json.load(f)

    books = [book for book in all_books.values() if book['content_type'] == 'text']

    print(f"Visiting {len(books)} text docs")

    for book in track(books, description="Downloading text books"):
        print(f"Processing book: {book['full_name']}")
        artifacts_dir = _download_page_descriptions(book)
        with open(path_to_idx, "w") as f:
            json.dump(all_books, f, indent=4, ensure_ascii=False)
        _make_up_markdown(artifacts_dir, book)



def _download_page_descriptions(book):
    url = book['url']
    digest = book.get('hash') or get_hash(url)
    artifacts_dir = get_in_workdir("../__artifacts/litres/js")
    os.makedirs(artifacts_dir, exist_ok=True)
    completed_dir = os.path.join(artifacts_dir, digest)
    if os.path.exists(completed_dir):
        return completed_dir
    incompleted_dir = completed_dir + ".part"
    os.makedirs(incompleted_dir, exist_ok=True)

    with create_driver() as driver:
        driver.get(url)
        read_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[class^="Button_textContainer__"]')))
        read_button.click()
        reader_url = driver.current_url
        parsed_url = urlparse(reader_url)
        queries = parse_qs(parsed_url.query)
        base_url = queries['baseurl'][0]
        resource_url = f"{domain}{base_url}json/"
        book['resource_url'] = resource_url
        counter = 0
        while True:
            file_name = f"{'{:03d}'.format(counter)}.js"
            counter += 1
            output_path = os.path.join(incompleted_dir, file_name)
            if not os.path.exists(output_path):
                file_url = f"{resource_url}{file_name}"
                resp = requests.get(file_url, headers={"Cookie": f"SID={get_sid()};"})
                if resp.status_code == 404:
                    break
                elif resp.status_code == 200:
                    with open(output_path, "wb") as f:
                        f.write(resp.content)
                else:
                    raise ValueError(f"Could not download file: {file_url}, resp: {resp}")

    os.rename(incompleted_dir, completed_dir)
    return completed_dir


def _make_up_markdown(input_dir, book):
    # directory for resulting markdown file
    output_dir = get_in_workdir(f"../__artifacts/litres/markdown/{book['full_name']}")
    os.makedirs(output_dir, exist_ok=True)

    # path to resulting markdown file
    output_file = os.path.join(output_dir, f"{book['full_name']}.md")
    if os.path.exists(output_file):
        return
    # temporary file to store partial results, will be renamed to output_file at the end
    partial_output = output_file + ".part"

    files = sorted([f for f in os.listdir(input_dir) if f.endswith('.js')], key=lambda x: int(x.split(".")[0]))
    all_footnotes = []
    context = {'f': all_footnotes, 'book': book, 'workdir': output_dir, 'footn_counter': 1}
    with open(partial_output, "w") as out:
        for f in files:
            with open(os.path.join(input_dir, f), "r") as f, create_driver() as driver:
                results = []
                for item in driver.execute_script("let c = " + f.read() + "; return c;"):
                    if res := textify(item, context).rstrip('\n'):
                        results.append(res)
                out.write('\n\n'.join(results))

        if all_footnotes:
            out.write('\n\n')
            out.write('\n\n'.join(all_footnotes))

    os.rename(partial_output, output_file)


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
                if not os.path.exists(image_location):
                    with requests.get(image_url, headers={"Cookie": f"SID={get_sid()};"}) as r:
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
    return s.replace('\xad', '').replace('\xa0', ' ').replace(' ', '').replace('*', '\*').replace('`', '\`')