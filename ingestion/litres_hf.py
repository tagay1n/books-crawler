"""Uploads prepared Litres markdown and images to a Hugging Face dataset."""
from .runtime_config import option as operational_option

from .litres_utils import get_in_workdir

MARKDOWN_DIR = "markdown"


def upload_to_hf():
    print("Uploading to huggingface")
    from huggingface_hub import HfApi
    api = HfApi()
    api.upload_folder(
        folder_path=get_in_workdir(MARKDOWN_DIR),
        repo_id=operational_option('litres_hf', 'hf_dataset'),
        repo_type="dataset",
    )
    print("Done")
