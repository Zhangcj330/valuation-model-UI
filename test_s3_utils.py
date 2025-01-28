import pytest
import pandas as pd
import boto3
from moto import mock_aws
import io
from s3_utils import download_and_validate_excel_files
from botocore.exceptions import NoCredentialsError
from unittest.mock import patch, MagicMock

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
            'PolicyID': ['P001', 'P002'],
            'Age': [30, 40],
            'Gender': ['M', 'F'],
            'Term': [10, 20]
        })
        
        # Create invalid Excel file (missing columns)
        invalid_df = pd.DataFrame({
            'PolicyID': ['P001'],
            'Age': [30]
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

def test_valid_excel_files(mock_s3_bucket):
    """Test downloading and validating Excel files with valid data"""
    s3_path = f's3://{mock_s3_bucket}/term/run1/model-point/'
    dfs = download_and_validate_excel_files(s3_path)
    
    assert len(dfs) == 1  # Only one valid file should be processed
    assert isinstance(dfs[0], pd.DataFrame)
    assert list(dfs[0].columns) == ['PolicyID', 'Age', 'Gender', 'Term']
    assert len(dfs[0]) == 2  # Two rows in valid file

def test_no_excel_files(mock_s3_bucket):
    """Test with path containing no Excel files"""
    s3_path = f's3://{mock_s3_bucket}/empty/folder/'
    
    with pytest.raises(ValueError, match="No files found"):
        download_and_validate_excel_files(s3_path)

def test_invalid_s3_path():
    """Test with invalid S3 path"""
    with pytest.raises(Exception):
        download_and_validate_excel_files('invalid_path')

def test_missing_required_columns(mock_s3_bucket, caplog):
    """Test handling of Excel files with missing required columns"""
    s3_path = f's3://{mock_s3_bucket}/term/run1/model-point/'
    dfs = download_and_validate_excel_files(s3_path)
    
    # Check logs for warning about invalid file
    assert any("missing required columns" in record.message for record in caplog.records)
    assert len(dfs) == 1  # Only valid file should be in results

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