import requests
import os
import zipfile
import json
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
import base64
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from random import randbytes
import pytz
from datetime import datetime, timedelta
import string
import random as rnd
from progress_wrapper import ProgressWrapper
from rich import print
from multiprocessing.pool import ThreadPool
import itertools
from utils import read_config, load_index_file, dump_index, HOST, request, download_part, base_dir
import bs4 as bs
import re
from urllib.parse import urlparse
from decrypt import _decrypt_file

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning)

# URLS
DETAILS_URL = HOST + "/tt/dl/edoc2"


def download(with_limited, limit):
    index = load_index_file()
    # a dictionary with download code as key and book's card path as a value
    # the card path is a key in the index 
    code_to_card_path = {v['download_code']: k for k, v in index.items() if 'download_code' in v}
    if not (not_downloaded_docs := _get_not_downloaded_docs(index, with_limited, limit)):
        print("No docs for downloading, exiting...")
        return
    
    print(f"About to download {len(not_downloaded_docs)} document(s)")
    config = read_config()
    
    for card_path, meta in not_downloaded_docs:
        try:
            _scrap_doc_card(card_path, meta)
            download_code = meta['download_code']
            if (existing_card_path := code_to_card_path.get(download_code, None)) and existing_card_path != card_path:
                # here if item with such download code already exists in the index
                existing_meta = index[existing_card_path]
                # update item iterating right now, but remain 'doc_card_url'
                del existing_meta['doc_card_url']
                meta.update(existing_meta)
                
                # delete old meta item because it contains obsolete links
                del index[existing_card_path]
                code_to_card_path[download_code] = card_path
                print(f"Replaced old card path '{existing_card_path}' with new '{card_path}' for download code '{download_code}'")
                if not meta.get("broken", False) or meta.get("downloaded", None):
                    # if merged meta shows document downloading was not broken or downloaded then just proceed next,
                    # else just 
                    continue
            
            context = {
                "meta": meta,
                "config": config
            }
            with ProgressWrapper(context, card_path):
                _get_details(context)
                _get_dh_params(context)
                _dh_key_exchange(context)
                _download_by_code(context)
                
            meta["downloaded"] = "full" if meta['access'] == "open" else 'limited'
            meta['decrypted'] = False
            
        except KeyboardInterrupt:
            print("Interrupting....")
            return
        except BaseException as e:
            import traceback
            print(f"Error: {e} {traceback.format_exc()}")
        finally:
            dump_index(idx=index)
    
    
def _get_not_downloaded_docs(index, with_limited, limit=None):
    not_downloaded_docs = []
    for card_path, meta in index.items():
        if meta.get("broken", False):
            continue
        
        downloaded = meta.get("downloaded") 
        if not downloaded or (with_limited and downloaded != 'full'): 
            not_downloaded_docs.append((card_path, meta))

    not_downloaded_docs = sorted(not_downloaded_docs, key=lambda x: x[1].get('publish_year', "").strip('[]'), reverse=True)
    return not_downloaded_docs[:limit]


def _scrap_doc_card(card_path, meta):
    with request(method="GET", url=HOST + card_path) as r:
        soup = bs.BeautifulSoup(r.text, "html.parser")

    record = soup.select_one(".record")

    def __preprocess(__m):
        __m = __m.strip().rstrip(' .')
        if "Загл. с титул. экрана" in __m:
            return None
        elif "Электрон. версия печ. публикации" in __m:
            return None
        elif "Электрон. текстовые дан." in __m:
            return None

        __m = re.sub(r"\[Электронный ресурс\]|NEW!!!", "", __m)

        if "Электронный ресурс" in __m:
            if udk := re.search('.*(УДК.*)', __m):
                meta['classification'] = udk.group(1).strip()

            return None
        elif "Свободный доступ из сети Интернет" in __m:
            meta["access"] = "open"
            return None
        elif 'Ограниченный доступ из сети Интернет' in __m:
            meta["access"] = "limited"
            return None
        elif "Коллекция:" in __m:
            return None

        __m = re.sub(r"\s+", r" ", __m)
        return __m

    meta["integrated_description"] = [j for j in [
        __preprocess(i) for i in re.split(r"—|\n|;", record.text)] if j]

    if "download_code" not in meta:
        for i_ in record.select("a"):
            if (re.match(r'Эл?ектр?оннн?ы?ы?й рес?урс', i_.text.strip()) or
                # case for broken content management
                    i_.text.startswith("http://kitap.tatar.ru/dl")):
                meta["doc_url"] = i_['href']
                break
        else:
            raise ValueError("Could not parse document's url", HOST + card_path)
        meta["download_code"] = (urlparse(meta["doc_url"]).path
                                 .removeprefix('/dl')
                                 .removeprefix('/kitap.tatar.ru/dl')
                                 .strip('/')
                                 .replace('-', '_'))
    meta['doc_card_url'] = r.url






