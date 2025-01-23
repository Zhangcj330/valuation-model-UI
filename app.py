import streamlit as st
import datetime
import os
import json
from pathlib import Path
import pandas as pd
import modelx as mx
import shutil

import boto3
import io
from urllib.parse import urlparse
from dotenv import load_dotenv
from botocore.exceptions import ClientError

def load_settings():
    """Load saved settings from a JSON file"""
    settings_file = Path("saved_settings.json")
    if not settings_file.exists():
        return None
        
    with open(settings_file, "r") as f:
        settings = json.load(f)
        # Convert date string back to datetime if needed
        if isinstance(settings.get("valuation_date"), str):
            settings["valuation_date"] = datetime.datetime.strptime(
                settings["valuation_date"], "%Y-%m-%d"
            ).date()
        return settings

def save_settings(settings):
    """Save settings to a JSON file"""
    settings_file = Path("saved_settings.json")
    # Convert date to string for JSON serialization
    settings["valuation_date"] = settings["valuation_date"].isoformat()
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=4)

def download_from_s3(s3_url):
    """
    Download file from S3 URL with authentication
    """
    try:
        # Get AWS credentials
        aws_access_key, aws_secret_key = get_aws_credentials()
        if not aws_access_key or not aws_secret_key:
            raise Exception("AWS credentials not found in .env file")
        
        # Parse S3 URL
        parsed_url = urlparse(s3_url)
        bucket_name = parsed_url.netloc
        key = parsed_url.path.lstrip('/')
        
        # Initialize S3 client with credentials and region
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=os.getenv('AWS_REGION', 'ap-southeast-1')  # Add default region
        )
        
        # First check if we can access the bucket and file
        s3_client.head_object(Bucket=bucket_name, Key=key)
        print("bucket_name", bucket_name)
        print("key", key)
        
        # If access check passed, download file
        file_obj = io.BytesIO()
        s3_client.download_fileobj(bucket_name, key, file_obj)
        file_obj.seek(0)
        
        return file_obj
        
    except Exception as e:
        raise Exception(f"Error downloading from S3: {str(e)}")

def run_pricing_model(settings):
    """Run the pricing model using modelX lifelib with the provided settings"""
    try:
        # Download and process input files
        assumptions = load_assumptions(settings["assumption_table_url"])
        model_points_df = load_model_points(settings["model_point_files_url"])
        
        # Initialize and configure model
        model = initialize_model(settings, assumptions, model_points_df)
        
        # Run model for each product group
        results = run_model_calculations(model, settings["product_groups"])
        
        return {
            'status': 'success',
            'results': results,
            'message': 'Model run completed successfully'
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error running model: {str(e)}'
        }

def load_assumptions(assumption_url):
    """Load assumption tables from S3"""
    assumption_file = download_from_s3(assumption_url)
    return {
        'lapse_rate_table': pd.read_excel(assumption_file, sheet_name='lapse'),
        'inflation_rate_table': pd.read_excel(assumption_file, sheet_name='CPI'),
        'prem_exp_table': pd.read_excel(assumption_file, sheet_name='prem expenses'),
        'fixed_exp_table': pd.read_excel(assumption_file, sheet_name='fixed expenses'),
        'comm_table': pd.read_excel(assumption_file, sheet_name='commissions'),
        'disc_curve': pd.read_excel(assumption_file, sheet_name='discount curve'),
        'mort_table': pd.read_excel(assumption_file, sheet_name='mortality')
    }

def load_model_points(model_points_url):
    """Load model points from S3"""
    model_point_file = download_from_s3(model_points_url)
    return pd.read_excel(model_point_file, sheet_name='MPF')

def initialize_model(settings, assumptions, model_points_df):
    """Initialize and configure the modelx model"""
    model = mx.read_model("Basic_Term_Model_v1")
    model.Data_Inputs.proj_period = settings["projection_period"]
    model.Data_Inputs.val_date = settings["valuation_date"]
    model.assumptions = assumptions
    model.model_points = model_points_df
    return model

def run_model_calculations(model, product_groups):
    """Run calculations for each product group"""
    results = {}
    for product in product_groups:
        model.product = product
        results[product] = {
                'present_value': model.Results_at_t.aggregate_pvs(),
                'cashflows': model.Results_at_t.aggregate_cfs(),
                'analytic': model.Results_at_t.analytic() 
            }
    
    return results

