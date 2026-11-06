"""Local Litres page validation, image encoding and atomic PDF assembly."""
from .runtime_config import option as operational_option
import io
import os
import glob
import hashlib
import pymupdf
from PIL import Image, UnidentifiedImageError
from rich.progress import track
from .litres_utils import RUNTIME, get_in_workdir
from .litres_browser import (
    _format_pdf_page_response_error,
)
from .litres_pdf_config import _get_pdf_compression_options


def _save_pdf_page_image(image_content, response, result_file, url):
    tmp_file = _temporary_path(result_file)
    try:
        img = Image.open(io.BytesIO(image_content))
    except UnidentifiedImageError as exc:
        raise ValueError(_format_pdf_page_response_error(response, url)) from exc
    try:
        with img:
            img.save(tmp_file, format="PNG", dpi=(operational_option('litres_pdf_config', 'raw_page_dpi'), operational_option('litres_pdf_config', 'raw_page_dpi')), optimize=True)
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
    artifacts_dir = get_in_workdir(f"images/{file_id}")
    pdf_dir = get_in_workdir("docs")
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
            for page_number, page in enumerate(track(images, description=f"Creating pdf for file: {file_id}")):
                if RUNTIME.get():
                    RUNTIME.get().budget.check()
                image_bytes, image_filetype = _page_image_bytes_for_pdf(
                    os.path.join(artifacts_dir, page),
                    page_number,
                    options,
                )
                with pymupdf.open(stream=image_bytes, filetype=image_filetype) as img:
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


def _page_image_bytes_for_pdf(image_path, page_number, options):
    if page_number < options["lossless_first_pages"]:
        return _lossless_page_png_bytes(image_path, options), "png"
    return _compressed_page_jpeg_bytes(image_path, options), "jpeg"


def _lossless_page_png_bytes(image_path, options):
    with Image.open(image_path) as source:
        source.load()
        image = source.copy()

    output = io.BytesIO()
    image.save(
        output,
        format="PNG",
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
