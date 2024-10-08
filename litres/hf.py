from utils import get_in_workdir


def upload_to_hf():
    print("Uploading to huggingface")
    from huggingface_hub import HfApi
    api = HfApi()
    api.upload_folder(
        folder_path=get_in_workdir("__artifacts/litres/markdown"),
        repo_id="neurotatarlar/tt-litres-books",
        repo_type="dataset",
    )
    print("Done")
