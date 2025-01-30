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

def get_s3_client():
    """
    Get an authenticated S3 client using credentials from .env
    
    Returns:
        boto3.client: Authenticated S3 client
    """
    aws_access_key, aws_secret_key = get_aws_credentials()
    if not aws_access_key or not aws_secret_key:
        raise Exception("AWS credentials not found in .env file")
    
    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=os.getenv('AWS_REGION', 'ap-southeast-1')
    )
    
    return s3_client 

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

def download_excel_files_from_s3(s3_path):
    """
    Download all Excel files from specified S3 path
    
    Args:
        s3_path (str): S3 path in format 's3://bucket-name/prefix/'
    
    Returns:
        list: List of tuples containing (file_key, temp_file_path) for each Excel file
    """
    try:
        bucket_name = s3_path.split('/')[2]
        prefix = '/'.join(s3_path.split('/')[3:])
        
        s3_client = boto3.client('s3')
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix
        )
        
        if 'Contents' not in response:
            raise ValueError(f"No files found in {s3_path}")
            
        excel_files = []
        downloaded_files = []
        
        # Filter for .xlsx files
        for obj in response['Contents']:
            if obj['Key'].endswith('.xlsx'):
                excel_files.append(obj['Key'])
        
        if not excel_files:
            raise ValueError(f"No Excel files found in {s3_path}")
            
        # Download each Excel file
        for file_key in excel_files:
            temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
            s3_client.download_file(bucket_name, file_key, temp_file.name)
            downloaded_files.append((file_key, temp_file.name))
            
        return downloaded_files
        
    except Exception as e:
        logger.error(f"Error in download_excel_files_from_s3: {str(e)}")
        raise

def get_standardized_column_name(columns, possible_names):
    """
    Find a matching column name from a list of possible variations
    
    Args:
        columns (list): List of actual column names in the DataFrame
        possible_names (list): List of possible variations of the column name
    
    Returns:
        str: Matching column name if found, None otherwise
    """
    # Convert all names to lowercase for case-insensitive comparison
    columns_lower = [col.lower().replace(' ', '_') for col in columns]
    for col, original_col in zip(columns_lower, columns):
        for possible_name in possible_names:
            if possible_name.lower() in col:
                return original_col
    return None

def validate_excel_files(file_paths):
    """
    Validate downloaded Excel files with flexible column name matching
    
    Args:
        file_paths (list): List of tuples containing (file_key, temp_file_path)
    
    Returns:
        list: List of validated DataFrame objects from Excel files
    """
    try:
        validated_dfs = []
        
        # Define column name variations
        required_column_variations = {
            'Policy number': [
                'policy', 'policyid', 'policy_id', 'policy_number', 
                'policy_no', 'policy_num', 'p_number', 'p_id', 'id'
            ],
            'age_at_entry': [
                'age', 'member_age', 'client_age', 'age_at_entry'
            ],
            'sex': [
                'gender', 'sex', 'member_gender', 'client_gender'
            ],
            'policy_term': [
                'term', 'policy_term', 'coverage_term', 'duration'
            ]
        }
        
        for file_key, temp_file_path in file_paths:
            try:
                df = pd.read_excel(temp_file_path)
                
                # Add filename as attribute to DataFrame
                filename = file_key.split('/')[-1]  # Get just the filename
                df.filename = filename
                
                # Dictionary to store matched column names
                column_mapping = {}
                missing_columns = []
                
                # Check for each required column
                for std_name, variations in required_column_variations.items():
                    matched_col = get_standardized_column_name(df.columns, variations)
                    if matched_col:
                        column_mapping[std_name] = matched_col
                    else:
                        missing_columns.append(std_name)
                
                if missing_columns:
                    logger.warning(
                        f"File {file_key} missing required columns: {missing_columns}\n"
                        f"Available columns: {list(df.columns)}"
                    )
                    continue
                
                # Rename columns to standardized names
                df_standardized = df.rename(columns={v: k for k, v in column_mapping.items()})
                
                # Additional validation checks can be added here
                
                validated_dfs.append(df_standardized)
                logger.info(f"Successfully validated file: {filename}")
                logger.info(f"Column mapping used: {column_mapping}")
                
            except Exception as e:
                logger.error(f"Error processing file {file_key}: {str(e)}")
                continue
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Error deleting temporary file {temp_file_path}: {str(e)}")
        
        if not validated_dfs:
            raise ValueError("No valid Excel files found after validation")
            
        return validated_dfs
        
    except Exception as e:
        logger.error(f"Error in validate_excel_files: {str(e)}")
        raise


def download_and_validate_excel_files(s3_path):
    """
    Download and validate all Excel files from specified S3 path
    
    Args:
        s3_path (str): S3 path in format 's3://bucket-name/prefix/'
    
    Returns:
        list: List of validated DataFrame objects from Excel files
    """
    downloaded_files = download_excel_files_from_s3(s3_path)
    return validate_excel_files(downloaded_files)

