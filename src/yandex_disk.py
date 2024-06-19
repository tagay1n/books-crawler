import os

import yadisk


def upload_to_yandex(path_to_file, config, path_to_remote_folder):
    # obtain oauth token
    y = yadisk.YaDisk(token=config['yandex']['oauth_token'])

    # create a folder if it does not exist
    path_collector = ''
    for path_segment in path_to_remote_folder.split(os.sep):
        path_collector += path_segment + os.sep
        if not y.exists(path_collector):
            y.mkdir(path_collector)

    file_name = os.path.basename(path_to_file).split('/')[-1]
    remote_path = f"{path_to_remote_folder}/{file_name}"

    # upload the file
    y.upload(path_to_file, remote_path, overwrite=True)
    return remote_path


def create_public_link(remote_path: str, config):
    # obtain oauth token
    y = yadisk.YaDisk(token=config['yandex']['oauth_token'])

    y.publish(remote_path)
    # get the public download link
    pub_key = y.get_meta(remote_path)['public_key']
    return y.get_public_download_link(pub_key)