def _get_details(context):
    context["progress"].main("Requesting key details...")

    code = context["meta"]["download_code"]
    # path to the directory where the artifacts of the key exchange will be stored
    
    work_dir = os.path.join(base_dir, code)
    context["work_dir"] = work_dir
    # path to the zip file obtained from the server
    zip_path = os.path.join(work_dir, "key_exchange_response.zip")
    # path to the directory where the zip file will be unzipped
    unzip_dir = os.path.join(work_dir, "key_exchange_response")
    # path to the JSON file containing key details
    key_details = os.path.join(unzip_dir, "doc.json")

    # generate a random token1 for the requestpwd
    token1 = ''.join(rnd.choice(string.ascii_lowercase) for _ in range(9))

    with request("GET", DETAILS_URL, params={"code": code, "token1": token1}) as response:
        if response.headers.get("Content-Type") != "application/zip":
            raise ValueError(
                f"Unexpected content type: {response.headers.get('Content-Type')}")
        else:
            os.makedirs(work_dir, exist_ok=True)
            with open(zip_path, "wb") as file:
                file.write(response.content)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(unzip_dir)

    with open(key_details, "r", encoding="utf-8") as file:
        key_details = json.load(file)
    context.update(key_details)
    context['meta']['format_url'] = key_details['formatUrl']


def _get_dh_params(context):
    """
    This function sends signature of token2 to the server and receives Diffie-Hellman parameters.
    It uses the server's private RSA key to sign the token2.
    """
    context["progress"].main("Requesting Diffie-Hellman parameters...")

    # preparing AES key
    aes_key = hashlib.pbkdf2_hmac(
        hash_name=hashes.SHA256().name,
        dklen=32,
        password=context['config']["aes"]["raw_key"],
        salt=context['config']["aes"]["salt"],
        iterations=100
    )

    # Decrypting the private RSA key
    cipher = AES.new(aes_key, AES.MODE_CBC,
                     iv=context['config']["aes"]["default_iv"])
    pem_private_key = unpad(cipher.decrypt(
        context['config']["priv_key"]), AES.block_size)

    # Loading server's private key from PEM format
    rsa_priv_key = serialization.load_pem_private_key(
        pem_private_key, password=None)
    context["rsa_priv_key"] = rsa_priv_key

    token2 = context['token2'].encode()

    # Generate signature
    sig = _sign(rsa_priv_key, token2, context['config']['sig_prefix'])

    form_data = {
        "token2": token2,
        "s": base64.b64encode(sig),
    }

    with request(method="POST", url=HOST + context['keyUrl'], data=form_data) as resp:
        context['dh_params'] = base64.b64decode(resp.json()['data'])
        # here we can verify the server's signature, but we don't need it for now


def _dh_key_exchange(context):
    """
    This function performs Diffie-Hellman key exchange with the server.
    """
    context["progress"].main("Performing Diffie-Hellman key exchange...")

    dh_params = context['dh_params']
    # Offset for prime
    offset1 = dh_params[0]
    # Offset for generator
    offset2 = dh_params[1]
    # Flag indication if the secret should be truncated, ignored for now
    _ = dh_params[2] > 0

    prime = dh_params[3: 3 + offset1]
    generator = dh_params[3 + offset1:3 + offset1 + offset2]
    server_dh_pub_key = dh_params[3 + offset1 + offset2:]

    prime = int.from_bytes(prime, byteorder="big")
    generator = int.from_bytes(generator, byteorder="big")

    # Server's public key in DH exchange
    server_dh_pub_key = int.from_bytes(server_dh_pub_key, byteorder="big")

    # Simple implementation of Diffie-Hellman key exchange
    raw_local_priv_key = randbytes(16)
    local_dh_priv_key = int.from_bytes(raw_local_priv_key, "big") % prime
    local_dh_pub_key = pow(generator, local_dh_priv_key, prime)  # g^x mod p
    raw_local_dh_pub_key = local_dh_pub_key.to_bytes(16, byteorder="big")

    shared_secret = pow(server_dh_pub_key, local_dh_priv_key, prime)
    secret_as_bytes = shared_secret.to_bytes(16, byteorder="big")

    dh_sig = _sign(context["rsa_priv_key"],
                   raw_local_dh_pub_key, context['config']['sig_prefix'])

    form_data = {
        "token2": context['token2'].encode(),
        "dh": base64.b64encode(raw_local_dh_pub_key),
        "dh2": base64.b64encode(dh_sig),
    }

    with request(method="POST", url=HOST + context['keyUrl'], data=form_data) as resp:
        # decrypt the document key
        # this key will be used to encrypt the document later on
        ciphertext = base64.b64decode(resp.json()['data'])
        cipher = AES.new(secret_as_bytes, AES.MODE_CBC,
                         iv=context['config']["aes"]["default_iv"])
        res = unpad(cipher.decrypt(ciphertext), AES.block_size)
        raw_aes_key = res[:16]
        iv = res[16:]
        # context['meta']["decryption_key"] = raw_aes_key
        context['meta']["decryption_key"] = base64.b64encode(raw_aes_key).decode('ascii')
        # context['meta']["decryption_key_iv"] = iv
        context['meta']["decryption_key_iv"] = base64.b64encode(iv).decode('ascii')