def upload_to_s3(content, s3_url):
    """
    Upload content to S3
    
    Args:
        content (Union[str, bytes]): The content to upload (string or bytes)
        s3_url (str): The S3 URL in format s3://bucket-name/path/to/file
        
    Returns:
        str: The S3 URL where the content was uploaded
    """
    try:
        # Parse bucket and key from s3_url
        if not s3_url.startswith('s3://'):
            raise ValueError("S3 URL must start with 's3://'")
        
        path_parts = s3_url[5:].split('/', 1)
        if len(path_parts) != 2:
            raise ValueError("Invalid S3 URL format")
        
        bucket = path_parts[0]
        key = path_parts[1]
        
        # Convert content to bytes if it's a string
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content
        
        # Upload to S3
        s3_client = get_s3_client()
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content_bytes
        )
        
        return s3_url
        
    except Exception as e:
        raise Exception(f"Failed to upload to S3: {str(e)}")

def get_excel_filenames_from_s3(s3_path):
    """
    Get list of Excel file names from specified S3 path
    
    Args:
        s3_path (str): S3 path in format 's3://bucket-name/prefix/'
    
    Returns:
        list: List of Excel file names (without path)
    """
    try:
        # Parse bucket and prefix from s3_path
        bucket_name = s3_path.split('/')[2]
        prefix = '/'.join(s3_path.split('/')[3:])
        
        # Get S3 client
        s3_client = get_s3_client()
        
        # List objects in the specified path
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix
        )
        
        if 'Contents' not in response:
            logger.warning(f"No files found in {s3_path}")
            return []
            
        # Filter for .xlsx files and extract just the filename
        excel_files = []
        for obj in response['Contents']:
            if obj['Key'].endswith('.xlsx'):
                # Get just the filename without the path
                filename = obj['Key'].split('/')[-1]
                # Remove the .xlsx extension
                filename = filename.replace('.xlsx', '')
                excel_files.append(filename)
        
        return sorted(excel_files)  # Return sorted list of filenames
        
    except Exception as e:
        logger.error(f"Error getting Excel filenames from S3: {str(e)}")
        raise

def get_foldernames_from_s3(s3_path):
    """
    Get list of folder names from specified S3 path
    
    Args:
        s3_path (str): S3 path in format 's3://bucket-name/prefix/'
    
    Returns:
        list: List of folder names
    """
    try:
        # Parse bucket and prefix from s3_path
        if not s3_path.startswith('s3://'):
            raise ValueError("S3 URL must start with 's3://'")
            
        bucket_name = s3_path.split('/')[2]
        prefix = '/'.join(s3_path.split('/')[3:])
        
        # Ensure prefix ends with '/'
        if prefix and not prefix.endswith('/'):
            prefix += '/'
        
        # Get S3 client
        s3_client = get_s3_client()
        
        # List objects with delimiter to get folders
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix,
            Delimiter='/'
        )
        
        folders = []
        
        # Get common prefixes (folders)
        if 'CommonPrefixes' in response:
            for obj in response['CommonPrefixes']:
                # Get the folder name without the full path and trailing slash
                folder_path = obj['Prefix']
                folder_name = folder_path.rstrip('/').split('/')[-1]
                folders.append(folder_name)
                
        return sorted(folders)  # Return sorted list of folder names
        
    except Exception as e:
        logger.error(f"Error getting folders from S3: {str(e)}")
        raise 


def download_folder_from_s3(models_url, model_name, local_path):
    """
    Download an entire folder from S3 URL to a local path with authentication
    Parameters:
        s3_url (str): S3 URL of the folder to download
        local_path (str): Relative or absolute path where files should be downloaded
    """
    try:
        if not models_url.endswith('/'):
            models_url += '/'
        if model_name.startswith('/'):
            model_name = model_name[1:]

        s3_url = models_url + model_name
        # Convert relative path to absolute path relative to current working directory
        local_path = os.path.abspath(os.path.join(os.getcwd(), local_path))
        
        parsed_url = urlparse(s3_url)
        bucket_name = parsed_url.netloc
        prefix = parsed_url.path.lstrip('/')

        # Create base directory if it doesn't exist
        if not os.path.exists(local_path):
            os.makedirs(local_path)

        s3_client = get_s3_client()
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']
                
                # Get the path relative to the prefix
                relative_path = os.path.relpath(key, prefix)
                
                # Join with local path to get the final destination
                local_file_path = os.path.join(local_path, relative_path)
                local_file_dir = os.path.dirname(local_file_path)
                
                # Debug print to see exactly where we're trying to create directories
                print(f"Creating directory: {local_file_dir}")
                
                if not os.path.exists(local_file_dir):
                    os.makedirs(local_file_dir)
                
                print(f"Downloading {key} to {local_file_path}")
                with open(local_file_path, 'wb') as f:
                    s3_client.download_fileobj(bucket_name, key, f)

    except Exception as e:
        raise Exception(f"Error downloading folder from S3: {str(e)}")