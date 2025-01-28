import boto3
import io
from urllib.parse import urlparse
import os
from dotenv import load_dotenv
import streamlit as st
from botocore.exceptions import ClientError
import tempfile
import pandas as pd
import logging

logger = logging.getLogger(__name__)

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

def download_and_validate_excel_files(s3_path):
    """
    Download and validate all Excel files from specified S3 path
    
    Args:
        s3_path (str): S3 path in format 's3://bucket-name/prefix/'
    
    Returns:
        list: List of validated DataFrame objects from Excel files
    """
    try:
        # Parse bucket and prefix from s3_path
        bucket_name = s3_path.split('/')[2]
        prefix = '/'.join(s3_path.split('/')[3:])
        
        # Initialize S3 client
        s3_client = boto3.client('s3')
        
        # List all objects in the specified path
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix
        )
        
        if 'Contents' not in response:
            raise ValueError(f"No files found in {s3_path}")
            
        excel_files = []
        validated_dfs = []
        
        # Filter for .xlsx files
        for obj in response['Contents']:
            if obj['Key'].endswith('.xlsx'):
                excel_files.append(obj['Key'])
        
        if not excel_files:
            raise ValueError(f"No Excel files found in {s3_path}")
            
        # Download and validate each Excel file
        for file_key in excel_files:
            # Create a temporary file to store the downloaded Excel
            with tempfile.NamedTemporaryFile(suffix='.xlsx') as temp_file:
                s3_client.download_file(bucket_name, file_key, temp_file.name)
                
                # Read Excel file
                try:
                    df = pd.read_excel(temp_file.name)
                    
                    # Validate Excel structure
                    required_columns = ['PolicyID', 'Age', 'Gender', 'Term']  # Add your required columns
                    missing_columns = [col for col in required_columns if col not in df.columns]
                    
                    if missing_columns:
                        logger.warning(f"File {file_key} missing required columns: {missing_columns}")
                        continue
                    
                    # Additional validation checks can be added here
                    # For example, check data types, value ranges, etc.
                    
                    validated_dfs.append(df)
                    logger.info(f"Successfully validated file: {file_key}")
                    
                except Exception as e:
                    logger.error(f"Error processing file {file_key}: {str(e)}")
                    continue
        
        if not validated_dfs:
            raise ValueError("No valid Excel files found after validation")
            
        return validated_dfs
        
    except Exception as e:
        logger.error(f"Error in download_and_validate_excel_files: {str(e)}")
        raise 