def _download_by_code(context):
    # download the part with document metadata
    context["progress"].main("Downloading document metadata...")
    meta_url = "part0.zip"
    enc_zip_dir = download_part(context, meta_url)
    # decrypt the metadata
    meta_dir = _decrypt_file(context, meta_url, enc_zip_dir)

    with open(os.path.join(meta_dir, "source.json"), "r", encoding="utf-8") as file:
        source_meta = json.load(file)

    parts = source_meta["parts"]
    # process the outline
    # outline_path = os.path.join(meta_dir, "outline.json")
    # if os.path.exists(outline_path):
    #     with open(outline_path, "r", encoding="utf-8") as file:
    #         outline_meta = json.load(file)
    #         available_pages = sum([i['pagesCount']
    #                               for i in parts if i.get("url")])
    #         context['meta']['available_pages'] = available_pages
    #         toc = _prepare_toc(outline_meta, available_pages)
    # else:
    #     toc = []

    parts_count = len(parts)
    with ThreadPool(processes=8) as pool:
        # download the parts
        counter = itertools.count()
        context['progress'].main(f"Downloaded (0/{parts_count}) parts")
        if not context['meta'].get('access'):
            context['meta']['access'] = "open"
        enc_part_paths = pool.map(lambda en: _download_part_task(
            context, en[1], en[0], counter, parts_count), enumerate(parts)
        )
        context['meta']['enc_part_paths'] = [
            {
                'num': p[0],
                'part_url': p[1],
                'enc_unzip_dir': os.path.normpath(p[2]),
            }
            for p in enc_part_paths if p
        ]
    context['progress'].main(f"[bold green]Parts downloading complete[/bold green]")

    
    # with ThreadPool(processes=4) as pool:
    #     # decrypt the parts
    #     counter = itertools.count()
    #     context['progress'].main(f"Decrypted (0/{parts_count}) parts")
    #     dec_part_paths = pool.map(lambda en: _decrypt_file_task(
    #         context, en[0], en[1], en[2], counter, parts_count), [i for i in enc_part_paths if i])

    # accumulate all parts into one pdf doc
    # context["progress"].main("Merging document parts...")
    # with pymupdf.open() as acc:
    #     for num, path in dec_part_paths:
    #         # open the encrypted pdf part
    #         with pymupdf.open(path) as pdf_doc:
    #             password = f"rbooks2-{source_meta["fingerprint"].split("-")[-1]}-{num+1}"
    #             pdf_doc.authenticate(password)
    #             # add the pages to the accumulator
    #             acc.insert_pdf(pdf_doc)

    #     acc.set_pagemode(source_meta["pageMode"])
    #     acc.set_pagelayout(source_meta["pageLayout"])
    #     acc.set_toc(toc)
    #     scribed_metadata = context["meta"]
    #     if classification := scribed_metadata.get("classification"):
    #         scribed_metadata["integrated_description"].append(classification)
    #     _metadata = {
    #         "title": scribed_metadata["title"],
    #         "subject": "; ".join(scribed_metadata["integrated_description"])
    #     }
    #     if author := scribed_metadata.get("author"):
    #         _metadata["author"] = author
    #     if tags := scribed_metadata.get("tags"):
    #         _metadata["keywords"] = ", ".join(tags)
    #     acc.set_metadata(_metadata)

    #     # save the final pdf
    #     file_name = f"{scribed_metadata["title"].strip().rstrip('.').replace("/", "-")}"
    #     file_name = file_name if len(file_name) < 100 else f"{file_name[:97]}..."
    #     output_path = os.path.normpath(os.path.join(results_dir, f"{file_name}.pdf"))
    #     with open(output_path, "wb") as file:
    #         file.write(acc.write())

    #     return output_path


def _download_part_task(context, part, num, counter, total):
    if not (part_url := part.get("url")):
        print(f"Part {num} does not have an URL")
        context['access'] = "limited"
        return None
    res = num, part_url, download_part(context, part_url)
    context['progress'].main(f"Downloaded ({next(counter) + 1}/{total}) parts")
    return res


