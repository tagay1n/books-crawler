from multiprocessing.pool import ThreadPool
import itertools
from Crypto.Cipher import AES
import os
from Crypto.Util.Padding import unpad
import zipfile
import pymupdf
from utils import read_config, load_index_file, dump_index, download_part, base_dir
from progress_wrapper import ProgressWrapper
import json
import base64
import copy
import shutil
from upload_docs import upload_doc, upload_metadata
import hashlib

def decrypt():
    index = load_index_file()
    if not (not_decrypted_docs := _get_not_decrypted_docs(index)):
        print("No docs for decrypting, exiting...")
        return
    print(f"About to decrypt {len(not_decrypted_docs)} document(s)")
    config = read_config()
    
    for card_path, meta in not_decrypted_docs:
        try:
            context = {
                "meta": meta,
                "config": config
            }
            with ProgressWrapper(context, card_path) as pw:
                code = context["meta"]["download_code"]
                # path to the directory where the artifacts of the key exchange will be stored
                
                work_dir = os.path.join(base_dir, code)
                context["work_dir"] = work_dir
                path_to_pdf = decrypt_doc_parts(context)
                del context['meta']['enc_part_paths']
                del context['meta']['format_url']
                del context['meta']['decryption_key']
                del context['meta']['decryption_key_iv']
                upstream_metadata = copy.deepcopy(context["meta"])
                del upstream_metadata['downloaded']
                del upstream_metadata['decrypted']

                # save metadata
                path_to_metadata = os.path.join(context['work_dir'], "metadata.zip")
                with zipfile.ZipFile(path_to_metadata, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                    meta_json = json.dumps(upstream_metadata, indent=None, separators=(',', ':'), ensure_ascii=False)
                    zf.writestr("metadata.json", meta_json)

                pw.main(f"Uploading artifacts to yandex disk --> {context['meta']['title']}")
                context['md5'] = _calculate_md5(path_to_pdf)
                upload_doc(
                    path_to_pdf=path_to_pdf,
                    config=config,
                    is_limited=meta["access"] == "limited"
                )
                
                # upload metadata to s3
                pw.main(f"Uploading artifacts to object storage --> {context['md5']}")
                upload_metadata(path_to_metadata=path_to_metadata, path_to_pdf=path_to_pdf, context=context)
                
                pw.main(f"[bold green]Decryption complete '{context['md5']}' '{context['meta']['title']}'[/bold green]")
                # shutil.rmtree(context['work_dir'])
                context['meta']['decrypted'] = True
        except KeyboardInterrupt:
            return
        except BaseException as e:
            import traceback
            print(f"Error: {e} {traceback.format_exc()}")
        finally:
            dump_index(idx=index)
            
            
def _get_not_decrypted_docs(index):
    not_decrypted_docs = []
    for card_path, meta in index.items():
        if not meta.get('decrypted', False) and meta.get('enc_part_paths'):
            not_decrypted_docs.append((card_path, meta))
        
    return not_decrypted_docs
            

def decrypt_doc_parts(context):
    enc_part_paths = context['meta']['enc_part_paths']
    parts_count = len(enc_part_paths)
    with ThreadPool(processes=4) as pool:
        # decrypt the parts
        counter = itertools.count()
        context['progress'].main(f"Decrypted (0/{parts_count}) parts")
        dec_part_paths = pool.map(lambda en: _decrypt_file_task(
            context, en[0], en[1], en[2], counter, parts_count), [(i['num'], i['part_url'], i['enc_unzip_dir']) for i in enc_part_paths if i]
        )
        
     # accumulate all parts into one pdf doc
    context["progress"].main("Merging document parts...")
    # decrypt the metadata
    meta_url = "part0.zip"
    enc_zip_dir = download_part(context, meta_url)
    meta_dir = _decrypt_file(context, meta_url, enc_zip_dir)

    with open(os.path.join(meta_dir, "source.json"), "r", encoding="utf-8") as file:
        source_meta = json.load(file)

    parts = source_meta["parts"]
    with pymupdf.open() as acc:
        for num, path in dec_part_paths:
            # open the encrypted pdf part
            with pymupdf.open(path) as pdf_doc:
                password = f"rbooks2-{source_meta['fingerprint'].split('-')[-1]}-{num+1}"
                pdf_doc.authenticate(password)
                # add the pages to the accumulator
                acc.insert_pdf(pdf_doc)

        acc.set_pagemode(source_meta["pageMode"])
        acc.set_pagelayout(source_meta["pageLayout"])
        toc = _get_toc(context, meta_dir, parts)
        acc.set_toc(toc)
        scribed_metadata = context["meta"]
        if classification := scribed_metadata.get("classification"):
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
        file_name = f"{scribed_metadata['title'].strip().rstrip('.').replace('/', '-')}"
        file_name = file_name if len(file_name) < 100 else f"{file_name[:97]}..."
        output_path = os.path.normpath(os.path.join(context["work_dir"], f"{file_name}.pdf"))
        with open(output_path, "wb") as file:
            file.write(acc.write())

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
        # read encrypted file by chunks 512 bytes at a time
        decrypted_data = b""
        total_size = os.path.getsize(enc_file_path)
        task = context["progress"].decrypt(part, total_size)
        while True:
            chunk = file.read(512)
            if not chunk:
                break
            decrypted_data += aes_key.decrypt(chunk)
            context['progress']._aux.update(task, advance=len(chunk))
        context['progress']._aux.update(task, description=f"Decrypted {part}")
        context['progress']._aux.stop_task(task)

    # unpad the decrypted data
    decrypted_data = unpad(decrypted_data, AES.block_size)
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