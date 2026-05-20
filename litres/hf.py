"""Uploads prepared Litres markdown and images to a Hugging Face dataset."""

from utils import get_in_workdir

MARKDOWN_DIR = "../__artifacts/litres/markdown"
HF_DATASET = "yasalma/tt-litres-books"


def upload_to_hf():
    print("Uploading to huggingface")
    from huggingface_hub import HfApi
    api = HfApi()
    api.upload_folder(
        folder_path=get_in_workdir(MARKDOWN_DIR),
        repo_id=HF_DATASET,
        repo_type="dataset",
    )
    print("Done")