def validate_settings(settings):
    """Validate user input settings"""
    if not settings["product_groups"]:
        raise ValueError("Please select at least one product group")
        
    if not all([settings["assumption_table_url"], settings["model_point_files_url"]]):
        raise ValueError("Please provide all S3 URLs")
        
    # Validate S3 URLs
    for url in [settings["assumption_table_url"], settings["model_point_files_url"]]:
        if not url.startswith('s3://'):
            raise ValueError(f"Invalid S3 URL format: {url}")
    
    return True

def display_settings_management(saved_settings):
    """Display the settings management section"""
    with st.expander("Settings Management"):
        st.info("You can save your current settings or load previously saved settings.")
        if saved_settings and st.button("Load Saved Settings"):
            st.session_state.update(saved_settings)
            st.success("Settings loaded successfully!")

def collect_form_inputs(saved_settings):
    """Collect all form inputs and return settings dict"""
    # Valuation Date
    default_date = datetime.date.today()
    if saved_settings and "valuation_date" in saved_settings:
        default_date = saved_settings["valuation_date"]
                
    settings = {
        "valuation_date": st.date_input(
            "Valuation Date",
            value=default_date,
            help="Select the valuation date for the pricing model"
        ),
        
        "assumption_table_url": st.text_input(
            "Enter S3 URL for assumption table",
            value=saved_settings.get("assumption_table_url", "") if saved_settings else "",
            help="Format: s3://bucket-name/path/to/file.xlsx"
        ),
        
        "model_point_files_url": st.text_input(
            "Enter S3 URL for model point files",
            value=saved_settings.get("model_point_files_url", "") if saved_settings else "",
            help="Format: s3://bucket-name/path/to/file.xlsx"
        ),
        
        "projection_period": st.number_input(
            "Projection Period (Years)",
            min_value=1,
            max_value=100,
            value=saved_settings.get("projection_period", 30) if saved_settings else 30,
            help="Enter the number of years to project"
        ),
        
        "product_groups": st.multiselect(
            "Select Product Groups to Run",
            options=[
                "Term Life", "Whole Life", "Universal Life",
                "Annuities", "Group Insurance", "Disability Insurance"
            ],
            default=saved_settings.get("product_groups", []) if saved_settings else [],
            help="Choose one or more product groups to include in the run"
        )
    }
    
    return settings

def process_model_run(settings):
    """Process the model run and display results"""
    st.success("Settings validated! Ready to run pricing model.")
    
    with st.spinner('Running pricing model...'):
        result = run_pricing_model(settings)
        
        if result['status'] == 'success':
            st.success("Model run completed successfully!")
            
            # Display results
            st.subheader("Model Results")
            for product, product_results in result['results'].items():
                with st.expander(f"Results for {product}"):
                    st.write("Present Value:", product_results['present_value'])
                    st.write("Cashflows:")
                    st.dataframe(product_results['cashflows'])
                    st.write("analytic:")
                    st.write(product_results['analytic'])
        else:
            st.error(result['message'])

def get_aws_credentials():
    """
    Get AWS credentials from .env file
    Returns tuple of (access_key, secret_key)
    """
    try:
        # Load environment variables from .env file
        load_dotenv()
        
        # Get credentials from environment variables
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        
        if not aws_access_key or not aws_secret_key:
            raise Exception("AWS credentials not found in .env file")
            
        return aws_access_key, aws_secret_key
        
    except Exception as e:
        st.error(f"Error reading AWS credentials: {str(e)}")
        return None, None

def main():
    st.title("Enterprise Pricing Model Settings")
    
    # Load saved settings
    saved_settings = load_settings()
    
    # Settings management section
    display_settings_management(saved_settings)
    
    # Create form and collect inputs
    with st.form("pricing_model_settings"):
        settings = collect_form_inputs(saved_settings)
        
        # Submit buttons
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Run Pricing Model")
        with col2:
            save_button = st.form_submit_button("Save Settings")
        
        if submitted or save_button:
            try:
                validate_settings(settings)
                
                if save_button:
                    save_settings(settings)
                    st.success("Settings saved successfully!")
                
                if submitted:
                    process_model_run(settings)
                    
            except ValueError as e:
                st.error(str(e))

if __name__ == "__main__":
    main()