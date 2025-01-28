import boto3
import io
from urllib.parse import urlparse
import os
from dotenv import load_dotenv
import streamlit as st
from botocore.exceptions import ClientError

def get_aws_credentials():
    """
    Get AWS credentials from .env file
    Returns tuple of (access_key, secret_key)
    """
    try:
        load_dotenv()
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        
        if not aws_access_key or not aws_secret_key:
            raise Exception("AWS credentials not found in .env file")
            
        return aws_access_key, aws_secret_key
        
    except Exception as e:
        st.error(f"Error reading AWS credentials: {str(e)}")
        return None, None

def download_from_s3(s3_url):
    """
    Download file from S3 URL with authentication
    """
    try:
        aws_access_key, aws_secret_key = get_aws_credentials()
        if not aws_access_key or not aws_secret_key:
            raise Exception("AWS credentials not found in .env file")
        
        parsed_url = urlparse(s3_url)
        bucket_name = parsed_url.netloc
        key = parsed_url.path.lstrip('/')
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=os.getenv('AWS_REGION', 'ap-southeast-1')
        )
        
        try:
            s3_client.head_object(Bucket=bucket_name, Key=key)
            print("bucket_name", bucket_name)
            print("key", key)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == '403':
                raise Exception(
                    "Access denied. Please check:\n"
                    "1. AWS credentials are correct\n"
                    "2. The IAM user has permission to access this S3 bucket\n"
                    "3. The bucket and file exist and are in the correct region"
                )
            elif error_code == '404':
                raise Exception(f"File not found: s3://{bucket_name}/{key}")
            else:
                raise Exception(f"S3 error ({error_code}): {str(e)}")
        
        file_obj = io.BytesIO()
        s3_client.download_fileobj(bucket_name, key, file_obj)
        file_obj.seek(0)
        
        return file_obj
        
    except Exception as e:
        raise Exception(f"Error downloading from S3: {str(e)}") 