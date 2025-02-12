import pytest
import pandas as pd
import boto3
from moto import mock_aws
import io
from s3_utils import download_and_validate_excel_files
from botocore.exceptions import NoCredentialsError
from unittest.mock import patch, MagicMock
import logging

@pytest.fixture
def mock_s3_bucket():
    """Fixture to create a mock S3 bucket with test files"""
    with mock_aws():
        # Create mock S3 client
        s3_client = boto3.client(
            's3',
            region_name='ap-southeast-1'
        )
        
        # Create test bucket
        bucket_name = 'valuation-model'
        s3_client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': 'ap-southeast-1'}
        )
        
        # Create valid Excel file
        valid_df = pd.DataFrame({
            'policy': ['P001', 'P002'],  # Changed to match flexible column names
            'age': [30, 40],
            'gender': ['M', 'F'],
            'term': [10, 20]
        })
        
        # Create invalid Excel file (missing columns)
        invalid_df = pd.DataFrame({
            'policy': ['P001'],
            'age': [30]
            # Missing gender and term columns
        })
        
        # Save DataFrames to bytes buffer
        valid_buffer = io.BytesIO()
        invalid_buffer = io.BytesIO()
        valid_df.to_excel(valid_buffer, index=False)
        invalid_df.to_excel(invalid_buffer, index=False)
        
        # Upload test files to mock S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key='term/run1/model-point/valid_file.xlsx',
            Body=valid_buffer.getvalue()
        )
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key='term/run1/model-point/invalid_file.xlsx',
            Body=invalid_buffer.getvalue()
        )
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key='term/run1/model-point/not_excel.txt',
            Body=b'This is not an excel file'
        )
        
        yield bucket_name


# def test_valid_excel_files(mock_s3_bucket):
#     """Test downloading and validating Excel files with valid data"""
#     s3_path = f's3://{mock_s3_bucket}/term/run1/model-point/'
#     dfs = download_and_validate_excel_files(s3_path)
    
#     # We expect only the valid file to be in results
#     assert len(dfs) == 1
#     df = dfs['valid_file']  # Access by filename without extension
#     assert isinstance(df, pd.DataFrame)
#     # Check original column names since we're not transforming them
#     assert all(col in df.columns for col in ['policy', 'age', 'gender', 'term'])
#     assert len(df) == 2  # Two rows in valid file


def test_no_excel_files(mock_s3_bucket):
    """Test with path containing no Excel files"""
    s3_path = f's3://{mock_s3_bucket}/empty/folder/'
    
    with pytest.raises(ValueError, match="No files found"):
        download_and_validate_excel_files(s3_path)

def test_invalid_s3_path():
    """Test with invalid S3 path"""
    with pytest.raises(Exception):
        download_and_validate_excel_files('invalid_path')


# def test_missing_required_columns(mock_s3_bucket, caplog):
#     """Test handling of Excel files with missing required columns"""
#     caplog.set_level(logging.WARNING)
#     s3_path = f's3://{mock_s3_bucket}/term/run1/model-point/'
#     dfs = download_and_validate_excel_files(s3_path)
    
#     # Check logs for warning about missing columns
#     assert any("missing required columns" in record.message.lower() for record in caplog.records)
#     # Only valid file should be included
#     assert len(dfs) == 1
#     assert 'valid_file' in dfs



@pytest.mark.parametrize("s3_path", [
    's3://non-existent-bucket/folder/',
    's3://valuation-model/empty/',
])
def test_error_conditions(s3_path):
    """Test various error conditions"""
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {
        'Contents': []
    }
    
    with patch('boto3.client', return_value=mock_s3):
        with pytest.raises(ValueError, match="No Excel files found"):  # Partial match
            download_and_validate_excel_files(s3_path) 