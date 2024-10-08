import json

from utils import get_in_workdir


def upload_pdfs():
    _index_file = get_in_workdir("../__artifacts/litres/books-index.json")
    with open(_index_file, "r") as f:
        _all_docs = json.load(f)

    for doc in [d for d in _all_docs.values() if d['content_type'] == 'pdf'][:1]:
        print(f"Uploading book: {doc['full_name']}")
        # upload_book(doc)
        # create_public_link(doc)
        # save_to_google_sheets(doc)
