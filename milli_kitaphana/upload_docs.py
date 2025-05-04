import os.path
from boto3 import Session


from yadisk_client import YaDisk, ConflictResolution


def upload_doc(path_to_pdf, config, is_limited):
    remote_dir = os.path.join(config['yandex']['disk']['target_dir'], "limited" if is_limited else "full")
    client = YaDisk(config['yandex']['disk']['oauth_token'])

    remote_path, _ = client.upload_or_replace(
        path_to_pdf, 
        remote_dir=remote_dir,
        conflict_resolution=ConflictResolution.SKIP
    )
    res = client.publish(remote_path)
    res = client.get_meta(res.path, fields=['md5'])
    return res.md5
    
def upload_metadata(path_to_metadata, path_to_pdf, context):
    config = context['config']
    client = Session().client(
        service_name='s3',
        aws_access_key_id=config['yandex']['cloud']['aws_access_key_id'],
        aws_secret_access_key=config['yandex']['cloud']['aws_secret_access_key'],
        endpoint_url='https://storage.yandexcloud.net'
    )
    meta_key = f"{context['md5']}.zip"
    meta_bucket = config["yandex"]["cloud"]['bucket']['upstream_metadata']
    client.upload_file(
        path_to_metadata,
        meta_bucket,
        meta_key
    )
    doc_key = f"{context['md5']}.pdf"
    doc_bucket = config["yandex"]["cloud"]['bucket']['document']
    if not client.list_objects_v2(Bucket=doc_bucket, Prefix=doc_key, MaxKeys=1).get("Contents", []):
        client.upload_file(
            path_to_pdf,
            doc_bucket,
            doc_key
        )
