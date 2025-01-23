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

def load_settings():
    """Load saved settings from a JSON file"""
    settings_file = Path("saved_settings.json")
    if settings_file.exists():
        with open(settings_file, "r") as f:
            return json.load(f)
    return None

def save_settings(settings):
    """Save settings to a JSON file"""
    settings_file = Path("saved_settings.json")
    # Convert date to string for JSON serialization
    settings["valuation_date"] = settings["valuation_date"].isoformat()
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=4)

def download_from_s3(s3_url):
    """
    Download file from S3 URL and return as a file-like object
    """
    try:
        # Parse S3 URL
        parsed_url = urlparse(s3_url)
        bucket_name = parsed_url.netloc
        key = parsed_url.path.lstrip('/')
        
        # Initialize S3 client
        s3_client = boto3.client('s3')
        
        # Download file to memory
        file_obj = io.BytesIO()
        s3_client.download_fileobj(bucket_name, key, file_obj)
        file_obj.seek(0)
        
        return file_obj
    except Exception as e:
        raise Exception(f"Error downloading from S3: {str(e)}")

def run_pricing_model(settings):
    """
    Run the pricing model using modelX lifelib with the provided settings
    """
    try:
        # Download files from S3 directly to memory
        assumption_file = download_from_s3(settings["assumption_table_url"])
        model_point_file = download_from_s3(settings["model_point_files_url"])
        
        # Read input files directly from memory
        assumptions = {
            'lapse_rate_table': pd.read_excel(assumption_file, sheet_name='lapse'),
            'inflation_rate_table': pd.read_excel(assumption_file, sheet_name='CPI'),
            'prem_exp_table': pd.read_excel(assumption_file, sheet_name='prem expenses'),
            'fixed_exp_table': pd.read_excel(assumption_file, sheet_name='fixed expenses'),
            'comm_table': pd.read_excel(assumption_file, sheet_name='commissions'),
            'disc_curve': pd.read_excel(assumption_file, sheet_name='discount curve'),
            'mort_table': pd.read_excel(assumption_file, sheet_name='mortality')
        }

        # Read model points directly from memory
        model_points_df = pd.read_excel(model_point_file, sheet_name='Model Points')
        
        # Initialize modelx model
        model = mx.read_model("Basic_Term_Model_v1")
        
        # Configure model settings
        model.Data_Inputs.proj_period = settings["projection_period"]
        model.Data_Inputs.val_date = settings["valuation_date"]
        
        # Load assumptions and model points into the model
        model.assumptions = assumptions
        model.model_points = model_points_df
        
        results = {}
        # Run model for each product group
        for product in settings["product_groups"]:
            model.product = product
            
            # Run the model calculations
            projection = model.run()
            
            # Store results
            results[product] = {
                'present_value': projection.present_value(),
                'cashflows': projection.cashflows(),
                'metrics': projection.get_metrics()
            }
     
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

def main():
    st.title("Enterprise Pricing Model Settings")
    
    # Load saved settings
    saved_settings = load_settings()
    
    # Add a settings management section
    with st.expander("Settings Management"):
        st.info("You can save your current settings or load previously saved settings.")
        if saved_settings:
            if st.button("Load Saved Settings"):
                # Convert saved date string back to datetime
                saved_settings["valuation_date"] = datetime.date.fromisoformat(
                    saved_settings["valuation_date"]
                )
                st.session_state.update(saved_settings)
                st.success("Settings loaded successfully!")
    
    # Create a form to collect all inputs
    with st.form("pricing_model_settings"):
        # Valuation Date
        val_date = st.date_input(
            "Valuation Date",
            value=saved_settings.get("valuation_date", datetime.date.today()) if saved_settings else datetime.date.today(),
            help="Select the valuation date for the pricing model"
        )
        
        # Replace file uploaders with URL inputs
        st.subheader("S3 File Locations")
        
        # Assumption Table URL
        st.markdown("##### Assumption Table S3 URL")
        assumption_table_url = st.text_input(
            "Enter S3 URL for assumption table",
            value=saved_settings.get("assumption_table_url", "") if saved_settings else "",
            help="Format: s3://bucket-name/path/to/file.xlsx"
        )
        
        # Model Point Files URL
        st.markdown("##### Model Point Files S3 URL")
        model_point_files_url = st.text_input(
            "Enter S3 URL for model point files",
            value=saved_settings.get("model_point_files_url", "") if saved_settings else "",
            help="Format: s3://bucket-name/path/to/file.xlsx"
        )
        
        # Projection Period
        projection_period = st.number_input(
            "Projection Period (Years)",
            min_value=1,
            max_value=100,
            value=saved_settings.get("projection_period", 30) if saved_settings else 30,
            help="Enter the number of years to project"
        )
        
        # Product Groups
        product_groups = st.multiselect(
            "Select Product Groups to Run",
            options=[
                "Term Life",
                "Whole Life",
                "Universal Life",
                "Annuities",
                "Group Insurance",
                "Disability Insurance"
            ],
            default=saved_settings.get("product_groups", []) if saved_settings else [],
            help="Choose one or more product groups to include in the run"
        )
        
        # Submit button
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Run Pricing Model")
        with col2:
            save_button = st.form_submit_button("Save Settings")
        
        if submitted or save_button:
            if not product_groups:
                st.error("Please select at least one product group")
                return
                
            if not all([assumption_table_url, model_point_files_url]):
                st.error("Please provide all S3 URLs")
                return
                
            # Validate S3 URLs
            for url in [assumption_table_url, model_point_files_url]:
                if not url.startswith('s3://'):
                    st.error(f"Invalid S3 URL format: {url}")
                    return
            
            # Collect settings
            run_settings = {
                "valuation_date": val_date,
                "assumption_table_url": assumption_table_url,
                "model_point_files_url": model_point_files_url,
                "projection_period": projection_period,
                "product_groups": product_groups
            }
            
            if save_button:
                save_settings(run_settings)
                st.success("Settings saved successfully!")
            
            if submitted:
                st.success("Settings validated! Ready to run pricing model.")
                
                # Run the pricing model
                with st.spinner('Running pricing model...'):
                    result = run_pricing_model(run_settings)
                    
                    if result['status'] == 'success':
                        st.success("Model run completed successfully!")
                        
                        # Display results
                        st.subheader("Model Results")
                        with st.expander(f"Results"):
                            st.write("Present Value:", result['results']['present_value'])
                            
                            st.write("Cashflows:")
                            st.dataframe(result['results']['cashflows'])

                    else:
                        st.error(result['message'])

if __name__ == "__main__":
    main()