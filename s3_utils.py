import boto3
import io
from urllib.parse import urlparse
import os
from dotenv import load_dotenv
import streamlit as st
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class S3Client:
    def __init__(self):
        """Initialize S3 client using credentials from .env"""
        self.aws_access_key, self.aws_secret_key = self.get_aws_credentials()
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key,
            region_name=os.getenv("AWS_REGION", "ap-southeast-1"),
        )

    def get_aws_credentials(self):
        """Get AWS credentials from .env file"""
        try:
            load_dotenv()
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

            if not aws_access_key or not aws_secret_key:
                raise Exception("AWS credentials not found in .env file")

            return aws_access_key, aws_secret_key

        except Exception as e:
            st.error(f"Error reading AWS credentials: {str(e)}")
            return None, None

    def download_file(self, s3_url):
        """Download file from S3 URL with authentication"""
        try:
            parsed_url = urlparse(s3_url)
            bucket_name = parsed_url.netloc
            key = parsed_url.path.lstrip("/")

            try:
                self.s3_client.head_object(Bucket=bucket_name, Key=key)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                if error_code == "403":
                    raise Exception(
                        "Access denied. Please check:\n"
                        "1. AWS credentials are correct\n"
                        "2. The IAM user has permission to access this S3 bucket\n"
                        "3. The bucket and file exist and are in the correct region"
                    )
                elif error_code == "404":
                    raise Exception(f"File not found: s3://{bucket_name}/{key}")
                else:
                    raise Exception(f"S3 error ({error_code}): {str(e)}")

            file_obj = io.BytesIO()
            self.s3_client.download_fileobj(bucket_name, key, file_obj)
            file_obj.seek(0)
            return file_obj

        except Exception as e:
            raise Exception(f"Error downloading from S3: {str(e)}")

    def upload_file(self, content, s3_url):
        """Upload content to S3"""
        try:
            if not s3_url.startswith("s3://"):
                raise ValueError("S3 URL must start with 's3://'")

            path_parts = s3_url[5:].split("/", 1)
            if len(path_parts) != 2:
                raise ValueError("Invalid S3 URL format")

            bucket = path_parts[0]
            key = path_parts[1]

            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            else:
                content_bytes = content

            self.s3_client.put_object(Bucket=bucket, Key=key, Body=content_bytes)

            return s3_url

        except Exception as e:
            raise Exception(f"Failed to upload to S3: {str(e)}")

    def list_files(self, s3_path):
        """List files in specified S3 path"""
        try:
            bucket_name = s3_path.split("/")[2]
            prefix = "/".join(s3_path.split("/")[3:])

            response = self.s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

            if "Contents" not in response:
                logger.warning(f"No files found in {s3_path}")
                return []

            files = [
                os.path.basename(obj["Key"])
                for obj in response["Contents"]
                if obj["Key"].endswith(".xlsx")
            ]
            return files

        except Exception as e:
            logger.error(f"Error listing files from S3: {str(e)}")
            raise

    def list_folders(self, s3_path):
        """List folders in specified S3 path"""
        try:
            if not s3_path.startswith("s3://"):
                raise ValueError("S3 URL must start with 's3://'")

            bucket_name = s3_path.split("/")[2]
            prefix = "/".join(s3_path.split("/")[3:])

            if prefix and not prefix.endswith("/"):
                prefix += "/"

            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name, Prefix=prefix, Delimiter="/"
            )

            folders = [
                obj["Prefix"].rstrip("/").split("/")[-1]
                for obj in response.get("CommonPrefixes", [])
            ]
            return folders

        except Exception as e:
            logger.error(f"Error listing folders from S3: {str(e)}")
            raise

    def download_folder(self, models_url, model_name, local_path):
        """Download an entire folder from S3 URL to a local path with authentication"""
        try:
            if not models_url.endswith("/"):
                models_url += "/"
            if model_name.startswith("/"):
                model_name = model_name[1:]

            s3_url = models_url + model_name
            local_path = os.path.abspath(os.path.join(os.getcwd(), local_path))
            parsed_url = urlparse(s3_url)
            bucket_name = parsed_url.netloc
            prefix = parsed_url.path.lstrip("/")

            if not os.path.exists(local_path):
                os.makedirs(local_path)

            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
            for page in pages:
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    relative_path = os.path.relpath(key, prefix)
                    local_file_path = os.path.join(local_path, relative_path)
                    local_file_dir = os.path.dirname(local_file_path)

                    if not os.path.exists(local_file_dir):
                        os.makedirs(local_file_dir)

                    with open(local_file_path, "wb") as f:
                        self.s3_client.download_fileobj(bucket_name, key, f)

        except Exception as e:
            raise Exception(f"Error downloading folder from S3: {str(e)}")
