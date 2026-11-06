"""Validated Litres PDF and browser settings."""
from .runtime_config import option as operational_option
from .litres_utils import read_config


def _get_pdf_compression_options():
    pdf_config = _get_pdf_config()
    options = {
        "jpeg_quality": int(_required_config_value(pdf_config, "pdf.jpeg_quality")),
        "max_width": _required_config_value(pdf_config, "pdf.max_width", allow_none=True),
        "dpi": int(_required_config_value(pdf_config, "pdf.dpi")),
        "lossless_first_pages": int(_required_config_value(pdf_config, "pdf.lossless_first_pages")),
    }
    if options["max_width"] is not None:
        options["max_width"] = int(options["max_width"])

    if not 1 <= options["jpeg_quality"] <= 100:
        raise ValueError("pdf.jpeg_quality must be between 1 and 100")
    if options["max_width"] is not None and options["max_width"] <= 0:
        raise ValueError("pdf.max_width must be positive or null")
    if options["dpi"] <= 0:
        raise ValueError("pdf.dpi must be positive")
    if options["lossless_first_pages"] < 0:
        raise ValueError("pdf.lossless_first_pages must be zero or positive")
    return options


def _get_pdf_browser_headless():
    pdf_config = _get_pdf_config()
    return _config_bool(
        _required_config_value(pdf_config, "pdf.browser_headless"),
        "pdf.browser_headless",
    )


def _get_pdf_browser_challenge_wait_seconds():
    pdf_config = _get_pdf_config()
    value = int(_required_config_value(pdf_config, "pdf.browser_challenge_wait_seconds"))
    if value <= 0:
        raise ValueError("pdf.browser_challenge_wait_seconds must be positive")
    return value


def _get_pdf_config():
    config = read_config()
    if not isinstance(config, dict):
        raise ValueError("sources.litres in the selected operational YAML is empty or invalid")
    pdf_config = config.get("pdf")
    if not isinstance(pdf_config, dict):
        raise ValueError("pdf is not set in sources.litres in the selected operational YAML")
    return pdf_config


def _required_config_value(config, name, allow_none=False):
    key = name.rsplit(".", 1)[-1]
    if key not in config:
        raise ValueError(f"{name} is not set in sources.litres in the selected operational YAML")
    value = config.get(key)
    if value is None and allow_none:
        return value
    if value is None or value == "":
        raise ValueError(f"{name} is not set in sources.litres in the selected operational YAML")
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
