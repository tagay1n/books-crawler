import yadisk

import books_downloader
from utils import create_files_if_not_exists, get_real_path


def main():
    # prepare files and dirs
    (
        visited_non_book_pages_sink,
        visited_book_pages_sink,
        book_pages_sink,
        book_metas,
        downloaded_files,
        downloads_folder
    ) = create_files_if_not_exists()
    configs = read_config()

    # phase 1: collect list of the links of book's pages and store them in the file
    # book_pages_collector.collect(book_pages_sink, visited_non_book_pages_sink, DOMAIN, BOOKS_PAGE_MASK, SKIP_FILTERS)

    # phase 2: visit the book's pages and collect the meta information about the books
    # book_pages_visitor.visit()

    # phase 3: download the books using the collected meta information, then upload them to Yandex.Disk and upload meta
    # information to the Google Sheets
    books_downloader.download(downloaded_files, configs)


def read_config():
    import yaml
    with open(get_real_path("../../config.yaml")) as f:
        data_map = yaml.safe_load(f)

    if oauth := data_map['yandex-oauth']:
        y = yadisk.YaDisk(token=oauth)
        if not y.check_token():
            raise Exception("Invalid Yandex Disk OAuth token")

    return data_map


if __name__ == '__main__':
    main()