# def _decrypt_file_task(context, num, part_url, enc_unzip_dir, counter, total):
#     res = num, _decrypt_file(context, part_url, enc_unzip_dir)
#     context['progress'].main(f"Decrypted ({next(counter) + 1}/{total}) parts")
#     return res


def _prepare_toc(outline_meta, available_pages):
    """
    This function prepares the table of contents for the PDF document.
    """
    res = []
    for i in outline_meta:
        title = i['title'].strip().rstrip('.')
        page_no = 1 + int(i['dest'][0])
        res.append([1, title, page_no if page_no <= available_pages else -1])

    return res


# def _download_part(context, part):
#     work_dir = context["work_dir"]
#     part_name, _ = part.split(".")
#     enc_zip_path = os.path.join(work_dir, part_name + "_encrypted.zip")
#     enc_unzip_dir = os.path.join(work_dir, part_name + "_encrypted")

#     url = HOST + context["formatUrl"].format(url=part)
#     # download the encrypted zip file
#     with _request(method="GET", url=url, stream=True) as response:
#         os.makedirs(work_dir, exist_ok=True)
#         # save the encrypted zip file
#         with open(enc_zip_path, "wb") as enc_zip:
#             task = context["progress"].download(part)
#             total_size = 0
#             for chunk in response.iter_content(chunk_size=1024):
#                 enc_zip.write(chunk)
#                 chunk_len = len(chunk)
#                 total_size += chunk_len
#                 context['progress']._aux.update(task, advance=chunk_len)
#             context['progress']._aux.update(
#                 task, description=f"Downloaded {part}")
#             context['progress']._aux.stop_task(task)

#     # unzip the encrypted zip file
#     with zipfile.ZipFile(enc_zip_path, 'r') as enc_zip:
#         enc_zip.extractall(enc_unzip_dir)

#     return enc_unzip_dir


# def _decrypt_file(context, part, enc_unzip_dir):
#     work_dir = context["work_dir"]
#     part_name, ext = part.split(".")

#     enc_file_path = os.path.join(enc_unzip_dir, "enc.dat")
#     with open(enc_file_path, "rb") as file:
#         aes_key = AES.new(context["decryption_key"],
#                           AES.MODE_CBC, iv=context["decryption_key_iv"])
#         # read encrypted file by chunks 512 bytes at a time
#         decrypted_data = b""
#         total_size = os.path.getsize(enc_file_path)
#         task = context["progress"].decrypt(part, total_size)
#         while True:
#             chunk = file.read(512)
#             if not chunk:
#                 break
#             decrypted_data += aes_key.decrypt(chunk)
#             context['progress']._aux.update(task, advance=len(chunk))
#         context['progress']._aux.update(task, description=f"Decrypted {part}")
#         context['progress']._aux.stop_task(task)

#     # unpad the decrypted data
#     decrypted_data = unpad(decrypted_data, AES.block_size)
#     # save the decrypted file
#     dec_path = os.path.join(work_dir, part_name + "_decrypted." + ext)

#     with open(dec_path, "wb") as dec_zip:
#         dec_zip.write(decrypted_data)

#     # unzip the decrypted file
#     if ext == "zip":
#         dec_unzip_dir = os.path.join(work_dir, part_name + "_decrypted")
#         with zipfile.ZipFile(dec_path, 'r') as dec_zip:
#             dec_zip.extractall(dec_unzip_dir)
#         return dec_unzip_dir
#     else:
#         # if the decrypted file is not a zip file, just return the path to the file
#         return dec_path


# def _request(method, url, params=None, data=None, stream=False, attempts=10):
#     resp = requests.request(
#         method=method,
#         url=url,
#         params=params,
#         verify=False,
#         data=data,
#         stream=stream,
#         timeout=30,
#         headers={
#             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
#         }
#     )
#     resp.raise_for_status()
#     return resp


def _datetime_to_bytes(dt):
    res = int(dt.timestamp())
    res = res.to_bytes(8, byteorder='little', signed=False)
    return res


def _sign(priv_key, message, prefix):
    entropia = randbytes(16)
    anchor = datetime.now(pytz.UTC)
    since = _datetime_to_bytes(anchor - timedelta(hours=1))
    until = _datetime_to_bytes(anchor + timedelta(hours=1))

    message_to_sign = hashlib.sha256(
        message).digest() + entropia + since + until

    sig = priv_key.sign(
        data=bytes(message_to_sign),
        padding=padding.PKCS1v15(),
        algorithm=hashes.SHA256(),
    )
    return prefix + message_to_sign + sig
