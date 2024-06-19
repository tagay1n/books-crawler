import os

import yadisk


def upload_to_yandex(path_to_file: str, config, path_to_remote_folder: str):
    # obtain oauth token
    y = yadisk.YaDisk(token=config['yandex-oauth'])

    # create a folder if it does not exist
    if not y.exists(path_to_remote_folder):
        y.mkdir(path_to_remote_folder)

    file_name = os.path.basename(path_to_file).split('/')[-1]
    remote_path = f"{path_to_remote_folder}/{file_name}"

    # upload the file
    y.upload(path_to_file, remote_path, overwrite=True)
    # make the file public
    y.publish(remote_path)
    # get the public download link
    pub_key = y.get_meta(remote_path)['public_key']
    return y.get_public_download_link(pub_key)
