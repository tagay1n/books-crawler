"""Decrypts downloaded document parts, merges PDFs with metadata, uploads artifacts to storage, and updates the index for completed items."""

from .runtime_config import ConfiguredThreadPoolExecutor, option as operational_option
import itertools
from Crypto.Cipher import AES
import os
import re
from Crypto.Util.Padding import unpad
import zipfile
import pymupdf
from .milli_kitaphana_utils import read_config, load_index_file, dump_index, download_part
from .milli_kitaphana_progress_wrapper import ProgressWrapper
import json
import base64
import copy
import hashlib
from unidecode import unidecode


class LimitedBookError(ValueError):
    """The decrypted provider manifest explicitly withholds full-text parts."""

def _get_not_decrypted_docs(index):
    not_decrypted_docs = []
    for card_path, meta in index.items():
        if not meta.get('decrypted', False) and meta.get('enc_part_paths'):
            not_decrypted_docs.append((card_path, meta))

    return not_decrypted_docs


def _upstream_metadata(meta):
    # Only source claims belong in Gemini context; never include credentials,
    # filesystem paths, acquisition flags or publication recovery state.
    fields = ('title', 'author', 'publish_year', 'lang', 'collection', 'tags',
              'properties_raw', 'classification', 'integrated_description',
              'doc_url', 'doc_card_url', 'download_code', 'url', 'access', 'record_type')
    return {field: copy.deepcopy(meta[field]) for field in fields if field in meta}


def _remove_decryption_recovery_fields(meta):
    for field in ("enc_part_paths", "format_url", "decryption_key", "decryption_key_iv"):
        meta.pop(field, None)


def decrypt_doc_parts(context):
    enc_part_paths = context['meta']['enc_part_paths']
    parts_count = len(enc_part_paths)
    with ConfiguredThreadPoolExecutor(max_workers=operational_option('milli_kitaphana_decrypt', 'workers')) as pool:
        # decrypt the parts
        counter = itertools.count()
        context['progress'].main(f"Decrypted (0/{parts_count}) parts")
        dec_part_paths = list(pool.map(lambda en: _decrypt_file_task(
            context, en[0], en[1], en[2], counter, parts_count), [(i['num'], i['part_url'], i['enc_unzip_dir']) for i in enc_part_paths if i]
        ))

     # accumulate all parts into one pdf doc
    context["progress"].main("Merging document parts...")
    # decrypt the metadata
    meta_url = "part0.zip"
    enc_zip_dir = download_part(context, meta_url)
    meta_dir = _decrypt_file(context, meta_url, enc_zip_dir)

    with open(os.path.join(meta_dir, "source.json"), "r", encoding="utf-8") as file:
        source_meta = json.load(file)

    parts = source_meta["parts"]
    if not isinstance(parts, list) or not parts:
        raise ValueError('Document metadata contains no book parts')
    if any(not part.get('url') for part in parts):
        raise LimitedBookError('Document metadata contains restricted book parts')
    if len(parts) != parts_count or sorted(num for num, _ in dec_part_paths) != list(range(parts_count)):
        raise ValueError('Encrypted book parts are missing or have duplicate indexes')
    with pymupdf.open() as acc:
        for num, path in sorted(dec_part_paths):
            # open the encrypted pdf part
            with pymupdf.open(path) as pdf_doc:
                password = f"rbooks2-{source_meta['fingerprint'].split('-')[-1]}-{num+1}"
                if pdf_doc.needs_pass and not pdf_doc.authenticate(password):
                    raise ValueError('PDF part password verification failed')
                if pdf_doc.page_count <= 0:
                    raise ValueError('PDF part is empty')
                expected_pages = parts[num].get('pagesCount')
                if isinstance(expected_pages, int) and pdf_doc.page_count != expected_pages:
                    raise ValueError('PDF part page count differs from source metadata')
                # add the pages to the accumulator
                acc.insert_pdf(pdf_doc)

        acc.set_pagemode(source_meta["pageMode"])
        acc.set_pagelayout(source_meta["pageLayout"])
        toc = _get_toc(context, meta_dir, parts)
        acc.set_toc(toc)
        scribed_metadata = context["meta"]
        if classification := scribed_metadata.get("classification"):
            if classification not in scribed_metadata["integrated_description"]:
                scribed_metadata["integrated_description"].append(classification)
        _metadata = {
            "title": scribed_metadata["title"],
            "subject": "; ".join(scribed_metadata["integrated_description"])
        }
        if author := scribed_metadata.get("author"):
            _metadata["author"] = author
        if tags := scribed_metadata.get("tags"):
            _metadata["keywords"] = ", ".join(tags)
        acc.set_metadata(_metadata)

        # save the final pdf
        file_name = _build_output_filename(scribed_metadata)
        output_path = os.path.normpath(os.path.join(context["work_dir"], file_name))
        with open(output_path + ".part", "wb") as file:
            file.write(acc.write(no_new_id=True))
        os.replace(output_path + ".part", output_path)

        return output_path


