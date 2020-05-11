import os

from azure.storage.blob import BlockBlobService


class AzureBlob:
    def __init__(self, account_name, account_key, container_name):
        self.account_name = account_name
        self.account_key = account_key
        self.container_name = container_name
        self.blob_obj = BlockBlobService(account_name=account_name, account_key=account_key)

    def upload_file_to_blob(self, local_path, file_name):
        print("Uploading Local Data File [{file}] to BLOB".format(file=file_name))
        self.blob_obj.create_blob_from_path(container_name=self.container_name, blob_name=file_name,
                                            file_path=os.path.join(local_path, file_name))

    def download_files_from_blob(self, local_path, file_name):
        print("Downloading Data File: [{file}] from BLOB".format(file=file_name))
        self.blob_obj.get_blob_to_path(container_name=self.container_name, blob_name=file_name,
                                       file_path=os.path.join(local_path, file_name))
