from io import BytesIO
from google.cloud import storage
import os
from urllib.parse import urlparse, unquote
import base64
import io
from basics.utils import UUID
from datetime import datetime, timedelta
from chat.constants import GCP_CLIENT_DATA_BUCKET_NAME, GCP_PROJECT_ID_FOR_BUCKET
from backend.logger import Logger
import re 

workflow_logger = Logger(Logger.WORKFLOW_LOG)
error_logger = Logger(Logger.ERROR_LOG)

class GCPBucketService:

    def __init__(self, bucket_name=None):
        self.bucket_name = bucket_name or GCP_CLIENT_DATA_BUCKET_NAME
        project_id = GCP_PROJECT_ID_FOR_BUCKET
        self.client = storage.Client(project=project_id)
        self.bucket = self.client.bucket(self.bucket_name)

    def download_file(self, blob_name, destination_file_name):
        # Download blob to a local file
        blob = self.bucket.blob(blob_name)
        if not blob.exists():
            raise FileNotFoundError(f"Blob {blob_name} does not exist in bucket {self.bucket_name}.")

        blob.download_to_filename(destination_file_name)
        return f"Downloaded {blob_name} to {destination_file_name}."

    def upload_local_file(self, source_file_path, destination_blob_name):
        # Upload a file that exists locally to a bucket
        if not os.path.exists(source_file_path):
            raise FileNotFoundError(f"File {source_file_path} not found.")

        blob = self.bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_path)
        blob.make_public()
        return blob.public_url

    def upload_base64_file(self, company, base64_encoding, destination_blob_name=None):
        if destination_blob_name is None:
            destination_blob_name = self.get_blob_path(company=company)
        try:
            # Decode the base64 string into bytes
            match = re.match(r"data:(.*?);base64,", base64_encoding)
            content_type = match.group(1) if match else "application/octet-stream"
            base64_data = base64_encoding.split(",", 1)[-1]
            decoded_bytes = base64.b64decode(base64_data)
            file_stream = io.BytesIO(decoded_bytes)
            blob = self.bucket.blob(destination_blob_name)
            blob.upload_from_file(file_stream, content_type=content_type)  # Adjust content type if needed
            
            # blob.make_public()
            # print(blob.public_url)
            expiration_minutes = 30
            url = blob.generate_signed_url(
                    expiration=timedelta(minutes=expiration_minutes),
                    method="GET"
            )

            return url

        except Exception as e:
            # print(traceback.print_exc())
            raise Exception(f"Failed to upload file: {str(e)}")
    
    def get_blob_path(self, company, image_id=None, blob_type="image", blob_path="api", extension="jpg"):
        """
            Generate a blob storage path.

            :param company: Company object.
            :param image_id: Unique identifier for the image.
            :param blob_type: Type of blob (e.g., "image", "video")
            :param blob_path: path where the blob is stored after static path (e.g., api_route, whatsapp)
            :param extension: Extension of blob.
            :return: Formatted blob storage path. 
        """
        if image_id is None:
            image_id = UUID().get_uuid()

        now = datetime.now()
            
        full_blob_path = f'{blob_type}s/{company.prefix}_{company.id}/{now.year}/{now.month}/{now.day}/{blob_path}/{image_id}_{int(now.timestamp())}.{extension}'
        return full_blob_path

    def upload_file(self, file_obj, destination_blob_name):
        # Upload an image/file to a blob
        blob = self.bucket.blob(destination_blob_name)
        blob.upload_from_file(file_obj)
        blob.make_public()
        return blob.public_url

    def upload_bytes_to_blob(self, bytes_obj, destination_blob_name):
        # Upload a file in bytes format to a blob
        blob = self.bucket.blob(destination_blob_name)
        blob.upload_from_string(bytes_obj)

        # bucket level access is use, so blob cant be made public from code
        # blob.make_public()
        return blob.public_url

    def delete_blob(self, blob_name):
        # Delete a blob from the bucket
        blob = self.bucket.blob(blob_name)
        if blob.exists():
            blob.delete()
            return f"Blob {blob_name} deleted."
        else:
            raise FileNotFoundError(f"Blob {blob_name} does not exist in bucket {self.bucket_name}.")

    def blob_exists(self, blob_name):
        # Checks if a blob exists in the bucket
        blob = self.bucket.blob(blob_name)
        return blob.exists()

    def download_from_url(self, url):
        url = unquote(url)
        parsed_url = urlparse(url)
        blob_path = parsed_url.path.lstrip('/').replace(f"{self.bucket_name}/", '', 1)
        blob = self.bucket.blob(blob_path)

        image_data = blob.download_as_bytes()

        return BytesIO(image_data)

    def download_from_url_in_bytes(self, url):
        url = unquote(url)
        parsed_url = urlparse(url)
        blob_path = parsed_url.path.lstrip('/').replace(f"{self.bucket_name}/", '', 1)
        blob = self.bucket.blob(blob_path)

        image_data = blob.download_as_bytes()
        return image_data