def _decrypt_file_task(context, num, part_url, enc_unzip_dir, counter, total):
    res = num, _decrypt_file(context, part_url, enc_unzip_dir)
    context['progress'].main(f"Decrypted ({next(counter) + 1}/{total}) parts")
    return res


def _decrypt_file(context, part, enc_unzip_dir):
    work_dir = context["work_dir"]
    part_name, ext = part.split(".")

    enc_file_path = os.path.join(enc_unzip_dir, "enc.dat")
    with open(enc_file_path, "rb") as file:
        aes_key = AES.new(
            key=base64.b64decode(context['meta']["decryption_key"]),
            mode=AES.MODE_CBC,
            iv=base64.b64decode(context['meta']["decryption_key_iv"])
        )
        # Accumulate chunks once; repeated bytes concatenation copies the whole
        # document on every iteration and makes large recovery runs quadratic.
        decrypted_chunks = []
        total_size = os.path.getsize(enc_file_path)
        task = context["progress"].decrypt(part, total_size)
        while True:
            chunk = file.read(64 * 1024)
            if not chunk:
                break
            decrypted_chunks.append(aes_key.decrypt(chunk))
            context['progress']._aux.update(task, advance=len(chunk))
        context['progress']._aux.update(task, description=f"Decrypted {part}")
        context['progress']._aux.stop_task(task)

    # unpad the decrypted data
    decrypted_data = unpad(b"".join(decrypted_chunks), AES.block_size)
    # save the decrypted file
    dec_path = os.path.join(work_dir, part_name + "_decrypted." + ext)

    with open(dec_path, "wb") as dec_zip:
        dec_zip.write(decrypted_data)

    # unzip the decrypted file
    if ext == "zip":
        dec_unzip_dir = os.path.join(work_dir, part_name + "_decrypted")
        with zipfile.ZipFile(dec_path, 'r') as dec_zip:
            dec_zip.extractall(dec_unzip_dir)
        return dec_unzip_dir
    else:
        # if the decrypted file is not a zip file, just return the path to the file
        return dec_path


def _get_toc(context, meta_dir, parts):
    # process the outline
    toc = []
    outline_path = os.path.join(meta_dir, "outline.json")
    if os.path.exists(outline_path):
        with open(outline_path, "r", encoding="utf-8") as file:
            outline_meta = json.load(file)
            available_pages = sum([i['pagesCount']
                                  for i in parts if i.get("url")])
            context['meta']['available_pages'] = available_pages
            for i in outline_meta:
                title = i['title'].strip().rstrip('.')
                page_no = 1 + int(i['dest'][0])
                toc.append([1, title, page_no if page_no <= available_pages else -1])
    return toc


def _safe_filename(name: str, default: str = "document") -> str:
    # Remove Windows-invalid characters and control chars, then trim trailing dots/spaces.
    cleaned = re.sub(r'[<>:"/\\\\|?*]', "-", name)
    cleaned = "".join(ch for ch in cleaned if ord(ch) >= 32).strip().rstrip(".")
    if not cleaned:
        cleaned = default
    reserved = {
        "con", "prn", "aux", "nul",
        "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
        "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
    }
    if cleaned.lower() in reserved:
        cleaned = f"_{cleaned}"
    return cleaned


def _build_output_filename(meta: dict) -> str:
    title = meta.get("title", "document")
    download_code = meta.get("download_code", "")

    translit = unidecode(title)
    translit = re.sub(r"\s+", "_", translit).strip("_")

    if download_code:
        combined = f"{translit}__{download_code}"
    else:
        combined = translit

    combined = _safe_filename(combined)
    if len(combined) > 100:
        combined = f"{combined[:98]}__"

    return f"{combined}.pdf"


def _calculate_md5(file_path: str):
    """
    Calculates MD5 hash of the file

    :param file_path: path to the file
    :return: MD5 hash of the file
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(2048), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()
